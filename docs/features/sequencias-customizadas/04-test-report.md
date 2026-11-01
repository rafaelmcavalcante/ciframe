# Relatório de testes — Sequências de Acordes Customizadas

## Resultado da suíte

- **38 testes, todos passando** (`Ran 38 tests — OK`). Execução local em Python
  3.14.8 (10,1 s a 10,7 s); a mesma suíte foi rodada no Python 3.9.22 da imagem
  Docker (`python:3.9-slim` do `Dockerfile`), com 38 testes OK em 13,6 s. A maior
  parte do tempo é o carregamento único do CSV e a passada de equivalência.
- Nenhum bug de implementação foi encontrado. Nenhuma linha de `main.py`,
  `matching.py`, `sequencias_db.py`, `musica.py` ou do frontend foi alterada
  para fazer teste passar.
- `requirements.txt` continua igual; a suíte usa só `unittest` e a stdlib.

Distribuição dos testes por arquivo:

| Arquivo | Testes | Foco |
|---|---:|---|
| `tests/test_matching.py` | 11 | matcher e validação sintática |
| `tests/test_db.py` | 8 | SQLite, seeds, `user_version`, concorrência |
| `tests/test_api.py` | 17 | catálogo, 400/409/201, lookup, paginação, contrato |
| `tests/test_equivalence.py` | 1 | equivalência com a tag nas 67.585 linhas |
| `tests/test_regressao.py` | 1 | regressão das 6 sequências por conjunto |
| **Total** | **38** | |

Isolamento: `tests/support.py` cria um diretório temporário com
`tempfile.mkdtemp()` e define `CIFRAME_DB` **antes** de importar `main`.
Cada teste de API apaga e recria o banco temporário e recarrega os mapas em
memória, então todo teste começa com os 6 seeds. A suíte nunca lê nem escreve
em `./db` e nunca toca em `docs/features/sequencias-customizadas/baseline/`
(os fixtures são apenas lidos).

## Cobertura

### Matching (`matching.py`)

- Caixa: `Am/F` casa com `am/f`, `AM/F` e grafias mistas.
- Normalização de entrada: `trim`, descarte de vazios, minúsculas e separação
  por vírgula (`' Am, f ,C,, G ,'` → `['am','f','c','g']`).
- Fatia contígua com ordem preservada: match no início, no meio, ordem inversa
  rejeitada, lacunas rejeitadas.
- Repetições: `am,f,am` dentro de `am,f,am,f` casa; `am,am` em `am,f` não casa.
- Vocabulário da música contido no alvo, inclusive o caso em que a fatia existe
  mas sobra acorde fora do alvo.
- Alvo vazio e alvo maior que a cifra nunca casam.
- **Falso positivo de substring:** `Em,G` **não** casa com `Em,G7` (nem com
  `G7,Em`, nem com `Em,G7,Em,G`), `C` não casa com `C#` e `Am,G` não casa com
  `Am,G7`. O controle exato `Em,G` continua casando.
- Validação: limites inclusivos de 12 itens × 12 caracteres, preservação de
  grafia/ordem e montagem de `chave`/`chave_legado`
  (`Bm,G,D,A` → `bm,g,d,a` / `bmgda`).

### Persistência (`sequencias_db.py`)

- `init_db()` cria a tabela, grava os seeds 0–5 com ids explícitos,
  `chave`, `chave_legado` e `criado_em` em UTC (`+00:00`), e deixa
  `user_version=1`.
- Segunda inicialização é idempotente: mesmas linhas, sem duplicar e sem
  reescrever `user_version`.
- Banco de versão futura (`user_version=2`) aborta com `RuntimeError` citando a
  versão e o caminho, **sem** criar a tabela nem escrever.
- Esquema de versão 1 incompleto aborta com mensagem explícita e não grava.
- `carregar_catalogo()` preserva o **id 0** nos dois mapas (`bm,g,d,a` e
  `bmgda`), cobrindo o `is not None` em vez de truthiness.
- Inserção: id 6, grafia e ordem preservadas, chaves normalizadas; duplicata
  exata, duplicata legada (`AmFCG`) e duplicata de seed com caixa diferente
  (`bm,g,d,a` → id 0) lançam `SequenciaDuplicada` com o id existente.
