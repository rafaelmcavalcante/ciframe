# Pesquisa — Sequências de Acordes Customizadas

## Resumo

O matching de sequência não é calculado em tempo real hoje: `GET /similares?sequencia=...` remove as vírgulas da query (`main.py:191`), usa a string como chave do dict `sequencias` (`main.py:40-45`) e filtra músicas pela tag pré-computada `SEQ_FAMOSA` (`main.py:203-223`). O baseline real no container Docker é 199, 296, 4, 5, 7 e 3 músicas (514 no total), com página de no máximo 100 (`main.py:35`, `main.py:226-228`). O experimento `scripts/research_matching.py` mostra que nenhuma definição "natural" (contígua, com lacunas, contenção de conjuntos, ordem dos distintos) reproduz esse baseline; só a reprodução literal da regra que gerou a tag (`scripts/generate_data_set.py:7-24`) reproduz as 6 sequências, com 67.585/67.585 linhas de acordo. Essa regra exige a sequência contígua **e** que todo o vocabulário da música esteja contido no vocabulário da sequência. O frontend `#/porsequencia` mostra 4 sequências hardcoded em JS (`static/assets/js/controllers/sequencia.js:2-37`), correspondentes aos ids 0, 1, 4 e 5; os ids 2 (`Em,G`) e 3 (`C,A7,Dm,G7`) não aparecem. O DeepWiki confirmou o fluxo de `/similares`, as 6 sequências e a divergência 4 vs 6, mas errou ao afirmar que já existem SQLite, `POST /similares/cadastrar` e matching em tempo real; nada disso está no código local.

## 1. Algoritmo de matching

### 1.1 Caminho de `/similares?sequencia=...`

`get_similares` (`main.py:170-201`) testa `acordes` primeiro (`main.py:184-186`), depois `id_unico_musica` (`main.py:187-189`) e por último `sequencia` (`main.py:190-197`). No ramo de sequência, `sequencia_tag.replace(',', '')` remove apenas vírgulas (`main.py:191`); a string resultante precisa ser exatamente uma chave do dict `sequencias` (`main.py:40-45`):

| chave | id | acordes, na ordem |
|---|---:|---|
| `BmGDA` | 0 | Bm, G, D, A |
| `CGAmF` | 1 | C, G, Am, F |
| `EmG` | 2 | Em, G |
| `CA7DmG7` | 3 | C, A7, Dm, G7 |
| `GmF` | 4 | Gm, F |
| `CC7FFm` | 5 | C, C7, F, Fm |

Se a chave não existir, o endpoint devolve `json.dumps([])` imediatamente (`main.py:194-197`); não cai no matching por acordes. Se existir, `get_similares_por_sequencia` (`main.py:203-223`) filtra por gênero (`main.py:205`, `main.py:266-272`) e inclui a música quando `str(id_seq) in musica.seqs_famosas` (`main.py:209`). O retorno tem 9 campos (`main.py:210-220`) e não inclui `diferenca` nem `intersecao`.

### 1.2 Origem de `seqs_famosas`

No startup, `main.py` abre o CSV e descarta a primeira linha (`main.py:49-50`), depois remove aspas, remove toda ocorrência literal de `NA` e corta o último caractere antes de `split(',')` (`main.py:52-55`). A coluna `CIFRA` (índice 8) passa por `limpa_cifra` (`main.py:11-23`, `main.py:58-61`); `SEQ_FAMOSA` (índice 7) é dividida por `;` (`main.py:63`). `Musica` guarda `cifra` (lista ordenada, com repetições), `acordes = list(set(cifra))` (sem ordem e sem repetições) e `seqs_famosas` (`musica.py:16-18`).

O CSV não tem cabeçalho: a primeira linha é a música `14-bis,a-qualquer-tempo,...` (`data/top/dataset_final.csv:1`). Como `main.py:50` a trata como cabeçalho, 67.585 músicas entram em memória, não 67.586 (confirmado por `/musicas` e pela saída do script). Das 67.585, 514 têm tag: 199 com `0`, 296 com `1`, 4 com `2`, 5 com `3`, 7 com `4` e 3 com `5`.

A tag não é calculada pelo backend. O gerador está em `scripts/generate_data_set.py:7-24` e a regra efetiva é:

