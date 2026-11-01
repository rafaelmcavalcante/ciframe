# coding: utf-8
"""Testes da API: catalogo, cadastro, erros, lookup, paginacao e contrato."""
import json
import threading
import unittest

from tests import support

CAMPOS_SIMILAR_SEQUENCIA = frozenset([
    'id_unico_musica', 'id_artista', 'id_musica', 'nome_artista',
    'nome_musica', 'popularidade', 'acordes', 'genero', 'url',
])

CAMPOS_MUSICA = frozenset([
    'id_unico_musica', 'id_artista', 'id_musica', 'nome_artista',
    'nome_musica', 'genero', 'popularidade', 'tom', 'cifra', 'acordes',
    'seqs_famosas', 'url',
])

SEQUENCIAS_SEED = [
    (0, ['Bm', 'G', 'D', 'A']),
    (1, ['C', 'G', 'Am', 'F']),
    (2, ['Em', 'G']),
    (3, ['C', 'A7', 'Dm', 'G7']),
    (4, ['Gm', 'F']),
    (5, ['C', 'C7', 'F', 'Fm']),
]


class ApiBase(unittest.TestCase):

    def setUp(self):
        self.main = support.reiniciar_catalogo()
        self.client = support.cliente()

    def post_acordes(self, acordes):
        return self.client.post('/sequencias', json={'acordes': acordes})

    def catalogo(self):
        resposta = self.client.get('/sequencias')
        self.assertEqual(resposta.status_code, 200)
        return support.json_da_resposta(resposta)


class CatalogoTest(ApiBase):

    def test_get_sequencias_devolve_os_seis_seeds_em_ordem_de_id(self):
        resposta = self.client.get('/sequencias')

        self.assertEqual(resposta.status_code, 200)
        corpo = support.json_da_resposta(resposta)
        self.assertEqual([item['id'] for item in corpo], [0, 1, 2, 3, 4, 5])
        self.assertEqual([item['acordes'] for item in corpo],
                         [acordes for _, acordes in SEQUENCIAS_SEED])
        for item in corpo:
            self.assertEqual(set(item), {'id', 'acordes', 'criado_em'})
            self.assertTrue(item['criado_em'])

    def test_post_valido_201_e_aparece_no_catalogo(self):
        resposta = self.post_acordes(['Am', 'F', 'C', 'G'])

        self.assertEqual(resposta.status_code, 201)
        criado = support.json_da_resposta(resposta)
        self.assertEqual(set(criado), {'id', 'acordes', 'criado_em'})
        self.assertEqual(criado['id'], 6)
        self.assertEqual(criado['acordes'], ['Am', 'F', 'C', 'G'])
        self.assertTrue(criado['criado_em'])

        catalogo = self.catalogo()
        self.assertEqual([item['id'] for item in catalogo], list(range(7)))
        self.assertEqual(catalogo[6]['acordes'], ['Am', 'F', 'C', 'G'])
        self.assertEqual(catalogo[6]['criado_em'], criado['criado_em'])

    def test_post_limites_inclusivos_aceitam_12_itens_de_12_caracteres(self):
        acordes = ['123456789012'] * 12

        resposta = self.post_acordes(acordes)

        self.assertEqual(resposta.status_code, 201)
        criado = support.json_da_resposta(resposta)
        self.assertEqual(criado['acordes'], acordes)
        self.assertEqual(len(criado['acordes']), 12)

    def test_post_valido_preserva_grafia_e_ordem(self):
        resposta = self.post_acordes(['aM', 'F', 'c', 'G'])

        self.assertEqual(resposta.status_code, 201)
        criado = support.json_da_resposta(resposta)
        self.assertEqual(criado['acordes'], ['aM', 'F', 'c', 'G'])
        self.assertEqual(self.catalogo()[6]['acordes'],
                         ['aM', 'F', 'c', 'G'])


