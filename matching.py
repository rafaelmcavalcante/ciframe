# coding: utf-8
"""Regra unica de matching e validacao sintatica de sequencias de acordes.

A sequencia precisa aparecer como fatia contigua da cifra, preservando ordem e
repeticoes, e a musica inteira so pode usar acordes do vocabulario da sequencia.
Comparacao sempre em minusculas; sem enharmonia, sufixo ou baixo invertido.
"""
import unicodedata

LIMITE_ACORDES = 12
LIMITE_TOKEN = 12
SEPARADORES = (',', ';', '|')


def montar_chaves(acordes):
    """Devolve (chave, chave_legado) normalizadas em minusculas."""
    tokens = [acorde.lower() for acorde in acordes]
    return ','.join(tokens), ''.join(tokens)


def normalizar_entrada(texto):
    """Divide por virgula, aplica trim, descarta vazios e minusculiza."""
    tokens = []
    for parte in texto.split(','):
        token = parte.strip()
        if token:
            tokens.append(token.lower())
    return tokens


def validar_acordes(valor):
    """Valida a lista de acordes de um POST.

    Devolve (tokens, None) em caso de sucesso, preservando grafia e ordem, ou
    (None, mensagem) em caso de erro. A validacao e sintatica: acorde
    desconhecido e repeticao sao aceitos.
    """
    if not isinstance(valor, list):
        return None, 'acordes deve ser uma lista'
    if not 1 <= len(valor) <= LIMITE_ACORDES:
        return None, 'acordes deve ter entre 1 e %d itens' % LIMITE_ACORDES

    tokens = []
    for item in valor:
        if not isinstance(item, str):
            return None, 'cada acorde deve ser uma string'
        token = item.strip()
        if not token:
            return None, 'acorde nao pode ser vazio'
        if len(token) > LIMITE_TOKEN:
            return None, 'acorde com mais de %d caracteres' % LIMITE_TOKEN
        if any(ch.isspace() for ch in token):
            return None, 'acorde nao pode conter espaco'
        if any(ch in token for ch in SEPARADORES):
            return None, 'acorde nao pode conter , ; ou |'
        if any(unicodedata.category(ch) == 'Cc' for ch in token):
            return None, 'acorde nao pode conter caractere de controle'
        tokens.append(token)
    return tokens, None


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