1. a sequência unida por `;`, em minúsculas, aparece como substring contígua da cifra também unida por `;` (`scripts/generate_data_set.py:12-13`);
2. todos os tokens de acorde da música pertencem ao conjunto de tokens da sequência (`scripts/generate_data_set.py:16-20`). O loop percorre `acorde.split(';')` (a música), não `tokens` (a sequência).

O item 2 explica os números baixos: não basta a música conter a progressão; ela não pode usar nenhum acorde fora dela. Exemplos reais: `30-seconds-to-mars_city-of-angels` tem tag `0` e vocabulário distinto `{D,A,Bm,G}`; `3-doors-down_every-time-you-go` contém `Bm,G,D,A` contíguo, mas usa `G6`, `D9`, `B9`, `C`, `A6` etc. e não tem tag `0`.

### 1.3 Ordem, repetição e normalização

- **Ordem**: a tag usa a string unida por `;`, então a ordem importa (`scripts/generate_data_set.py:13`). `musica.acordes` é um `set` (`musica.py:17`) e não serve para matching que dependa de ordem; a lista ordenada é `musica.cifra`.
- **Repetições**: a substring preserva repetições. `Em,G` exige `Em` imediatamente seguido de `G`; `Em,Em,G` só casa a partir do segundo `Em`.
- **Caixa**: a geração da tag faz `acorde.lower()` (`scripts/generate_data_set.py:12`), então o casamento é case-insensitive. O corpus tem 151 grupos de tokens que diferem só por caixa (ex.: `Am7`/`AM7`, `Eb`/`EB`, `F/G`/`F/g`); o script mede esses grupos em `scripts/research_matching.py:256-260`. Para as 6 sequências atuais, a comparação case-insensitive e a case-sensitive dão os mesmos totais (`scripts/research_matching.py:238-254`).
- **Variações de escrita**: não há normalização de enharmonia (`C#` vs `Db`), sufixo (`Bm` vs `Bm7`) nem baixo invertido (`A` vs `A/C#`) em `main.py`; a comparação é por token exato (a menos de caixa). Os scripts offline `scripts/normalize_chords.R` e `scripts/simplify_chords.R` existem, mas `main.py` não os usa.
- **Fronteira de token**: o teste é substring na string unida, não comparação de tokens. Na prática, a checagem de vocabulário elimina casamentos parciais; sem ela, `em;g` poderia casar dentro de `em;g7`.
- **Parsing textual**: `limpa_cifra` separa por `;` e depois por espaços, e em tokens com `|` pega o primeiro pedaço (`main.py:11-23`). Isso produz tokens que não são acordes (exemplos medidos: `2x`, `)`, `:`, `#m`), que entram no vocabulário e podem afetar a regra de vocabulário contido.

## 2. Validação contra os dados reais

### 2.1 Baseline

Ambiente: `docker build -t ciframe .` e `docker run -d --name ciframe-baseline -p 8080:8080 ciframe`; commit `fb97001`; CSV com sha256 `5f94f49b945ffac76f9a114b353b51d6a07b9e6feeb1243ce5989295234b9207`. `/generos` respondeu 200 com array JSON. As páginas foram salvas em `/tmp/opencode/baseline/<id>_<chave>/pagina_<n>.json`, com resumo em `/tmp/opencode/baseline/summary.json`.

| seq | query | página 1 | página 2 | página 3 | total | tags no CSV |
|---|---|---:|---:|---:|---:|---:|
| 0 | `Bm,G,D,A` | 100 | 99 | 0 | **199** | 199 |
| 1 | `C,G,Am,F` | 100 | 100 | 96 | **296** | 296 |
| 2 | `Em,G` | 4 | 0 | — | **4** | 4 |
| 3 | `C,A7,Dm,G7` | 5 | 0 | — | **5** | 5 |
| 4 | `Gm,F` | 7 | 0 | — | **7** | 7 |
| 5 | `C,C7,F,Fm` | 3 | 0 | — | **3** | 3 |
| | | | | | **514** | **514** |

A página 1 é limitada por `TAM_PAGINA = 100` (`main.py:35`) e `get_pagina` (`main.py:226-228`). O frontend de sequência não envia `pagina` (`static/assets/js/controllers/sequencia.js:72-77`), então a UI recebe no máximo 100 resultados para os ids 0 e 1. Sondagens de borda: `sequencia=BmGDA` (sem vírgulas) devolve 100 na página 1; `sequencia=bm,g,d,a` devolve `[]` (chave case-sensitive); `sequencia=Bm, G, D, A` devolve `[]` (o `replace` não remove espaços, `main.py:191`).

