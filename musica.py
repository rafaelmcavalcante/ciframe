import sys


class Musica:

    def __init__(self, id_artista, nome_artista, id_musica, nome_musica,
    
            genero, popularidade, seqs_famosas, tom, cifra):

            self.id_artista = id_artista
            self.nome_artista = nome_artista
            
            self.id_musica = id_musica
            self.nome_musica = nome_musica

            self.genero = genero
            self.popularidade = popularidade
            self.tom = tom
            self.cifra = cifra
            self.acordes = list(set(cifra))
            self.seqs_famosas = seqs_famosas

            # derivados uma unica vez para o matching de sequencias; as strings
            # sao interned para nao duplicar um objeto por token do dataset
            self.cifra_lower = [sys.intern(acorde.lower()) for acorde in cifra]
            self.vocabulario = frozenset(self.cifra_lower)

            self.id_unico_musica = '%s_%s' % (id_artista, id_musica)

            self.url = 'http://www.cifraclub.com.br/%s/%s' % (id_artista, id_musica)

    def para_dict(self):
        """Payload historico de /musicas e /musica/<id>/, sem os derivados.

        cifra_lower e vocabulario existem para o matching e nao sao
        serializaveis (frozenset) nem fazem parte do contrato da API.
        """
        dados = dict(self.__dict__)
        dados.pop('cifra_lower', None)
        dados.pop('vocabulario', None)
        return dados

    def __str__(self):
        return '%s,%s,%s' % (self.id_unico_musica, self.genero, self.popularidade)