- Concorrência no banco: dois inserts simultâneos da mesma sequência produzem
  exatamente um sucesso e uma duplicidade, com uma única linha gravada; seis
  inserts simultâneos de sequências distintas retornam ids 6–11, sem
  `database is locked`.

### API (`main.py`)

- `GET /sequencias`: 200, ids 0–5 em ordem, acordes iguais aos seeds, exatamente
  `{id, acordes, criado_em}` por item.
- `POST /sequencias` válido: 201, id 6, objeto criado igual ao que aparece no
  catálogo; limites de 12 × 12 aceitos; grafia/ordem preservadas.
- Matriz de **24 casos de 400**: corpo não-JSON, JSON malformado, array/string/
  `null`/número no lugar do objeto, sem `acordes`, `acordes` nulo ou string,
  lista vazia, 13 itens, itens não-string (inteiro, `null`, lista, objeto),
  token vazio/só espaços/espaço interno/tab/vírgula/ponto e vírgula/pipe/
  caractere de controle/mais de 12 caracteres. Todos devolvem `{"erro": "..."}`
  e nenhum grava no catálogo.
- **409** exato e legado nos seeds (sempre com `id: 0`, inclusive `BmGDA` e
  `bm, g, d, a`), e após cadastro (exato, com caixa/espaços e legado sem
  vírgulas), sempre com o mesmo `id`.
- Lookup: `Bm,G,D,A` e `BmGDA` devolvem o mesmo conjunto de 199; caixa/espaços
  (`bm, g, d, a`) também devolvem 199; sequência nova `Am,F,C,G` funciona pelas
  duas chaves e devolve o mesmo conjunto (278 músicas, medido; o teste compara
  os conjuntos em vez de fixar o número); desconhecida (`Zz,Zz`) devolve
  **exatamente** `[]` com 200.
- Paginação: `C,G,Am,F` produz páginas `[100, 100, 96, 0]`, 296 ids, sem
  duplicatas.
- Filtro de gênero: `Bm,G,D,A&generos=Rock` devolve subconjunto próprio de
  199, todos com `genero == "Rock"`, e o payload mantém os 9 campos.
- Contrato: `GET /sequencias`, `GET /similares`, `GET /generos`, `POST` 409 e
  `POST` 400 devolvem `Content-Type: text/html`, `Access-Control-Allow-Origin:
  *` e corpo JSON serializado por `json.dumps` (nunca `application/json`).
- `GET /musicas`: 67.585 itens, cada um com exatamente os 12 campos históricos,
  sem `cifra_lower` nem `vocabulario`. `GET /musica/<id>/`: 12 campos, mesmo
  `id_unico_musica`, sem os campos derivados.
- Concorrência na API: em 3 rodadas, dois `POST` simultâneos da mesma sequência
  devolvem exatamente um 201 e um 409 com o mesmo id, uma única linha no
  catálogo e nunca 500.

### Equivalência com a tag (`tests/test_equivalence.py`)

Percorre as **67.585 músicas** carregadas por `main` e, para cada uma, compara o
conjunto de seeds encontrado por `casa_sequencia()` com:

1. a tag `seqs_famosas` lida do CSV; e
2. `legacy_tag_rule()` de `scripts/research_matching.py`, reprodução literal da
   regra que gerou a tag.

Resultado: **zero divergências** nas duas comparações e contagens exatas
`{0: 199, 1: 296, 2: 4, 3: 5, 4: 7, 5: 3}` (514 no total). O CSV usado foi
`data/top/dataset_final.csv`, sha256
`5f94f49b945ffac76f9a114b353b51d6a07b9e6feeb1243ce5989295234b9207`.

### Frontend (verificação manual)

Não existe harness de frontend no repositório e a suíte não inventou um. O que
foi verificado manualmente, com gunicorn temporário em `127.0.0.1:5010`
(`CIFRAME_DB` em `/tmp`), Firefox headless via BiDi:

- Abrir `/#/porsequencia` mostra **6** sequências e **21** hexágonos.
- Cadastrar `Am, F, C, G` leva a **7** sequências, seleciona a nova e dispara a
  busca com **100** cards na página 1 (mesmo contrato de
  `?sequencia=Am,F,C,G`).
