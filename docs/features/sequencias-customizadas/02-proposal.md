# Proposta — Sequências de Acordes Customizadas

## Abordagem escolhida

A abordagem escolhida é a **Proposta 1**: uma única regra de matching — a regra
legada, calculada em tempo real sobre `musica.cifra` — aplicada tanto às 6
sequências existentes quanto às novas, com o catálogo de sequências persistido
em SQLite. Músicas e gêneros continuam vindo de
`data/top/dataset_final.csv` em memória (`main.py:49-98`).

### Algoritmo de matching

Uma sequência é uma lista ordenada de acordes `S = [s1, ..., sk]`; a cifra de
uma música é a lista ordenada de tokens `C = [c1, ..., cn]`, com repetições
(`Musica.cifra`, `musica.py:16-17` — não `Musica.acordes`, que é um `set` sem
ordem). A música casa com a sequência quando as duas condições valem:

1. **Adjacência:** existe `i` tal que `lower(C[i:i+k]) == lower(S)`, isto é, a
   sequência aparece como fatia contígua da cifra, preservando ordem e
   repetições.
2. **Vocabulário contido:** todo token de `C` (em minúsculas) pertence ao
   conjunto de tokens de `S` (em minúsculas). A música inteira só pode usar
   acordes que estão na sequência.

A comparação é **case-insensitive** (`lower()`), sem normalização de enharmonia
(`C#`/`Db`), sufixo (`Bm`/`Bm7`) ou baixo invertido (`A`/`A/C#`). Sequência
vazia nunca casa (e é rejeitada no cadastro). Essa é a reprodução em nível de
tokens da regra que gerou a tag `SEQ_FAMOSA` em
`scripts/generate_data_set.py:7-24`; o experimento `scripts/research_matching.py`
já havia mostrado que as definições “naturais” (contígua, com lacunas, contenção
de conjuntos, ordem dos distintos) produzem milhares de falsos positivos e
**nenhuma** reproduz o baseline. A versão por tokens foi comparada com a versão
literal por string em todas as linhas: **0 divergências em 67.585 linhas**.

Consequência de produto: sequências novas também são estritas. Nos exemplos
medidos, `Am,F,C,G` devolve 278 músicas e `E,B,C#m,A` devolve 103 — pouco, mas
coerente com a proposta do app (“músicas que você consegue tocar só com esses
acordes”). A alternativa de relaxar o vocabulário para sequências novas
(aumentaria para 1.125 e 552, respectivamente) foi descartada porque cria duas
semânticas para o mesmo botão de busca.

No startup, `main.py` passa a guardar `cifra` em minúsculas e o vocabulário de
cada música (custo medido: ~407 ms para 67.585 linhas). Com isso, uma busca
custa ~17 ms no caso de 4 acordes e 15–26 ms em sequências de 8–12 acordes,
porque o filtro de vocabulário poda a maioria das músicas antes da checagem de
adjacência. O matching não usa mais `Musica.seqs_famosas` (`main.py:209`); o
parsing da tag (`main.py:63`, `musica.py:18`) é mantido temporariamente apenas
como conferência de regressão.

### Ordem dos resultados e critério de regressão

A ordem atual **não é determinística**: `apply_filtro` concatena listas por
gênero na ordem de `generos`, que nasce de `list(set(...))` (`main.py:92`,
`main.py:266-272`); com hash randomization, dois processos devolvem os mesmos
ids em ordens diferentes. O baseline em
`docs/features/sequencias-customizadas/baseline/` é uma foto de uma dessas
ordens e não é reproduzível por nenhum processo novo (testado inclusive com
`PYTHONHASHSEED` de 0 a 2000).

Por isso, **não congelamos a ordem do fixture**. O critério de regressão passa a
ser: para cada uma das 6 sequências, o **conjunto de `id_unico_musica`** e o
**total** devem ser idênticos ao fixture (199, 296, 4, 5, 7, 3; 514 no total), e
os 9 campos de cada música devem ser iguais por id. A ordem e o
`ids_sha256` do `manifest.json` não são comparados; `baseline/README.md` já
documenta essa comparação por conjunto (substituiu o `diff -r`, que comparava
ordem).