class ValidacaoTest(ApiBase):

    def test_matriz_de_400(self):
        casos = [
            ('corpo nao-JSON',
             {'data': 'acordes=Am,F', 'content_type': 'text/plain'}),
            ('JSON malformado',
             {'data': '{', 'content_type': 'application/json'}),
            ('array em vez de objeto',
             {'data': '[]', 'content_type': 'application/json'}),
            ('string em vez de objeto',
             {'data': '"Am,F"', 'content_type': 'application/json'}),
            ('null em vez de objeto',
             {'data': 'null', 'content_type': 'application/json'}),
            ('numero em vez de objeto',
             {'data': '1', 'content_type': 'application/json'}),
            ('sem a chave acordes', {'json': {}}),
            ('acordes null', {'json': {'acordes': None}}),
            ('acordes string', {'json': {'acordes': 'Am,F'}}),
            ('lista vazia', {'json': {'acordes': []}}),
            ('mais de 12 itens',
             {'json': {'acordes': ['A%d' % i for i in range(13)]}}),
            ('item inteiro', {'json': {'acordes': [1]}}),
            ('item null', {'json': {'acordes': [None]}}),
            ('item lista', {'json': {'acordes': [['Am']]}}),
            ('item objeto', {'json': {'acordes': [{'acorde': 'Am'}]}}),
            ('token vazio', {'json': {'acordes': ['']}}),
            ('token so com espacos', {'json': {'acordes': ['   ']}}),
            ('token com espaco interno', {'json': {'acordes': ['Am F']}}),
            ('token com tab', {'json': {'acordes': ['Am\tF']}}),
            ('token com virgula', {'json': {'acordes': ['Am,F']}}),
            ('token com ponto e virgula', {'json': {'acordes': ['Am;F']}}),
            ('token com pipe', {'json': {'acordes': ['Am|F']}}),
            ('token com caractere de controle',
             {'data': json.dumps({'acordes': ['Am\u0000']}),
              'content_type': 'application/json'}),
            ('token com mais de 12 caracteres',
             {'json': {'acordes': ['AcordeComMaisDe12Caracteres']}}),
        ]

        for nome, opcoes in casos:
            with self.subTest(caso=nome):
                resposta = self.client.post('/sequencias', **opcoes)
                self.assertEqual(resposta.status_code, 400,
                                 '%s devolveu %d' % (nome, resposta.status_code))
                corpo = support.json_da_resposta(resposta)
                self.assertEqual(set(corpo), {'erro'})
                self.assertTrue(isinstance(corpo['erro'], str) and corpo['erro'])

        # nenhum 400 pode ter gravado no catalogo
        self.assertEqual(len(self.catalogo()), 6)


class DuplicidadeTest(ApiBase):

    def test_409_exato_e_409_legado_dos_seeds(self):
        exato = self.post_acordes(['Bm', 'G', 'D', 'A'])
        self.assertEqual(exato.status_code, 409)
        corpo_exato = support.json_da_resposta(exato)
        self.assertEqual(set(corpo_exato), {'erro', 'id'})
        self.assertEqual(corpo_exato['id'], 0)

        legado = self.post_acordes(['BmGDA'])
        self.assertEqual(legado.status_code, 409)
        self.assertEqual(support.json_da_resposta(legado)['id'], 0)

        # caixa e espacos normalizam para a mesma chave
        normalizada = self.post_acordes(['bm', ' g ', 'd', 'a'])
        self.assertEqual(normalizada.status_code, 409)
        self.assertEqual(support.json_da_resposta(normalizada)['id'], 0)

        self.assertEqual(len(self.catalogo()), 6)

    def test_409_exato_e_legado_apos_cadastro(self):
        primeiro = self.post_acordes(['Am', 'F', 'C', 'G'])
        self.assertEqual(primeiro.status_code, 201)
        id_novo = support.json_da_resposta(primeiro)['id']

        for nome, acordes in [
                ('exato', ['Am', 'F', 'C', 'G']),
                ('exato com caixa e espacos', ['am', 'f ', 'C', ' g']),
                ('legado sem virgulas', ['AmFCG'])]:
            with self.subTest(caso=nome):
                resposta = self.post_acordes(acordes)
                self.assertEqual(resposta.status_code, 409)
                corpo = support.json_da_resposta(resposta)
                self.assertEqual(set(corpo), {'erro', 'id'})
                self.assertEqual(corpo['id'], id_novo)

        self.assertEqual(len(self.catalogo()), 7)


class LookupTest(ApiBase):

    def test_lookup_por_chave_e_chave_legado_devolve_o_mesmo_conjunto(self):
        com_virgulas, tamanhos_virgulas = support.coletar_similares(
            self.client, 'Bm,G,D,A')
        legado, tamanhos_legado = support.coletar_similares(
            self.client, 'BmGDA')

        self.assertEqual(len(com_virgulas), 199)
        self.assertEqual(set(com_virgulas), set(legado))
        self.assertEqual(len(com_virgulas), len(legado))
        self.assertEqual(sum(tamanhos_virgulas[:2]), 199)
        self.assertEqual(sum(tamanhos_legado[:2]), 199)

    def test_lookup_case_insensitive_com_espacos(self):
        ids, _ = support.coletar_similares(self.client, 'bm, g, d, a')

        self.assertEqual(len(ids), 199)
        self.assertEqual(len(set(ids)), 199)

    def test_lookup_de_sequencia_nova_pelas_duas_chaves(self):
        resposta = self.post_acordes(['Am', 'F', 'C', 'G'])
        self.assertEqual(resposta.status_code, 201)

        com_virgulas, _ = support.coletar_similares(
            self.client, 'Am,F,C,G')
        legado, _ = support.coletar_similares(self.client, 'AmFCG')

        self.assertTrue(com_virgulas)
        self.assertEqual(set(com_virgulas), set(legado))
        self.assertEqual(len(com_virgulas), len(legado))

    def test_sequencia_desconhecida_devolve_lista_vazia(self):
        resposta = self.client.get(
            '/similares', query_string={'sequencia': 'Zz,Zz'})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data.decode('utf-8'), '[]')


