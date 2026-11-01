# coding: utf-8
"""Testes unitarios da regra unica de matching (matching.py)."""
import unittest

from matching import (casa_sequencia, montar_chaves, normalizar_entrada,
                      validar_acordes)


def casa(cifra, alvo):
    """Reproduz o caminho de main.py: normaliza caixa antes do matcher."""
    cifra_lower = [acorde.lower() for acorde in cifra]
    alvo_lower = [acorde.lower() for acorde in alvo]
    return casa_sequencia(cifra_lower, frozenset(cifra_lower), alvo_lower)


class MatchingTest(unittest.TestCase):

    def test_case_insensitive(self):
        self.assertTrue(casa(['Am', 'F'], ['am', 'f']))
        self.assertTrue(casa(['am', 'f'], ['AM', 'F']))
        self.assertTrue(casa(['aM', 'f', 'C', 'g'], ['Am', 'F', 'c', 'G']))

    def test_normalizar_entrada_trim_e_minusculas(self):
        self.assertEqual(normalizar_entrada(' Am, f ,C,, G ,'),
                         ['am', 'f', 'c', 'g'])
        self.assertEqual(normalizar_entrada(''), [])
        self.assertEqual(normalizar_entrada(' , , '), [])

    def test_fatia_contigua_preserva_ordem(self):
        # fatia no inicio: a musica so usa acordes do alvo
        self.assertTrue(casa(['g', 'am', 'g'], ['g', 'am']))
        # fatia no meio
        self.assertTrue(casa(['g', 'c', 'g'], ['c', 'g']))
        # ordem invertida nao casa
        self.assertFalse(casa(['c', 'g', 'am', 'c'], ['c', 'am', 'g']))
        # acordes fora de ordem / com lacuna nao casam
        self.assertFalse(casa(['c', 'g', 'c', 'g'], ['c', 'g', 'g']))
        self.assertFalse(casa(['c', 'g', 'c', 'g'], ['g', 'c', 'c']))

    def test_repeticao_importa(self):
        self.assertTrue(casa(['am', 'f', 'am', 'f'], ['am', 'f', 'am']))
        self.assertTrue(casa(['am', 'f', 'am', 'f'], ['f', 'am', 'f']))
        self.assertFalse(casa(['am', 'f'], ['am', 'am']))
        self.assertFalse(casa(['am', 'f'], ['f', 'f']))

    def test_vocabulario_da_musica_contido_no_alvo(self):
        # o alvo cobre todo o vocabulario da musica e aparece como fatia
        self.assertTrue(casa(['c', 'g', 'c'], ['c', 'g']))
        # acorde fora do alvo derruba o match, mesmo com a fatia presente
        self.assertFalse(casa(['em', 'g', 'd'], ['em', 'g']))

    def test_alvo_vazio_nunca_casa(self):
        self.assertFalse(casa(['c', 'g'], []))
        self.assertFalse(casa([], []))
        self.assertFalse(casa_sequencia([], frozenset(), []))

    def test_alvo_maior_que_a_cifra(self):
        self.assertFalse(casa(['c', 'g'], ['c', 'g', 'am']))
        self.assertFalse(casa([], ['c']))
        self.assertFalse(casa(['em', 'g'], ['em', 'g', 'd']))

    def test_falso_positivo_de_substring(self):
        # "Em,G" nao pode casar dentro de "Em,G7": o vocabulario da musica
        # inclui G7, que nao pertence ao alvo
        self.assertFalse(casa(['em', 'g7'], ['em', 'g']))
        self.assertFalse(casa(['g7', 'em'], ['em', 'g']))
        self.assertFalse(casa(['em', 'g7', 'em', 'g'], ['em', 'g']))
        self.assertFalse(casa(['c'], ['c#']))
        self.assertFalse(casa(['am', 'g'], ['am', 'g7']))
        # controle: a sequencia exata continua casando
        self.assertTrue(casa(['em', 'g'], ['em', 'g']))


class ValidacaoTest(unittest.TestCase):

    def test_limites_inclusivos(self):
        tokens, erro = validar_acordes(['123456789012'] * 12)
        self.assertIsNone(erro)
        self.assertEqual(len(tokens), 12)
        self.assertEqual(tokens[0], '123456789012')

    def test_preserva_grafia_e_ordem(self):
        tokens, erro = validar_acordes([' aM ', 'F', 'c', 'G'])
        self.assertIsNone(erro)
        self.assertEqual(tokens, ['aM', 'F', 'c', 'G'])

    def test_chaves_normalizadas(self):
        self.assertEqual(montar_chaves(['Bm', 'G', 'D', 'A']),
                         ('bm,g,d,a', 'bmgda'))
        self.assertEqual(montar_chaves(['AmFCG']), ('amfcg', 'amfcg'))


if __name__ == '__main__':
    unittest.main()
