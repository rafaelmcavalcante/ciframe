# coding: utf-8
"""Testes de persistencia: init, seeds, user_version, insercao e concorrencia."""
import json
import os
import sqlite3
import tempfile
import threading
import unittest

from tests import support

import sequencias_db
from sequencias_db import (SEQUENCIAS_SEED, SequenciaDuplicada,
                           carregar_catalogo, init_db, inserir_sequencia)


def linhas_do_banco(caminho):
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute(
            'SELECT id, acordes, chave, chave_legado, criado_em '
            'FROM sequences ORDER BY id').fetchall()
    finally:
        conexao.close()


def user_version(caminho):
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute('PRAGMA user_version').fetchone()[0]
    finally:
        conexao.close()


class BancoTest(unittest.TestCase):

    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory(
            prefix='seq-db-', dir=support.DIRETORIO_TEMP)
        self.addCleanup(self.temporario.cleanup)
        self.caminho = os.path.join(self.temporario.name, 'sequencias.db')

    def test_init_cria_seeds_e_user_version(self):
        caminho_retornado = init_db(self.caminho)

        self.assertEqual(caminho_retornado, self.caminho)
        self.assertEqual(user_version(self.caminho), 1)

        linhas = linhas_do_banco(self.caminho)
        self.assertEqual([linha[0] for linha in linhas],
                         [id_seq for id_seq, _ in SEQUENCIAS_SEED])
        self.assertEqual([json.loads(linha[1]) for linha in linhas],
                         [acordes for _, acordes in SEQUENCIAS_SEED])

        for id_seq, acordes in SEQUENCIAS_SEED:
            linha = linhas[id_seq]
            esperado_chave = ','.join(acorde.lower() for acorde in acordes)
            esperado_legado = ''.join(acorde.lower() for acorde in acordes)
            self.assertEqual(linha[2], esperado_chave)
            self.assertEqual(linha[3], esperado_legado)
            self.assertTrue(linha[4].endswith('+00:00'), linha[4])

    def test_init_idempotente_nao_duplica_nem_reescreve(self):
        init_db(self.caminho)
        antes = linhas_do_banco(self.caminho)

        init_db(self.caminho)

        depois = linhas_do_banco(self.caminho)
        self.assertEqual(depois, antes)
        self.assertEqual(len(depois), 6)
        self.assertEqual(user_version(self.caminho), 1)

    def test_versao_futura_aborta_sem_escrever(self):
        conexao = sqlite3.connect(self.caminho)
        conexao.execute('PRAGMA user_version = 2')
        conexao.commit()
        conexao.close()

        with self.assertRaises(RuntimeError) as contexto:
            init_db(self.caminho)

        self.assertIn('user_version=2', str(contexto.exception))
        self.assertIn(self.caminho, str(contexto.exception))
        self.assertEqual(user_version(self.caminho), 2)

        conexao = sqlite3.connect(self.caminho)
        try:
            tabelas = [linha[0] for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")]
        finally:
            conexao.close()
        self.assertNotIn('sequences', tabelas)

    def test_esquema_de_versao_1_incompleto_aborta(self):
        conexao = sqlite3.connect(self.caminho)
        conexao.execute('CREATE TABLE sequences (id INTEGER PRIMARY KEY)')
        conexao.execute('PRAGMA user_version = 1')
        conexao.commit()
        conexao.close()

        with self.assertRaises(RuntimeError) as contexto:
            init_db(self.caminho)

        self.assertIn('nao tem as colunas esperadas', str(contexto.exception))
        conexao = sqlite3.connect(self.caminho)
        try:
            total = conexao.execute(
                'SELECT COUNT(*) FROM sequences').fetchone()[0]
        finally:
            conexao.close()
        self.assertEqual(total, 0)

    def test_carregar_catalogo_preserva_id_zero(self):
        init_db(self.caminho)

        catalogo = carregar_catalogo(self.caminho)

        self.assertEqual(sorted(catalogo['por_id']), [0, 1, 2, 3, 4, 5])
        # id 0 e valido: a busca precisa usar "is not None", nao truthiness
        self.assertIsNotNone(catalogo['por_chave'].get('bm,g,d,a'))
        self.assertEqual(catalogo['por_chave'].get('bm,g,d,a'), 0)
        self.assertEqual(catalogo['por_chave_legado'].get('bmgda'), 0)
        self.assertEqual(catalogo['por_id'][0]['acordes'],
                         ['Bm', 'G', 'D', 'A'])
        self.assertTrue(catalogo['por_id'][0]['criado_em'])

    def test_inserir_sequencia_e_duplicidades(self):
        init_db(self.caminho)

        id_seq, criado_em = inserir_sequencia(['Am', 'F', 'C', 'G'],
                                              self.caminho)
        self.assertEqual(id_seq, 6)
        self.assertTrue(criado_em.endswith('+00:00'))

        linhas = linhas_do_banco(self.caminho)
        self.assertEqual(len(linhas), 7)
        self.assertEqual(linhas[6][0], 6)
        self.assertEqual(json.loads(linhas[6][1]), ['Am', 'F', 'C', 'G'])
        self.assertEqual(linhas[6][2], 'am,f,c,g')
        self.assertEqual(linhas[6][3], 'amfcg')

        with self.assertRaises(SequenciaDuplicada) as exata:
            inserir_sequencia(['Am', 'F', 'C', 'G'], self.caminho)
        self.assertEqual(exata.exception.id_existente, 6)

        # chave_legado colide mesmo sem virgulas
        with self.assertRaises(SequenciaDuplicada) as legada:
            inserir_sequencia(['AmFCG'], self.caminho)
        self.assertEqual(legada.exception.id_existente, 6)

        # caixa/espaacos tambem sao a mesma sequencia, inclusive o seed id 0
        with self.assertRaises(SequenciaDuplicada) as seed_zero:
            inserir_sequencia(['bm', 'g', 'd', 'a'], self.caminho)
        self.assertEqual(seed_zero.exception.id_existente, 0)

        self.assertEqual(len(linhas_do_banco(self.caminho)), 7)

    def test_dois_inserts_concorrentes_da_mesma_sequencia(self):
        init_db(self.caminho)
        barreira = threading.Barrier(2)
        resultados = []

        def tentar_inserir():
            barreira.wait()
            try:
                id_seq, _ = inserir_sequencia(['Am', 'F', 'C', 'G'],
                                              self.caminho)
                resultados.append(('ok', id_seq))
            except SequenciaDuplicada as erro:
                resultados.append(('duplicada', erro.id_existente))
            except Exception as erro:  # pragma: no cover - falha explicita
                resultados.append(('erro', repr(erro)))

        threads = [threading.Thread(target=tentar_inserir) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        self.assertEqual(sorted(resultado[0] for resultado in resultados),
                         ['duplicada', 'ok'])

        sucesso = [r for r in resultados if r[0] == 'ok'][0]
        duplicada = [r for r in resultados if r[0] == 'duplicada'][0]
        self.assertEqual(duplicada[1], sucesso[1])

        conexao = sqlite3.connect(self.caminho)
        try:
            total = conexao.execute(
                'SELECT COUNT(*) FROM sequences').fetchone()[0]
            iguais = conexao.execute(
                'SELECT COUNT(*) FROM sequences WHERE chave = ?',
                ('am,f,c,g',)).fetchone()[0]
        finally:
            conexao.close()
        self.assertEqual(total, 7)
        self.assertEqual(iguais, 1)

    def test_inserts_concorrentes_de_sequencias_distintas(self):
        init_db(self.caminho)
        sequencias = [['T%d' % indice, 'G'] for indice in range(6)]
        barreira = threading.Barrier(len(sequencias))
        resultados = []

        def tentar_inserir(acordes):
            barreira.wait()
            try:
                id_seq, _ = inserir_sequencia(acordes, self.caminho)
                resultados.append(('ok', id_seq))
            except Exception as erro:  # pragma: no cover - falha explicita
                resultados.append(('erro', repr(erro)))

        threads = [threading.Thread(target=tentar_inserir, args=(acordes,))
                   for acordes in sequencias]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        self.assertEqual([resultado[0] for resultado in resultados],
                         ['ok'] * len(sequencias))
        self.assertEqual(sorted(resultado[1] for resultado in resultados),
                         list(range(6, 6 + len(sequencias))))
        self.assertEqual(len(linhas_do_banco(self.caminho)),
                         6 + len(sequencias))


if __name__ == '__main__':
    unittest.main()