class PaginacaoEGeneroTest(ApiBase):

    def test_paginacao_de_c_g_am_f(self):
        ids, tamanhos = support.coletar_similares(
            self.client, 'C,G,Am,F')

        self.assertEqual(tamanhos, [100, 100, 96, 0])
        self.assertEqual(len(ids), 296)
        self.assertEqual(len(set(ids)), 296)

        padrao = self.client.get(
            '/similares', query_string={'sequencia': 'C,G,Am,F'})
        itens = support.json_da_resposta(padrao)
        self.assertEqual(len(itens), 100)
        for item in itens:
            self.assertEqual(set(item), CAMPOS_SIMILAR_SEQUENCIA)

    def test_filtro_de_genero(self):
        todas, _ = support.coletar_similares(self.client, 'Bm,G,D,A')
        rock, _ = support.coletar_similares(
            self.client, 'Bm,G,D,A', generos='Rock')

        self.assertGreater(len(rock), 0)
        self.assertLess(len(rock), len(todas))
        self.assertTrue(set(rock) < set(todas))

        resposta = self.client.get(
            '/similares',
            query_string={'sequencia': 'Bm,G,D,A', 'generos': 'Rock',
                          'pagina': 1})
        itens = support.json_da_resposta(resposta)
        self.assertEqual(len(itens), len(rock))
        for item in itens:
            self.assertEqual(item['genero'], 'Rock')
            self.assertEqual(set(item), CAMPOS_SIMILAR_SEQUENCIA)


class ContratoTest(ApiBase):

    def test_json_dumps_content_type_text_html_e_cors(self):
        respostas = [
            ('GET /sequencias', self.client.get('/sequencias')),
            ('GET /similares',
             self.client.get('/similares',
                             query_string={'sequencia': 'Em,G'})),
            ('GET /generos', self.client.get('/generos')),
            ('POST 409',
             self.post_acordes(['Bm', 'G', 'D', 'A'])),
            ('POST 400',
             self.client.post('/sequencias', data='x',
                              content_type='text/plain')),
        ]

        for nome, resposta in respostas:
            with self.subTest(caso=nome):
                self.assertEqual(
                    resposta.headers.get('Access-Control-Allow-Origin'), '*')
                content_type = resposta.headers.get('Content-Type', '')
                self.assertTrue(content_type.startswith('text/html'),
                                '%s: %s' % (nome, content_type))
                self.assertFalse(content_type.startswith('application/json'))
                texto = resposta.data.decode('utf-8').strip()
                self.assertIn(texto[0], '[{')
                json.loads(texto)

    def test_musicas_com_12_campos_historicos(self):
        resposta = self.client.get('/musicas')

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.headers.get('Content-Type', '')
                        .startswith('text/html'))
        self.assertEqual(
            resposta.headers.get('Access-Control-Allow-Origin'), '*')

        musicas = support.json_da_resposta(resposta)
        self.assertEqual(len(musicas), 67585)
        for musica in musicas:
            self.assertEqual(set(musica), CAMPOS_MUSICA)
            self.assertNotIn('cifra_lower', musica)
            self.assertNotIn('vocabulario', musica)

    def test_musica_por_id_com_12_campos_historicos(self):
        id_musica = next(iter(self.main.musicas))

        resposta = self.client.get('/musica/%s/' % id_musica)

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.headers.get('Content-Type', '')
                        .startswith('text/html'))
        self.assertEqual(
            resposta.headers.get('Access-Control-Allow-Origin'), '*')
        musica = support.json_da_resposta(resposta)
        self.assertEqual(set(musica), CAMPOS_MUSICA)
        self.assertNotIn('cifra_lower', musica)
        self.assertNotIn('vocabulario', musica)
        self.assertEqual(musica['id_unico_musica'], id_musica)


class ConcorrenciaApiTest(ApiBase):

    def test_dois_posts_simultaneos_da_mesma_sequencia(self):
        for rodada in range(3):
            acordes = ['T%d' % rodada, 'G']
            barreira = threading.Barrier(2)
            resultados = []

            def enviar():
                barreira.wait()
                try:
                    cliente = support.cliente()
                    resposta = cliente.post('/sequencias',
                                            json={'acordes': acordes})
                    resultados.append({
                        'status': resposta.status_code,
                        'corpo': support.json_da_resposta(resposta),
                    })
                except Exception as erro:  # pragma: no cover - falha explicita
                    resultados.append({'status': 'erro',
                                       'corpo': repr(erro)})

            threads = [threading.Thread(target=enviar) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)

            with self.subTest(rodada=rodada):
                self.assertEqual(sorted(r['status'] for r in resultados),
                                 [201, 409])
                criado = [r for r in resultados if r['status'] == 201][0]
                duplicado = [r for r in resultados if r['status'] == 409][0]
                self.assertEqual(duplicado['corpo']['id'],
                                 criado['corpo']['id'])

                catalogo = self.catalogo()
                self.assertEqual(len(catalogo), 6 + rodada + 1)
                ocorrencias = [item for item in catalogo
                               if item['acordes'] == acordes]
                self.assertEqual(len(ocorrencias), 1)
                self.assertEqual(ocorrencias[0]['id'],
                                 criado['corpo']['id'])


if __name__ == '__main__':
    unittest.main()
