# coding: utf-8
"""Regressao obrigatoria: 6 sequencias por CONJUNTO de ids contra o baseline.

Ordem dos resultados e `ids_sha256` nao entram no criterio (baseline/README.md).
"""
import json
import os
import unittest

from tests import support

BASELINE = os.path.join(support.RAIZ, 'docs', 'features',
                        'sequencias-customizadas', 'baseline')

SEQUENCIAS = [
    (0, 'Bm,G,D,A', 199),
    (1, 'C,G,Am,F', 296),
    (2, 'Em,G', 4),
    (3, 'C,A7,Dm,G7', 5),
    (4, 'Gm,F', 7),
    (5, 'C,C7,F,Fm', 3),
]


class RegressaoTest(unittest.TestCase):

    def setUp(self):
        self.main = support.reiniciar_catalogo()
        self.client = support.cliente()

    def test_conjuntos_e_totais_batem_com_o_baseline(self):
        total = 0

        for id_seq, sequencia, esperado in SEQUENCIAS:
            with self.subTest(sequencia=sequencia):
                caminho = os.path.join(BASELINE, 'seq-%d-ids.json' % id_seq)
                with open(caminho, encoding='utf-8') as arquivo:
                    ids_baseline = set(json.load(arquivo)['ids'])

                ids, _ = support.coletar_similares(self.client, sequencia)

                self.assertEqual(len(ids_baseline), esperado)
                self.assertEqual(len(ids), esperado)
                self.assertEqual(len(set(ids)), esperado)
                self.assertEqual(
                    set(ids), ids_baseline,
                    'regressao na sequencia %s: faltando=%d sobrando=%d'
                    % (sequencia,
                       len(ids_baseline - set(ids)),
                       len(set(ids) - ids_baseline)))
                total += len(ids)

        self.assertEqual(total, 514)


if __name__ == '__main__':
    unittest.main()