Para eliminar a nondeterminismo, a ordem dos gêneros passa a ser **alfabética**
(`generos = sorted(generos)` em `main.py:92`). Isso é uma **mudança de
comportamento observável**: a ordem dos resultados de `/similares` (por
sequência e por acordes), `/search` e `/generos` deixa de variar entre
processos. Conjuntos, contagens e paginação (100 por página, `main.py:35`,
`main.py:226-228`) não mudam. A ordem alfabética também não coincide com a do
fixture; a regressão continua sendo por conjunto + contagem, como acima.

### Banco de dados

SQLite via `sqlite3` da biblioteca padrão (3.46.1 na imagem; nenhuma dependência
nova, `requirements.txt:4-5` não muda). O arquivo fica em
`/app/db/sequencias.db` (ou `CIFRAME_DB`, se definido), nunca em `/app/data`:
o CSV está em `/app/data/top/dataset_final.csv` (`Dockerfile:8`) e um volume
montado em `/app/data` esconderia o CSV, quebrando o startup. Em ambiente local
sem Docker, o caminho padrão é `./db/sequencias.db`.

A persistência entre recriações depende do volume nomeado:

```
docker run -p 8080:8080 -v ciframe-data:/app/db ciframe
```

`docker restart` no mesmo container já preserva a camada gravável, mas
`docker rm`/novo `docker run`/novo build perdem o arquivo sem o volume. Bind
mount não é necessário; o volume nomeado é mais portátil e não depende de
caminho do host. `.gitignore` e `.dockerignore` passam a excluir `db/` e
`*.db`, para que um banco local não seja copiado para a imagem pelo
`COPY . .` (`Dockerfile:8`). O `README.md` e o `AGENTS.md` passam a documentar o
comando com `-v`.

A inicialização é idempotente: cria o diretório do banco e a tabela se não
existirem, registra os seeds 0–5 com `INSERT OR IGNORE` e grava
`PRAGMA user_version` para migrações futuras.
O catálogo é pequeno e lido inteiro no startup para um mapa em memória
(`chave`/`chave_legado` → id), atualizado a cada `POST`; assim `/similares` não
faz leitura de banco por requisição. O `Dockerfile` continua com um único
processo gunicorn (`Dockerfile:12`), o que mantém o mapa consistente; se o
número de workers crescer, será preciso revalidar cache e concorrência.

### Esquema de dados (alto nível)

Uma única tabela, sem tabela de matches (o matching é calculado em tempo real):

```sql
CREATE TABLE IF NOT EXISTS sequences (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  acordes      TEXT NOT NULL,          -- JSON array, na ordem cadastrada
  chave        TEXT NOT NULL UNIQUE,   -- lower(','.join(acordes))
  chave_legado TEXT NOT NULL UNIQUE,   -- lower(''.join(acordes))
  criado_em    TEXT NOT NULL           -- UTC, ISO-8601
);
```

- `acordes` guarda a lista ordenada como JSON (o catálogo é pequeno; não há
  necessidade de tabela filha).
- `chave` é a identidade canônica, sem espaços e em minúsculas, usada para
  deduplicação.
- `chave_legado` é a forma sem vírgulas, que preserva a compatibilidade com
  `?sequencia=BmGDA` (o backend atual remove vírgulas em `main.py:191`). As duas
  colunas são `UNIQUE`; um cadastro que colida em qualquer uma delas recebe 409.
- Os 6 seeds entram com ids 0–5 e as mesmas listas de `main.py:40-45`; novas
  sequências começam em 6.
- Migrações ficam para o plano; nesta fase basta a criação idempotente e o
  `user_version`.

### API

Todos os endpoints continuam devolvendo `json.dumps(...)` como string (não
`jsonify`), mantendo o `Content-Type: text/html` e o
`Access-Control-Allow-Origin: *` (`main.py:274-277`). O frontend AngularJS
continua conseguindo consumir porque o corpo começa com `[` ou `{`, caso em que
o `$http` faz o parse do JSON mesmo com `text/html`.

