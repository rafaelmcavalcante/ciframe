# coding: utf-8
"""Catalogo de sequencias de acordes persistido em SQLite (stdlib apenas).

O CSV continua sendo a fonte de musicas e generos; apenas o catalogo de
sequencias vive aqui. O modulo nao depende de Flask para poder ser testado e
usado no startup sem contexto de request.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VERSAO_ESQUEMA = 1
CAMINHO_DOCKER = '/app/db/sequencias.db'
CAMINHO_LOCAL = os.path.join('db', 'sequencias.db')

COLUNAS = ('id', 'acordes', 'chave', 'chave_legado', 'criado_em')

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sequences (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  acordes      TEXT NOT NULL,
  chave        TEXT NOT NULL UNIQUE,
  chave_legado TEXT NOT NULL UNIQUE,
  criado_em    TEXT NOT NULL
)
"""

# seeds 0-5: as mesmas sequencias do dict historico de main.py
SEQUENCIAS_SEED = (
    (0, ['Bm', 'G', 'D', 'A']),
    (1, ['C', 'G', 'Am', 'F']),
    (2, ['Em', 'G']),
    (3, ['C', 'A7', 'Dm', 'G7']),
    (4, ['Gm', 'F']),
    (5, ['C', 'C7', 'F', 'Fm']),
)


class SequenciaDuplicada(Exception):
    """Ja existe uma sequencia com a mesma chave (com ou sem virgulas)."""

    def __init__(self, id_existente):
        self.id_existente = id_existente
        super(SequenciaDuplicada, self).__init__(
            'sequencia ja cadastrada com id=%s' % id_existente)


def caminho_db():
    """CIFRAME_DB > /app/db no container > ./db no ambiente local."""
    caminho = os.environ.get('CIFRAME_DB')
    if caminho:
        return caminho
    if os.path.isdir('/app'):
        return CAMINHO_DOCKER
    return CAMINHO_LOCAL


def montar_chaves(acordes):
    """Devolve (chave, chave_legado) normalizadas em minusculas."""
    tokens = [acorde.lower() for acorde in acordes]
    return ','.join(tokens), ''.join(tokens)


def _agora_utc():
    return datetime.now(timezone.utc).isoformat()


def _conectar(caminho):
    conexao = sqlite3.connect(caminho, timeout=5)
    conexao.execute('PRAGMA busy_timeout=5000')
    return conexao


def _validar_esquema(conexao, caminho):
    existentes = [linha[1] for linha in
                  conexao.execute('PRAGMA table_info(sequences)')]
    faltando = [coluna for coluna in COLUNAS if coluna not in existentes]
    if faltando:
        raise RuntimeError(
            'tabela sequences em %s nao tem as colunas esperadas: %s'
            % (caminho, ', '.join(faltando)))


def _inserir_seeds(conexao):
    criado_em = _agora_utc()
    for id_sequencia, acordes in SEQUENCIAS_SEED:
        chave, chave_legado = montar_chaves(acordes)
        conexao.execute(
            'INSERT OR IGNORE INTO sequences '
            '(id, acordes, chave, chave_legado, criado_em) '
            'VALUES (?, ?, ?, ?, ?)',
            (id_sequencia, json.dumps(acordes, ensure_ascii=False),
             chave, chave_legado, criado_em))


def init_db(caminho=None):
    """Cria diretorio/tabela, grava os seeds e ajusta user_version.

    Idempotente: pode rodar em todo startup. Banco de versao futura aborta o
    startup em vez de ser reescrito. Devolve o caminho usado.
    """
    caminho = caminho or caminho_db()
    diretorio = os.path.dirname(os.path.abspath(caminho))
    try:
        os.makedirs(diretorio, exist_ok=True)
    except OSError as erro:
        raise RuntimeError(
            'nao foi possivel criar o diretorio do banco de sequencias em %s: %s'
            % (diretorio, erro))

    try:
        conexao = _conectar(caminho)
    except sqlite3.Error as erro:
        raise RuntimeError(
            'nao foi possivel abrir o banco de sequencias em %s: %s'
            % (caminho, erro))

    try:
        versao = conexao.execute('PRAGMA user_version').fetchone()[0]
        if versao > VERSAO_ESQUEMA:
            raise RuntimeError(
                'banco de sequencias em %s tem user_version=%d; '
                'esta versao do app suporta ate %d'
                % (caminho, versao, VERSAO_ESQUEMA))
        conexao.execute(ESQUEMA)
        _validar_esquema(conexao, caminho)
        _inserir_seeds(conexao)
        if versao == 0:
            conexao.execute('PRAGMA user_version = %d' % VERSAO_ESQUEMA)
            versao = VERSAO_ESQUEMA
        conexao.commit()
        total = conexao.execute('SELECT COUNT(*) FROM sequences').fetchone()[0]
    except sqlite3.Error as erro:
        raise RuntimeError(
            'falha ao inicializar o banco de sequencias em %s: %s'
            % (caminho, erro))
    finally:
        conexao.close()

    logger.info(
        'banco de sequencias: caminho=%s user_version=%d linhas=%d',
        caminho, versao, total)
    return caminho


def carregar_catalogo(caminho=None):
    """Le todas as linhas e devolve os mapas chave/chave_legado/id."""
    caminho = caminho or caminho_db()
    try:
        conexao = _conectar(caminho)
        try:
            linhas = conexao.execute(
                'SELECT id, acordes, criado_em, chave, chave_legado '
                'FROM sequences ORDER BY id').fetchall()
        finally:
            conexao.close()
    except sqlite3.Error as erro:
        raise RuntimeError(
            'falha ao carregar o catalogo de sequencias de %s: %s'
            % (caminho, erro))

    catalogo = {
        'por_chave': {},
        'por_chave_legado': {},
        'por_id': {},
    }
    for id_sequencia, acordes_json, criado_em, chave, chave_legado in linhas:
        catalogo['por_chave'][chave] = id_sequencia
        catalogo['por_chave_legado'][chave_legado] = id_sequencia
        catalogo['por_id'][id_sequencia] = {
            'acordes': json.loads(acordes_json),
            'criado_em': criado_em,
        }

    logger.info('catalogo de sequencias: caminho=%s linhas=%d',
                caminho, len(catalogo['por_id']))
    return catalogo


def inserir_sequencia(acordes, caminho=None):
    """Insere preservando grafia/ordem e devolve (id, criado_em).

    Conexao curta por operacao (sem compartilhar entre threads). Colisao em
    qualquer chave vira SequenciaDuplicada com o id existente.
    """
    caminho = caminho or caminho_db()
    chave, chave_legado = montar_chaves(acordes)
    criado_em = _agora_utc()

    conexao = _conectar(caminho)
    try:
        try:
            cursor = conexao.execute(
                'INSERT INTO sequences (acordes, chave, chave_legado, criado_em) '
                'VALUES (?, ?, ?, ?)',
                (json.dumps(acordes, ensure_ascii=False), chave, chave_legado,
                 criado_em))
            id_sequencia = cursor.lastrowid
            conexao.commit()
        except sqlite3.IntegrityError:
            linha = conexao.execute(
                'SELECT id FROM sequences WHERE chave = ? OR chave_legado = ? '
                'LIMIT 1', (chave, chave_legado)).fetchone()
            conexao.rollback()
            raise SequenciaDuplicada(linha[0] if linha is not None else None)
    finally:
        conexao.close()

    return id_sequencia, criado_em