### 2.2 Experimento

`scripts/research_matching.py` (somente stdlib) reproduz `limpa_cifra` (`scripts/research_matching.py:55-66`), o parsing de `main.py:49-63` (`scripts/research_matching.py:68-103`) e as 6 sequências (`scripts/research_matching.py:33-41`). O ground truth é o conjunto de músicas cuja tag CSV contém o id. Foram comparadas cinco definições (`scripts/research_matching.py:43-54`, `scripts/research_matching.py:104-158`):

| nome | definição operacional |
|---|---|
| `a_contiguous_ordered` | a sequência é uma fatia contígua de `cifra`, preservando ordem e repetições |
| `b_ordered_gapped` | a sequência é uma subsequência ordenada de `cifra`, com lacunas |
| `c_set_containment` | todo acorde distinto da sequência aparece em `cifra`, ignorando ordem e repetições |
| `d_distinct_relative_order` | remove repetições mantendo a primeira ocorrência; a sequência é subsequência dessa lista |
| `e_legacy_tag_rule` | reprodução literal de `scripts/generate_data_set.py:7-24`: substring contígua + vocabulário da música contido no da sequência |

Comando: `python3 scripts/research_matching.py --baseline /tmp/opencode/baseline --json-out /tmp/opencode/research_matching.json`. Resultado: 67.585 linhas carregadas, 0 malformadas, 514 com tag e **67.585/67.585 linhas com o conjunto de tags previsto por `e` igual ao do CSV** (`scripts/research_matching.py:227-235`, `scripts/research_matching.py:270-272`).

| definição | TP | FP | FN | precisão | recall | sequências com conjunto exato |
|---|---:|---:|---:|---:|---:|---:|
| `a_contiguous_ordered` | 514 | 5.945 | 0 | 0,0796 | 1,0000 | 0/6 |
| `b_ordered_gapped` | 514 | 28.127 | 0 | 0,0179 | 1,0000 | 0/6 |
| `c_set_containment` | 514 | 31.102 | 0 | 0,0163 | 1,0000 | 0/6 |
| `d_distinct_relative_order` | 213 | 6.859 | 301 | 0,0301 | 0,4144 | 0/6 |
| `e_legacy_tag_rule` | 514 | 0 | 0 | 1,0000 | 1,0000 | **6/6** |

Contagens por sequência (actual / previsto):

| seq | actual | a | b | c | d | e |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 199 | 866 | 4.763 | 5.768 | 322 | **199** |
| 1 | 296 | 1.216 | 5.887 | 6.894 | 687 | **296** |
| 2 | 4 | 3.110 | 13.643 | 14.160 | 4.332 | **4** |
| 3 | 5 | 96 | 427 | 582 | 97 | **5** |
| 4 | 7 | 1.039 | 3.641 | 3.847 | 1.521 | **7** |
| 5 | 3 | 132 | 280 | 365 | 113 | **3** |

**Somente `e_legacy_tag_rule` reproduz o baseline**, tanto em contagem quanto em conjunto de ids; os conjuntos de `e` são idênticos aos ids do baseline vivo e às tags do CSV para os 6 ids (`scripts/research_matching.py:174-191`, `scripts/research_matching.py:296-307`). As definições (a), (b) e (c) têm recall 1,0 (toda música com tag satisfaz a definição), mas produzem muitos falsos positivos. A definição (d) perde 301 positivos: uma ocorrência contígua posterior não garante que a primeira ocorrência de cada acorde respeite a ordem da sequência. Exemplo: `30-seconds-to-mars_city-of-angels` tem tag `0`, mas a ordem de primeira ocorrência dos distintos é `D,A,Bm,G`, então `d` gera falso negativo.

## 3. Banco de dados

### 3.1 Estado atual

Não há banco de dados. As 6 sequências são um dict literal (`main.py:40-45`); músicas e gêneros vêm do CSV em memória (`main.py:49-98`). Não há rota de escrita: as rotas de `main.py` são `GET` (`main.py:101-201`). `requirements.txt:4-5` lista apenas `Flask==3.1.3` e `gunicorn==23.0.0`; não há import de `sqlite3`, `shelve`, `tinydb`, SQLAlchemy ou driver Postgres no app. `AGENTS.md:9-11` registra "no database". O `Dockerfile` é único e local-only (`Dockerfile:1-12`), com `COPY . .` (`Dockerfile:8`), `EXPOSE 8080` (`Dockerfile:10`) e `CMD ["gunicorn", ...]` (`Dockerfile:12`); não há `VOLUME`. O ADR `docs/adr/0001-local-only-docker-deploy.md:9-12` registra container único e backend em memória.