- Cadastrar `Bm, G, D, A` (duplicata) exibe `sequencia ja cadastrada (id 0)` e
  não cria uma oitava sequência.
- Buscar `Zz, Zz` termina com **8** blocos / **0** cards e a mensagem
  “Nenhuma música encontrada” (o bloco extra é o estado vazio, não uma
  sequência).
- O estado “Buscando…” foi observado durante as buscas reais.
- `node --check` passou em
  `static/assets/js/controllers/sequencia.js` e `static/assets/js/routes.js`.

## Teste de regressão obrigatório

As 6 sequências originais continuam devolvendo **exatamente os mesmos conjuntos
de ids** de antes da migração para SQLite. O teste
`tests/test_regressao.py` percorre todas as páginas de `/similares` e compara o
conjunto com `docs/features/sequencias-customizadas/baseline/seq-N-ids.json`:

| id | `sequencia` | total esperado | resultado |
|---:|---|---:|---|
| 0 | `Bm,G,D,A` | 199 | ✅ 199 |
| 1 | `C,G,Am,F` | 296 | ✅ 296 |
| 2 | `Em,G` | 4 | ✅ 4 |
| 3 | `C,A7,Dm,G7` | 5 | ✅ 5 |
| 4 | `Gm,F` | 7 | ✅ 7 |
| 5 | `C,C7,F,Fm` | 3 | ✅ 3 |
| | **total** | **514** | ✅ **514** |

Critério seguido à risca: comparação por **conjunto** de `id_unico_musica`,
não por ordem; `ids_sha256` e ordem não entram. As contagens também aparecem de
forma independente na equivalência com a tag (seção anterior) e no teste de
paginação da API.

## Como rodar

A partir da raiz do repositório, com o virtualenv já criado:

```
.venv/bin/python -m unittest discover -s tests -t . -v
```

O comando não precisa de servidor rodando, Docker nem banco preparado: o helper
cria o banco temporário. A suíte inteira leva ~10–16 s (a maior parte é o
carregamento único do CSV e a passada de equivalência nas 67.585 linhas).

## O que ficou de fora

- **Frontend automatizado:** sem harness no repo (AngularJS 1.4.9 por CDN, sem
  build), não havia como rodar testes de UI sem adicionar dependência ou
  infraestrutura nova. A verificação foi manual, como descrito acima.
- **Inspeção visual/pixel e CSS:** layout, cores dos hexágonos, responsividade e
  aparência dos estados não foram inspecionados automaticamente.
- **Estados de erro do frontend no browser:** o estado de carregamento foi
  observado, mas o erro de `GET /sequencias` com “Tentar de novo” **não** foi
  forçado no DevTools nesta rodada; o código foi revisado, não exercitado na UI.
- **Múltiplos workers gunicorn:** a suíte roda com os mapas em memória de um
  único processo. O comportamento documentado (um `POST` em um worker não é
  visto por outro) não foi testado; a configuração atual continua com 1 worker.
- **Volume Docker e persistência entre containers:** validados manualmente na
  fase de implementação (registro no `03-plan.md`), mas não fazem parte desta
  suíte, que usa banco temporário. `docker rm` + novo `docker run` com/sem `-v`
  não foram reexecutados aqui.
- **Docker build/imagem:** a suíte roda no `.venv` local, não dentro da imagem.
- **Percurso de `POST` concorrente contra o gunicorn real:** a concorrência foi
  testada no nível do banco e via test client Flask em threads. A garantia de
  produção continua sendo o `UNIQUE` + `busy_timeout` + 1 worker, não um teste
  de carga.
- **`/musicas` e `/musica/<id>/` com todos os ids:** o teste de `/musicas`
  valida os 12 campos nas 67.585 músicas; `/musica/<id>/` é amostrado em um id,
  não em todos.
- **Performance:** tempos de startup, RSS e latência de busca não têm teste de
  regressão automatizado; as medições estão registradas no `03-plan.md`.
- **Outras versões de Python/navegadores:** a suíte rodou em Python 3.14.8
  (local) e 3.9.22 (imagem Docker); só Firefox headless foi usado no frontend.
