# coding: utf-8
"""Equivalencia do matcher com a tag SEQ_FAMOSA do CSV nas 67.585 linhas.

A logica de referencia vem de scripts/research_matching.py (experimento, nao
teste): `legacy_tag_rule` e a reproducao literal da regra que gerou a tag.
"""
import importlib.util
import os
import unittest

from tests import support

from matching import casa_sequencia


def carregar_research_matching():
    caminho = os.path.join(support.RAIZ, 'scripts', 'research_matching.py')
    especificacao = importlib.util.spec_from_file_location(
        'research_matching_para_teste', caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


class EquivalenciaComTagTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.main = support.importar_main()
        cls.research = carregar_research_matching()
        cls.seeds = list(cls.main.SEQUENCIAS_SEED)
        cls.alvos = {
            id_seq: [acorde.lower() for acorde in acordes]
            for id_seq, acordes in cls.seeds
        }

    def test_matcher_iguala_tag_e_regra_legada_em_todas_as_linhas(self):
        linhas = 0
        contagens = {id_seq: 0 for id_seq, _ in self.seeds}
        divergencias_tag = []
        divergencias_legado = []

        for musica in self.main.musicas.values():
            linhas += 1
            tags = set(id_seq for id_seq, _ in self.seeds
                       if str(id_seq) in musica.seqs_famosas)
            calculado = set()
            legado = set()

            for id_seq, acordes in self.seeds:
                if casa_sequencia(musica.cifra_lower, musica.vocabulario,
                                  self.alvos[id_seq]):
                    calculado.add(id_seq)
                if self.research.legacy_tag_rule(musica.cifra, acordes):
                    legado.add(id_seq)

            if calculado != tags:
                divergencias_tag.append((musica.id_unico_musica,
                                         sorted(tags), sorted(calculado)))
            if legado != tags:
                divergencias_legado.append((musica.id_unico_musica,
                                            sorted(tags), sorted(legado)))
            for id_seq in calculado:
                contagens[id_seq] += 1

        self.assertEqual(linhas, 67585)
        self.assertEqual(divergencias_tag, [],
                         'primeiras divergencias: %r' % divergencias_tag[:5])
        self.assertEqual(divergencias_legado, [],
                         'primeiras divergencias: %r'
                         % divergencias_legado[:5])
        self.assertEqual(contagens, {0: 199, 1: 296, 2: 4, 3: 5, 4: 7, 5: 3})
        self.assertEqual(sum(contagens.values()), 514)


if __name__ == '__main__':
    unittest.main()