### 3.2 Fatos verificados no container

- Python 3.9; `sqlite3` 3.46.1 disponível na stdlib; `shelve` importa; `tinydb` não está instalado (`ModuleNotFoundError`); `postgres`, `psql`, `pg_ctl`, `psycopg` e `psycopg2` não existem na imagem.
- Um arquivo criado em `/app` sobreviveu a `docker restart` no mesmo container; um arquivo criado no container antigo não apareceu em um novo `docker run --rm ... ciframe`, porque o novo container parte da imagem, não da camada gravável anterior.
- Um bind mount (`-v /tmp/opencode/ciframe-data:/data`) preservou o SQLite entre `docker rm` e um novo `docker run`.
- `docker inspect ciframe` mostrou `Volumes=null`; o comando documentado em `README.md:15-18` e `AGENTS.md:22-25` não passa `-v`.
- `.dockerignore:1-4` exclui apenas `.git`, `.venv`, `__pycache__` e `*.pyc`; `.gitignore:1-4` não tem padrão de banco. Como o `Dockerfile:8` faz `COPY . .`, um arquivo de banco presente no contexto de build seria copiado para a imagem.

### 3.3 Opções e implicações

| opção | dependência / mudança no `Dockerfile` | `docker restart` | `docker rm` + novo `docker run` | observações |
|---|---|---|---|---|
| **SQLite** (`sqlite3` stdlib) | nenhuma dependência nova; `requirements.txt`/`Dockerfile` não precisam mudar para abrir o arquivo | sim, se o arquivo estiver em `/app` (camada gravável) | não, sem volume/bind mount | arquivo único, SQL, `UNIQUE`, transações; um escritor por vez; com o `CMD` atual o gunicorn usa 1 worker (`Dockerfile:12`) |
| **TinyDB** | `tinydb` não está instalado; exigiria adicionar ao `requirements.txt` e rebuildar (o `Dockerfile:6` instala as dependências) | sim, se o JSON estiver em `/app` | não, sem volume | dependência Python adicional; armazenamento em arquivo; sem processo de servidor |
| **shelve** (stdlib) | nenhuma dependência nova | sim, se o arquivo estiver em `/app` | não, sem volume | chave-valor com pickle; cria um ou mais arquivos conforme o backend `dbm`; sem schema/consulta |
| **Postgres** | não está na imagem; exigiria instalar servidor + driver, inicializar data dir e iniciar o processo | sim, com volume do data dir | sim, com volume nomeado | é um servidor, não uma biblioteca embarcada; no container único precisaria rodar junto do gunicorn (o `CMD` atual só inicia gunicorn); como serviço separado, contraria o container único de `docs/adr/0001-local-only-docker-deploy.md:9-12` |

O ponto central da persistência é o que "reiniciar" significa:

- `docker restart` no mesmo container preserva a camada gravável; um arquivo em `/app` sobrevive.
- `docker rm`/`docker run` novo, `docker build` novo ou outro host perdem a camada gravável; só bind mount (`-v /host/path:/app/data`) ou volume nomeado (`-v ciframe-data:/app/data`) preserva.
- `VOLUME` no `Dockerfile` cria volume anônimo; por si só não garante reutilização entre recriações. O `Dockerfile` atual não declara `VOLUME`.

## 4. Frontend `#/porsequencia`

### 4.1 Rota, controller e template

A rota `#/porsequencia` é declarada em `static/assets/js/routes.js:17-21` e aponta para `templates/sequencia.html` com `SequenciaController` e `controllerAs: "Sequencia"`. O controller está em `static/assets/js/controllers/sequencia.js`; o template em `static/templates/sequencia.html`; o script é carregado em `static/index.html:145`, junto com AngularJS 1.4.9 e jQuery por CDN (`static/index.html:125-134`), sem build step. O link de entrada está em `static/templates/home.html:79`.

### 4.2 As 4 sequências hardcoded

`sequencia.js:2-31` define quatro objetos e `sequencia.js:32-37` os empilha em `vm.sequenciasFamosas`:

| variável JS | acordes | chave no backend | id |
|---|---|---|---|
| `sequencia1` | Bm, G, D, A | `BmGDA` | 0 |
| `sequencia2` | C, G, Am, F | `CGAmF` | 1 |
| `sequencia3` | Gm, F | `GmF` | 4 |
| `sequencia4` | C, C7, F, Fm | `CC7FFm` | 5 |

O frontend cobre os ids **0, 1, 4 e 5**; ficam de fora `Em,G` (id 2) e `C,A7,Dm,G7` (id 3). A terceira sequência da tela é a de id 4, não a de id 2. A divergência é pré-existente e está descrita em `docs/features/sequencias-customizadas/00-enunciado.md:26-31`; o backend tem 6 chaves (`main.py:40-45`), o controller tem 4 literais (`sequencia.js:2-37`).

### 4.3 O que a página faz

1. Renderiza as 4 sequências como hexágonos clicáveis (`static/templates/sequencia.html:5-8`), usando a diretiva `df-hex` (`static/assets/js/directives/df-hex.js:1-12`, `static/templates/directives/df-hex.html:1-9`).
2. Ao clicar, `pesquisarPorSequencia(sequencia)` copia o objeto para `vm.minhaSequencia` e monta a URL (`sequencia.js:63-77`).
3. `createChordsString` junta os acordes com vírgula, sem espaço (`sequencia.js:55-61`); a URL fica `similares?sequencia=<acordes>` e, se `vm.meuGenero` estiver preenchido, acrescenta `&generos=<genero>` (`sequencia.js:72-76`). Não há `pagina`.
4. `$http.get(...)` (`sequencia.js:77`); no sucesso, `vm.musics = data` (`sequencia.js:83`); no erro, mostra "Ops! Algo errado." (`sequencia.js:85-89`).
5. O select de gênero (`sequencia.html:24-30`) chama `pesquisarPorSequencia()` sem argumento; o controller usa o `vm.minhaSequencia` já selecionado (`sequencia.js:63-66`).
6. Os resultados são cards com título, artista e gênero (`sequencia.html:40-58`); clicar no card abre `music.url` em nova janela (`sequencia.js:97-99`). Clicar em um hexágono do painel de resultados chama `limparPesquisa()` (`sequencia.html:34`, `sequencia.js:92-95`).
7. O botão "Encontrei essas músicas" (`sequencia.html:10-14`) rola até `#results` (`sequencia.js:101-104`).

### 4.4 O que a página não faz

- Não busca o catálogo no backend: as 4 sequências são literais JS (`sequencia.js:2-37`); não há `$http.get` para `/sequencias` ou equivalente.
- Não tem campo de texto, seletor de acordes ou formulário para montar uma sequência nova. O único input é o select de gênero (`sequencia.html:24-30`).
- Não faz `POST` para lugar nenhum; a única chamada é o `GET` de `sequencia.js:77`.
- Não mostra as 6 sequências do backend; não há indicação na tela de que existem os ids 2 e 3.
- Não pagina: como não envia `pagina`, recebe a página 1 (até 100 resultados) e não tem controle de próxima página (`main.py:176`, `main.py:196`, `main.py:226-228`).
- O filtro `ng-hide="music.diferenca.length"` (`sequencia.html:43`) foi escrito para resultados de busca por acordes, que têm `diferenca` (`main.py:246-258`); a resposta de `/similares?sequencia=` não tem `diferenca` (`main.py:210-220`), então a expressão é `undefined` e o filtro não esconde nada.
- O constant `RESTAPI` em `static/assets/js/app.js:3-5` aponta para `http://localhost:5003`, mas o controller de sequência usa `apiUrl = ""` (`sequencia.js:72`), ou seja, URL relativa à origem.
- A lista de gêneros do select também é hardcoded no JS (`static/assets/js/app.js:6-58`, 51 gêneros), não vem de `/generos` (`main.py:158-160`).

### 4.5 Por que 4 != 6

O backend tem 6 entradas no dict `sequencias` (`main.py:40-45`) e o CSV tem tags para esses 6 ids. O controller tem apenas 4 objetos literais (`sequencia.js:2-37`), escolhidos manualmente; não há chamada que leia o dict do backend. Por isso a tela mostra 4, e os ids 2 (`Em,G`) e 3 (`C,A7,Dm,G7`) só são acessíveis por URL manual (`/similares?sequencia=Em,G` ou `...=C,A7,Dm,G7`).