**`GET /sequencias`** — catálogo completo, ordenado por `id`:

```json
[{"id": 0, "acordes": ["Bm", "G", "D", "A"], "criado_em": "2026-11-01T18:00:00Z"}]
```

Sem paginação nesta fase (o catálogo é pequeno; paginação fica fora do escopo).

**`POST /sequencias`** — cadastro anônimo, corpo JSON
`{"acordes": ["Am", "F", "C", "G"]}`:

- `201` com o objeto criado (mesmo formato do `GET`).
- `400` para payload inválido: corpo não-JSON, sem `acordes`, `acordes` que não
  seja lista, lista vazia, mais de 12 acordes, item que não seja string, token
  vazio depois do `trim`, token com mais de 12 caracteres, ou token contendo
  espaço, `,`, `;`, `|` ou caractere de controle.
- `409` para sequência duplicada (colisão em `chave` ou `chave_legado`), com
  `{"erro": "...", "id": <id existente>}`.

A validação é **sintática, não musical**: qualquer token não vazio que passe
pelos limites acima é aceito. Não usamos `/acordes` (`main.py:162-164`) como
lista fechada porque ele é derivado do parsing do CSV e contém lixo (`2x`,
`)`, `:`; ver pesquisa §1.3); uma regex musical estrita rejeitaria variações
legítimas do corpus (`Dm4/7`, `F#/Bb`, `A4(7`) e typos do usuário. Acorde
desconhecido é aceito e simplesmente devolve poucos ou nenhum resultado na
busca. Repetições dentro da sequência são permitidas, porque repetição é
significativa para o matching contíguo.

**`GET /similares?sequencia=...`** — contrato inalterado (9 campos, filtro de
gênero, página de 100). O lookup normaliza assim:

1. divide a entrada por `,`, aplica `trim` em cada token, descarta tokens vazios
   e converte para minúsculas;
2. monta `chave = ','.join(tokens)` e `chave_legado = ''.join(tokens)`;
3. procura primeiro por `chave` e depois por `chave_legado`; se não achar,
   devolve `[]` (comportamento atual de `main.py:194-197`).

Assim `?sequencia=Bm,G,D,A` continua funcionando (o frontend atual monta essa
forma em `static/assets/js/controllers/sequencia.js:55-77`), e
`?sequencia=BmGDA` continua funcionando via `chave_legado`, como hoje. Duas
mudanças deliberadas e não quebradas: espaços ao redor dos acordes
(`Bm, G, D, A`, que hoje devolve `[]`) e caixa (`bm,g,d,a`, que hoje devolve
`[]`) passam a ser aceitos, porque o matching já é case-insensitive.

### Frontend

Em `static/assets/js/controllers/sequencia.js`:

- remover os quatro literais de `sequencia.js:2-37`; no início do controller,
  `$http.get("sequencias")` e montar `vm.sequenciasFamosas` a partir do
  catálogo, convertendo cada acorde para `{acorde: "...", cor: "#2E1C74"}` para
  continuar usando `df-hex`;
- adicionar o formulário de cadastro: `vm.novaSequencia` (texto),
  `vm.cadastrando`, `vm.erroCadastro`; `vm.cadastrarSequencia()` divide por
  vírgula, faz `trim`, valida os mesmos limites do servidor e faz
  `$http.post("sequencias", {acordes: [...]})`; em `201`, recarrega/append no
  catálogo, seleciona a sequência e chama `pesquisarPorSequencia`; em `400`/`409`,
  mostra a mensagem devolvida;
- manter `createChordsString` (`sequencia.js:55-61`) e a URL relativa
  (`sequencia.js:72-77`), que já produzem `?sequencia=Am,F,C,G`; o filtro de
  gênero e a busca continuam iguais.

Em `static/templates/sequencia.html`: formulário acima dos hexágonos
(`:5-14`), com input de texto, botão, estado de carregamento e mensagem de erro;
lista de sequências continua em `ng-repeat`; corrigir o
`ng-hide="music.diferenca.length"` de `:43`, que nunca esconde nada no fluxo de
sequência porque a resposta não tem `diferenca`; adicionar estado vazio
(“nenhuma música encontrada”). Não há mudança de rota (`routes.js:17-21`) nem de
carregamento de script (`index.html:145`).

