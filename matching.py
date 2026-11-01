# coding: utf-8
"""Regra unica de matching de sequencias de acordes.

A sequencia precisa aparecer como fatia contigua da cifra, preservando ordem e
repeticoes, e a musica inteira so pode usar acordes do vocabulario da sequencia.
Comparacao sempre em minusculas; sem enharmonia, sufixo ou baixo invertido.
"""


def casa_sequencia(cifra_lower, vocabulario, alvo_lower):
    """True se a sequencia alvo aparece na musica segundo a regra unica."""
    if not alvo_lower:
        return False

    # poda barata: nenhum acorde da musica pode estar fora do alvo
    if not vocabulario.issubset(set(alvo_lower)):
        return False

    tamanho = len(alvo_lower)
    alvo = tuple(alvo_lower)
    for inicio in range(len(cifra_lower) - tamanho + 1):
        if tuple(cifra_lower[inicio:inicio + tamanho]) == alvo:
            return True
    return False