## 5. DeepWiki: hipótese vs código local

Consulta ao MCP `deepwiki` para `joaoarthurbm/ciframe`. A primeira resposta afirmou que a feature já existe com SQLite, `POST /similares/cadastrar` e matching em tempo real. Quando confrontado a citar arquivo e linha, recuou e disse que SQLite e o endpoint estão "descritos na documentação", mas não implementados; ainda assim afirmou que o ADR 0002 documenta SQLite.

| afirmação do DeepWiki | código local | evidência |
|---|---|---|
| "o projeto tem SQLite para sequências customizadas" | não existe banco; as sequências são dict literal | `main.py:40-45`; `requirements.txt:4-5`; nenhum import de `sqlite3` no app |
| "existe `POST /similares/cadastrar`" | não existe; a rota não está registrada | `POST /similares/cadastrar` → 405; `GET` → 404; rotas em `main.py:101-201` |
| "matching customizado é calculado em tempo real em `musica.acordes`" | não existe esse caminho; só lookup de tag | `main.py:203-223`; não há função de matching de sequência em `main.py` |
| "`#/porsequencia` permite cadastrar sequência" | a página só lista 4 hardcoded e faz GET | `sequencia.js:2-90`; `sequencia.html:1-63` |
| "ADR 0002 documenta a decisão de usar SQLite" | o ADR 0002 local é template não preenchido | `docs/adr/0002-persist-custom-sequences.md:1-8` |
| "6 sequências, `SEQ_FAMOSA`, frontend com 4 hardcoded" | correto | `main.py:40-45`, `main.py:63`, `main.py:203-223`, `sequencia.js:2-37` |

As respostas do DeepWiki refletem o enunciado/templates e uma wiki da feature planejada, não o código. Servem como hipótese, não como evidência.

## Trade-offs identificados

### Algoritmo de matching

| definição | ordem | adjacência | repetições | reproduz o baseline? | prós | contras |
|---|---|---|---|---|---|---|
| (a) contígua e ordenada | sim | sim | sim | não (0/6; 5.945 FP) | intuitiva para "progressão"; usa `cifra` ordenada; recall 1,0 | muito mais permissiva que a tag; música com acordes extras continua casando; precisão baixa |
| (b) ordenada com lacunas | sim | não | sim | não (0/6; 28.127 FP) | aceita acordes entre a progressão; recall máximo | quase qualquer música que use os acordes na ordem casa |
| (c) contenção de conjuntos | não | não | não | não (0/6; 31.102 FP) | simples; usa `musica.acordes` sem ordem | ignora a noção de sequência; precisão mínima |
| (d) ordem relativa dos distintos | sim, por primeira ocorrência | não | não | não (0/6; 301 FN) | ignora repetições e permite lacunas | falsos negativos quando um acorde aparece antes fora de ordem |
| (e) regra literal da tag | sim | sim | sim | **sim (6/6; 0 FP, 0 FN)** | reproduz exatamente o baseline; mantém regressão | exige que a música inteira use só acordes da sequência; para sequências novas tende a devolver poucos resultados |

Sub-decisões de normalização expostas pelo experimento:

| decisão | situação atual | efeito observado | trade-off |
|---|---|---|---|
| caixa | tag gerada com `lower()` (`scripts/generate_data_set.py:12`) | 0 diferença nas 6 sequências; 151 grupos ambíguos no corpus | case-insensitive reproduz a tag, mas funde `Am7`/`AM7`, `Eb`/`EB` etc.; case-sensitive preserva a grafia, mas divergiria da tag |
| enharmonia (`C#`/`Db`) | não normaliza | não afeta as 6 sequências | normalizar aumentaria matches, mas mudaria o conjunto e exigiria regra de equivalência |
| sufixo (`Bm`/`Bm7`) | não normaliza | `Bm7` não casa com `Bm` | normalizar aumentaria recall, mas confundiria acordes diferentes |
| baixo invertido (`A`/`A/C#`) | não normaliza | `A/C#` não casa com `A` | idem |
| repetições | (a)/(b) preservam; (c)/(d) ignoram | as 6 sequências não têm acorde repetido, então o baseline não restringe essa escolha | preservar é mais fiel a "sequência"; ignorar é mais tolerante |
| fonte de dados | `cifra` (ordenada) vs `acordes` (set) | ordem só existe em `cifra` (`musica.py:16-17`) | usar `acordes` só permite (c); usar `cifra` permite (a), (b) e (d) |
| múltiplas sequências por música | o gerador concatena ids sem separador (`scripts/generate_data_set.py:88`) | nenhuma linha atual tem mais de uma tag | um matcher em tempo real pode precisar representar mais de uma sequência; o formato atual não representa isso |