## Alternativas consideradas e descartadas

**Proposta 2 — duas regras (legado para as 6, progressão para as novas) com
matches materializados.** Daria resultados bem melhores para sequências novas
(866 vs 199 no exemplo `Bm,G,D,A`), mas cria duas semânticas para o mesmo botão,
exige uma tabela `sequence_matches` que cresce com o catálogo aberto, custa
~260–310 ms por cadastro para materializar e precisa ser rematerializada se o
CSV mudar. Foi descartada por complexidade e por dificultar explicar ao usuário
por que a mesma busca se comporta diferente conforme a sequência.

**Proposta 3 — manter o caminho da tag `SEQ_FAMOSA` para as 6 e calcular apenas
as novas.** Tem o menor risco de regressão, mas mantém duas fontes de verdade
(tag no CSV e regra calculada). Hoje elas concordam em 67.585/67.585 linhas, mas
podem divergir se o CSV for regenerado, e a tag continuaria sendo um artefato
obrigatório do build do CSV. Foi descartada porque a regra única é mais simples
de testar e não exige tratamento especial para ids 0–5.

**Outras opções de banco** (TinyDB, `shelve`, Postgres) foram descartadas com
base na pesquisa §3.3: TinyDB adiciona dependência e rebuild; `shelve` não tem
schema, `UNIQUE` nem consultas; Postgres exige um segundo processo/serviço e
contraria o container único do `docs/adr/0001-local-only-docker-deploy.md`.
SQLite entrega constraints e transações sem sair da stdlib.

## Escopo explícito

**Dentro do escopo:**

- Criar o banco SQLite, a tabela `sequences`, a inicialização idempotente e o
  seed das 6 sequências com ids 0–5.
- Implementar a regra de matching única sobre `musica.cifra`, com normalização
  de caixa no startup, e usá-la em `/similares?sequencia=...` para todas as
  sequências.
- `GET /sequencias` e `POST /sequencias`, com deduplicação por `chave` e
  `chave_legado`, validação sintática e os status 201/400/409.
- Lookup compatível com `?sequencia=Bm,G,D,A` e `?sequencia=BmGDA`.
- Frontend `#/porsequencia` lendo o catálogo do backend e cadastrando sequência
  nova; correção do `ng-hide` e estado vazio.
- Ordenar os gêneros alfabeticamente para tornar a ordem determinística,
  documentando a mudança de comportamento.
- Documentar o volume `-v ciframe-data:/app/db` em `README.md` e `AGENTS.md`;
  excluir `db/`/`*.db` de `.gitignore` e `.dockerignore`.
- Testes de matching, API, deduplicação, persistência e a regressão das 6 por
  conjunto + contagem; atualizar `baseline/README.md` para o novo critério.

**Fora do escopo (e por quê):**

- Migrar músicas/gêneros para o banco: restrição fixa do enunciado; o CSV
  continua sendo a fonte em memória.
- Paginação/contagem total na UI: o comportamento atual (máximo 100 resultados
  para os ids 0 e 1) permanece; paginar exige mudanças adicionais de contrato.
- Editar/excluir sequências, moderação, login, rate limit ou captcha: o
  catálogo é aberto e anônimo por requisito; abuso fica como risco conhecido.
- Normalização musical (enharmonia, sufixo, baixo invertido) e validação contra
  `/acordes`: mudaria os conjuntos de resultados e não é necessária para a
  regressão.
- Trocar a lista hardcoded de gêneros do frontend (`app.js:6-58`) por
  `/generos`: divergência pré-existente e independente desta feature.
- Suporte a múltiplos workers gunicorn, backup/restore do banco e alvo de
  deploy em nuvem: continuam indefinidos, como no ADR 0001.
- Trocar `json.dumps` por `jsonify` ou alterar `Content-Type`: é mudança de
  contrato, proibida pela restrição fixa.
