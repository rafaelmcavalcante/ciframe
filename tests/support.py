# coding: utf-8
"""Helper comum da suite: banco temporario e import tardio de main.

`main.py` roda `init_db()` no import, por isso `CIFRAME_DB` precisa apontar para
um diretorio temporario ANTES de importar o modulo. Este helper faz isso no
momento em que ele mesmo e importado; os testes nunca tocam em ./db nem no
baseline versionado.
"""
import atexit
import importlib
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

DIRETORIO_TEMP = tempfile.mkdtemp(prefix='ciframe-testes-')
CAMINHO_DB = os.path.join(DIRETORIO_TEMP, 'sequencias.db')
os.environ['CIFRAME_DB'] = CAMINHO_DB


def _limpar_diretorio_temp():
    shutil.rmtree(DIRETORIO_TEMP, ignore_errors=True)


atexit.register(_limpar_diretorio_temp)

_main = None


def importar_main():
    """Importa main uma unica vez, ja com CIFRAME_DB temporario definido."""
    global _main
    if _main is None:
        anterior = os.getcwd()
        os.chdir(RAIZ)
        try:
            _main = importlib.import_module('main')
        finally:
            os.chdir(anterior)
    return _main


def cliente():
    """Novo test client do Flask (um por teste/thread, sem estado compartilhado)."""
    return importar_main().app.test_client()


def reiniciar_catalogo():
    """Recria o banco do processo e recarrega os mapas em memoria.

    Garante isolamento entre testes de API: cada teste comeca com os 6 seeds.
    """
    main = importar_main()
    caminho = main.CIFRAME_DB_PATH
    if not os.path.abspath(caminho).startswith(os.path.abspath(DIRETORIO_TEMP)):
        raise AssertionError(
            'CIFRAME_DB fora do diretorio temporario da suite: %s' % caminho)
    if os.path.exists(caminho):
        os.remove(caminho)
    main.init_db(caminho)
    novo = main.carregar_catalogo(caminho)
    main.catalogo_sequencias.clear()
    main.catalogo_sequencias.update(novo)
    return main


def json_da_resposta(resposta):
    return json.loads(resposta.data.decode('utf-8'))


def coletar_similares(cliente_flask, sequencia, generos=None, max_paginas=10):
    """Percorre /similares?sequencia=... e devolve (ids, tamanhos das paginas)."""
    ids = []
    tamanhos = []
    for pagina in range(1, max_paginas + 1):
        params = {'sequencia': sequencia, 'pagina': pagina}
        if generos is not None:
            params['generos'] = generos
        resposta = cliente_flask.get('/similares', query_string=params)
        if resposta.status_code != 200:
            raise AssertionError(
                'GET /similares?sequencia=%s&pagina=%d devolveu %d'
                % (sequencia, pagina, resposta.status_code))
        itens = json_da_resposta(resposta)
        tamanhos.append(len(itens))
        ids.extend(item['id_unico_musica'] for item in itens)
        if not itens:
            return ids, tamanhos
    raise AssertionError(
        'mais de %d paginas para a sequencia %s' % (max_paginas, sequencia))