### Banco de dados

| critério | SQLite | TinyDB | shelve | Postgres |
|---|---|---|---|---|
| dependência | stdlib `sqlite3` (3.46.1 no container) | pacote externo, não instalado hoje | stdlib | driver + servidor |
| mudança no `Dockerfile`/`requirements.txt` | nenhuma para usar; volume é decisão de execução | `requirements.txt` + rebuild | nenhuma | instalar servidor/driver, inicializar e iniciar processo |
| `docker restart` | sim, arquivo em `/app` | sim, JSON em `/app` | sim, arquivo(s) em `/app` | sim, com volume do data dir |
| `docker rm` + novo `docker run` | não, sem `-v`/volume nomeado | não, sem volume | não, sem volume | sim, com volume nomeado |
| concorrência | um escritor por vez; 1 worker no `CMD` atual | escrita do arquivo inteiro | depende do backend `dbm` | robusta |
| schema/validação | SQL, `UNIQUE`, `NOT NULL`, transações | validação no código | nenhuma | SQL completo |
| aderência ao container único | alta | alta | alta | baixa se virar serviço separado |

Opções de persistência no Docker, com o `Dockerfile` atual:

- **Sem volume** (comando atual de `README.md:15-18`/`AGENTS.md:22-25`): o dado vive na camada gravável. `docker restart` preserva; `docker rm`/novo `docker run`/novo build perdem.
- **Bind mount** (`-v /host/path:/app/data`): persiste entre recriações; depende de caminho e permissões do host; o processo roda como root no container.
- **Volume nomeado** (`-v ciframe-data:/app/data`): persiste entre recriações; gerenciado pelo Docker; precisa ser documentado no comando de execução.
- **`VOLUME` no `Dockerfile`**: cria volume anônimo; por si só não garante reutilização entre recriações.
- **Postgres como segundo container**: exigiria rede/compose e contraria `docs/features/sequencias-customizadas/00-enunciado.md:63-65` e `docs/adr/0001-local-only-docker-deploy.md:9-12`.

### Frontend

| decisão | opções | prós | contras |
|---|---|---|---|
| fonte do catálogo | manter as 4 hardcoded | nenhuma chamada extra; comportamento atual preservado | continua divergindo das 6 do backend; não reflete cadastros |
| | buscar o catálogo no backend | uma fonte de verdade; reflete sequências novas | exige rota GET nova, estados de loading/erro e mudança no controller/template; o backend atual não tem essa rota |
| | híbrido (fallback hardcoded + fetch) | funciona se o backend falhar | mais código; fallback pode ficar stale e reintroduzir a divergência 4 vs 6 |
| entrada de sequência | texto livre de acordes separados por vírgula | simples; usa o mesmo formato da query | precisa validar tokens, duplicatas, vazio, maiúsculas e acordes desconhecidos |
| | seletor visual de acordes (hexágonos) | reutiliza `df-hex` e a UI existente | mais código e estado; a lista de acordes teria que vir de `/acordes` (`main.py:162-164`) ou de outra fonte |
| cadastro | formulário na própria `#/porsequencia` | mantém o fluxo na mesma página | precisa de POST, tratamento de erro e atualização da lista |
| | página/rota separada | separa busca de cadastro | mais uma rota e template; foge do escopo visual atual |
| duplicatas | rejeitar, ignorar ou atualizar | regra explícita e testável | cada escolha muda o contrato da API e a mensagem na UI |
| paginação | não paginar (estado atual) | menos código | ids 0 e 1 já retornam 100 de 199/296; a UI nunca mostra o total |
| | paginar | mostra todos os resultados | exige controle de página no frontend e parâmetro `pagina` no GET |

Restrições existentes que afetam qualquer mudança de frontend: AngularJS 1.4.9 + jQuery por CDN, sem build step (`static/index.html:125-147`); template e controller são carregados diretamente; não há suíte de testes no repositório; a lista de gêneros do select é hardcoded em `static/assets/js/app.js:6-58`; e a resposta de sequência não tem `diferenca`, então o `ng-hide` de `static/templates/sequencia.html:43` não filtra nada nesse fluxo.
