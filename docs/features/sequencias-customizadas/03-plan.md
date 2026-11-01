# Plano — Sequências de Acordes Customizadas

## Escopo, restrições e premissas

**Base:** `02-proposal.md` (abordagem escolhida), `docs/adr/0002-persist-custom-sequences.md`
(decisões fechadas) e `01-research.md` (evidências). Nenhuma decisão desses
documentos é reaberta aqui.

**Dentro do escopo:** catálogo de sequências em SQLite; matching único calculado
sobre `musica.cifra`; `GET/POST /sequencias`; lookup compatível com
`?sequencia=Bm,G,D,A` e `?sequencia=BmGDA`; frontend `#/porsequencia` lendo o
catálogo e cadastrando; gêneros em ordem alfabética; volume `db/` documentado e
ignorado no Git/Docker; verificação manual das 6 sequências e da feature nova.

**Fora do escopo:** migrar músicas/gêneros para o banco; paginação nova;
editar/excluir sequências; login, moderação, rate limit ou captcha; normalização
musical (enharmonia, sufixo, baixo invertido); trocar `json.dumps` por
`jsonify`; suportar múltiplos workers; backup/restore; nuvem.

**Restrições que valem para todos os passos:**

- Nenhuma dependência nova: `sqlite3` da stdlib; `requirements.txt` não muda.
- Todo endpoint continua devolvendo `json.dumps(...)` (string, sem `jsonify`),
  com `Content-Type: text/html` e `Access-Control-Allow-Origin: *`.
- Músicas e gêneros continuam vindo de `data/top/dataset_final.csv` em memória.
- Um único processo gunicorn (`Dockerfile:12`), sem `--threads` explícito; o mapa
  em memória pode assumir um worker.
- O frontend continua AngularJS 1.4.9 + jQuery por CDN, sem build step.

**Ordem e prazos:** não há data limite registrada no repositório. O
sequenciamento abaixo é por dependência e cada passo termina em um gate
verificável:

| Fase | Passos | Depende de | Gate |
|---|---|---|---|
| Persistência | 1 | — | banco criado, seeds 0–5, mapa carregado |
| Matching | 2 | 1 | conferência de startup bate com a tag |
| Ordem | 3 | 2 | `/generos` ordenado; ordem estável entre processos |
| API | 4 | 1–3 | matriz 201/400/409, lookup duplo e dict antigo removido |
| Frontend | 5 | 4 | cadastro e busca pela UI |
| Infra/docs | 6 | 4 (paralelo com 5) | volume e ignores verificados |
| Regressão | 7 | 1–6 | 6 sequências por conjunto + 514 |

Se a implementação mudar alguma decisão, este arquivo é atualizado **antes** de
continuar.

## Passos

### 1. Persistência SQLite, seed e catálogo em memória

**Arquivos:** `sequencias_db.py` (novo), `main.py`.

- [x] Criar `sequencias_db.py` com `sqlite3` apenas. Resolver o caminho nesta
  ordem: `CIFRAME_DB` (caminho completo do arquivo, se definido) →
  `/app/db/sequencias.db` quando `/app` existir → `./db/sequencias.db` no
  ambiente local. Criar o diretório com `os.makedirs(..., exist_ok=True)` antes
  de abrir; erro de permissão deve derrubar o startup com a mensagem e o caminho.
- [x] `init_db()` idempotente: abrir conexão, `PRAGMA busy_timeout=5000`, criar a
  tabela se não existir, rodar os seeds e ajustar `PRAGMA user_version`.
  Se `user_version > 1` (banco de uma versão futura), abortar o startup em vez de
  escrever; se `0`, criar e gravar `1`; se `1`, apenas validar a tabela.
- [x] Esquema único, sem tabela de matches:

```sql
CREATE TABLE IF NOT EXISTS sequences (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  acordes      TEXT NOT NULL,          -- JSON array, na ordem cadastrada
  chave        TEXT NOT NULL UNIQUE,   -- lower(','.join(acordes))
  chave_legado TEXT NOT NULL UNIQUE,   -- lower(''.join(acordes))
  criado_em    TEXT NOT NULL           -- UTC, ISO-8601
);
```

- [x] Seed com ids explícitos e `INSERT OR IGNORE` (pode rodar em todo startup;
  é barato e não duplica):

| id | `acordes` | `chave` | `chave_legado` |
|---:|---|---|---|
| 0 | `["Bm","G","D","A"]` | `bm,g,d,a` | `bmgda` |
| 1 | `["C","G","Am","F"]` | `c,g,am,f` | `cgamf` |
| 2 | `["Em","G"]` | `em,g` | `emg` |
| 3 | `["C","A7","Dm","G7"]` | `c,a7,dm,g7` | `ca7dmg7` |
| 4 | `["Gm","F"]` | `gm,f` | `gmf` |
| 5 | `["C","C7","F","Fm"]` | `c,c7,f,fm` | `cc7ffm` |

`criado_em` dos seeds é gerado em UTC no primeiro `INSERT`; como as linhas já
existem, o valor não muda depois. Próximo id livre: 6.
- [x] Manter o dict `sequencias` de `main.py:40-45` **intacto neste passo**: ele
  ainda é o lookup de `/similares?sequencia=...` (`main.py:194-195`). As mesmas
  seis listas viram a constante de seeds do módulo novo. A remoção do dict e do
  lookup acontece no passo 4, quando o catálogo assume a busca; removê-lo agora
  deixaria o endpoint quebrado (`NameError`) entre os passos 1 e 4.
- [x] `carregar_catalogo()` lê todas as linhas e devolve três mapas em memória:
  `chave → id`, `chave_legado → id` e `id → {acordes, criado_em}`. Carregar uma
  vez no startup de `main.py`, depois do CSV (para o log sair na ordem certa) e
  antes de servir qualquer rota.
- [x] `inserir_sequencia(acordes)` abre conexão por operação (sem conexão
  compartilhada entre threads), grava com placeholders, faz commit e devolve
  `id`/`criado_em`. Capturar `sqlite3.IntegrityError` e relançar uma exceção de
  duplicidade com o id existente.
- [x] No `POST`, atualizar os três mapas **somente depois** do commit. Usar
  `is not None` nas buscas por id: o id 0 é válido e não pode ser confundido com
  “não encontrado” (`or`/truthiness é proibido nesses lookups).
- [x] Log de startup: caminho do banco, `user_version`, total de linhas e
  tamanho do catálogo. Falha ao abrir/criar o banco encerra o processo (fail
  fast), em vez de subir uma API sem catálogo.

**Verificação:** iniciar com `CIFRAME_DB=/tmp/opencode/seq.db python main.py`,
duas vezes seguidas, e conferir que a segunda execução não duplica nada:

```bash
python3 - <<'PY'
import sqlite3
c = sqlite3.connect('/tmp/opencode/seq.db')
print('user_version:', c.execute('PRAGMA user_version').fetchone()[0])
for r in c.execute('SELECT id, acordes, chave, chave_legado FROM sequences ORDER BY id'):
    print(r)
PY
```

Esperado: `user_version: 1` e exatamente 6 linhas, ids 0–5, com as chaves da
tabela acima. O app continua no ar com o comportamento antigo: as 6 sequências
respondem igual porque o dict de `main.py` e o caminho da tag seguem no lugar
(`curl -s 'localhost:5000/similares?sequencia=BmGDA'` devolve o mesmo conjunto de
antes). O endpoint `GET /sequencias` só nasce no passo 4.

### 2. Matching único sobre `musica.cifra`

**Arquivos:** `matching.py` (novo), `musica.py`, `main.py`.

- [x] Em `Musica.__init__` (`musica.py:16-18`), derivar uma vez:
  `self.cifra_lower = [sys.intern(t.lower()) for t in cifra]` e
  `self.vocabulario = frozenset(self.cifra_lower)`. Manter `self.cifra` e
  `self.acordes` intactos: `acordes` continua sendo o `set` devolvido pela API e
  usado na busca por acordes. O `sys.intern` é obrigatório: sem ele, as strings
  minúsculas duplicam um objeto por token e o RSS sobe de 233 MB para 474 MB
  (+241 MB), acima do limite de ~100 MB; com ele fica em 313 MB (+80 MB), com
  startup de 1,51 s contra 1,06 s do commit anterior (medido com `import main`,
  uma passada de CSV).
- [x] Em `matching.py`, implementar a regra única:
  `casa_sequencia(cifra_lower, vocabulario, alvo_lower) -> bool`.
  Retornar `False` para alvo vazio. Primeiro podar por vocabulário
  (`vocabulario.issubset(set(alvo_lower))`); só então procurar a fatia contígua
  preservando ordem e repetições (`tuple(cifra_lower[i:i+k]) == tuple(alvo_lower)`).
  Comparação sempre em minúsculas; sem enharmonia, sufixo ou baixo invertido.
  Não usar `musica.acordes` (set, sem ordem) para o match.
- [x] Em `main.py:196`, trocar a chamada para passar a lista de acordes do
  catálogo, e em `get_similares_por_sequencia` substituir o teste
  `str(id_seq) in musica.seqs_famosas` (`main.py:209`) por
  `casa_sequencia(musica.cifra_lower, musica.vocabulario, alvo_lower)`.
  `alvo_lower` vem de `seq_por_id[id_seq]['acordes']`, calculado uma vez por
  requisição (não por música).
- [x] No startup, após carregar o catálogo e o CSV, rodar a conferência única:
  para cada id 0–5, comparar `{m.id_unico_musica | casa_sequencia(...)}` com
  `{m.id_unico_musica | str(id) in m.seqs_famosas}`; logar
  `conferencia seq=<id> calculado=<n> tag=<n> igual=<bool>`. Divergência vira
  `warning` e bloqueia o passo 7; não derruba o processo (o app continua
  servindo, mas a regressão é obrigatória).
- [x] `Musica.para_dict()` devolve uma cópia do `__dict__` sem `cifra_lower`
  e `vocabulario`; `/musicas` e `/musica/<id>/` usam esse método para manter os
  12 campos historicos e nao tentar serializar o `frozenset`. Sem isso, o gate
  do passo 7 encontrou `GET /musica/<id>/` com 500 (`TypeError: frozenset is
  not JSON serializable`) e `/musicas` teria o mesmo erro.
- [x] **Decisão — `Musica.seqs_famosas`:** manter o parsing da tag **apenas como
  conferência de startup** nesta entrega; nenhum request passa a usá-lo.
  - Custo de manter: uma lista por música (67.585 listas pequenas, alguns MB),
    `main.py:63` + `musica.py:18` + o argumento do construtor continuam
    existindo, e a conferência custa uma passada extra no startup (ordem de
    ~0,1–0,4 s). Custo por requisição: zero.
  - Custo de remover já: some a lista, o parsing e o argumento do construtor,
    mas também some o tripwire que denuncia divergência entre o matcher e a tag
    a cada boot; um bug do matcher só apareceria na verificação manual do passo
    7. O diff também mexe no parsing do CSV na mesma entrega que muda o
    matching, dificultando isolar a causa de uma regressão.
  - **Ponto exato de remoção (follow-up, fora desta entrega):** depois que o
    passo 7 passar e a fase de testes cobrir o matcher, remover
    `musica[SEQ_FAMOSA] = musica[SEQ_FAMOSA].split(";")` (`main.py:63`),
    `self.seqs_famosas = seqs_famosas` (`musica.py:18`) e o parâmetro
    correspondente em `main.py:71`; reexecutar a regressão por conjunto.
- [x] Custo medido esperado: ~407 ms de normalização no startup para 67.585
  linhas e ~17 ms por busca de 4 acordes; o filtro de vocabulário poda antes da
  adjacência. Se o startup regredir muito, medir antes de mudar a estratégia.

**Verificação:** no log de startup, as 6 linhas `conferencia` devem sair com
`igual=True` e contagens `199, 296, 4, 5, 7, 3`. Em paralelo, consultar as 6
sequências (a captura completa por conjunto é o passo 7) e confirmar que uma
sequência sem tag no CSV, mas que satisfaça a regra, também é encontrada. Essa
conferência é feita por script direto sobre o CSV com `casa_sequencia` (por
exemplo `Am,F,C,G`, que não é seed nem tem tag): o endpoint
`?sequencia=Am,F,C,G` só passa a responder no passo 4, quando o lookup do
`/similares` deixa de usar o dict antigo, que reconhece apenas as 6 chaves.

Medir também o custo em memória: `cifra_lower` e `vocabulario` criam uma lista e
um `frozenset` por música (67.585 de cada). Antes de aceitar o passo, comparar o
RSS do processo depois do startup com o do commit anterior:

```bash
docker run --rm --entrypoint /bin/sh ciframe-candidate -c \
  'python -c "import main, resource; print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss//1024, \"MB\")"'
```

Se o crescimento passar de ~100 MB ou se o startup somar mais de ~1 s, registrar
a medição como trade-off aceito e considerar guardar só o vocabulário (sem a
lista `cifra_lower` por música) ou reconstruir a lista sob demanda. A decisão
fica registrada aqui antes de seguir. Medição desta entrega (mesma máquina,
`import main`): 233 MB → 313 MB (+80 MB) e 1,06 s → 1,51 s com `sys.intern`;
abaixo dos limites, então a estratégia lista + frozenset foi mantida.

### 3. Ordem determinística dos gêneros

**Arquivos:** `main.py`.

- [x] Trocar `generos = list(generos)` (`main.py:92`) por
  `generos = sorted(generos)`. Nenhuma outra mudança de ordenação.
- [x] Efeitos observáveis (quando a requisição passa `generos=`, a ordem já era
  a da query e não muda; a mudança vale para o caso sem filtro, que é o default):

| Endpoint | O que muda | O que não muda |
|---|---|---|
| `GET /generos` | array em ordem alfabética | 52 gêneros |
| `GET /search` | ordem das músicas (gênero alfabético + popularidade dentro do gênero) | conjunto, contagem e paginação |
| `GET /similares?sequencia=` | ordem e, portanto, **quais** ids caem na página 1 | conjunto total, contagens e página de 100 |
| `GET /similares?acordes=` / `?id_unico_musica=` | desempate estável por gênero alfabético | conjunto, contagem e ordenação por diferença/interseção |
| `GET /musicas` | nada (ordem por popularidade) | — |
| `GET /acordes` | nada; continua `list(set)` não determinístico, fora do escopo | — |

- [x] Documentar no PR/descrição que a ordem antiga não era contrato e que a
  página 1 pode mudar de composição; o critério de regressão continua sendo
  conjunto + total. O frontend reordena os cards por popularidade
  (`sequencia.html:42`), mas quais cards chegam na página 1 muda.

**Verificação:** `curl -s localhost:5000/generos` deve satisfazer
`g == sorted(g)`; dois containers/processos novos devem devolver a mesma página
1 para `?sequencia=Bm,G,D,A` comparando a **lista ordenada de
`id_unico_musica`**, não o hash do corpo: o campo `acordes` de cada música
continua sendo `list(set(...))` e muda de ordem entre processos. Medido nesta
entrega: 52 gêneros ordenados e a mesma lista de 100 ids na página 1 em dois
processos (o payload bruto difere só na ordem de `acordes`).

### 4. API `GET/POST /sequencias` e lookup do `/similares`

**Arquivos:** `main.py`, `matching.py`, `sequencias_db.py`.

- [x] `GET /sequencias`: servir do mapa `id → {acordes, criado_em}` em ordem de
  id, sem paginação. Formato:
  `[{"id": 0, "acordes": ["Bm","G","D","A"], "criado_em": "..."}]`.
  Resposta via `json.dumps(...)`, sem `jsonify`.
- [x] `POST /sequencias`: ler `request.get_json(silent=True)`; `None` ou corpo
  que não seja objeto → 400. Validar `acordes` como lista de strings:
  1 a 12 itens; cada token com `strip()` não vazio; até 12 caracteres após o
  `trim`; sem espaço, `,`, `;`, `|` ou caractere de controle; item que não seja
  string → 400. A validação é sintática, não musical: acorde desconhecido é
  aceito e repetições são permitidas. Mensagem de erro em `{"erro": "..."}`.
- [x] Calcular `chave = ','.join(tokens_lower)` e
  `chave_legado = ''.join(tokens_lower)`; consultar os mapas. Colisão em
  qualquer uma → 409 com `{"erro": "...", "id": <id_existente>}`.
- [x] Inserir preservando a grafia e a ordem originais; 201 com o objeto criado.
  Em corrida entre a checagem e o `INSERT`, capturar `sqlite3.IntegrityError`,
  buscar o id existente e devolver 409 — nunca 500.
- [x] Em `get_similares`, ramo `sequencia_tag` (`main.py:190-197`): normalizar a
  entrada dividindo por `,`, aplicando `trim`, descartando vazios e convertendo
  para minúsculas; montar `chave` e `chave_legado`; procurar primeiro `chave`,
  depois `chave_legado`; não encontrada → `json.dumps([])`. Usar `is not None`
  para aceitar o id 0.
- [x] **Só agora remover** o dict `sequencias` (`main.py:40-45`) e a comparação
  `if acordes in sequencias` (`main.py:194-195`), junto com o `id_seq` que vinha
  dele: o lookup passa a ser pelos mapas do catálogo. Nenhuma linha de `main.py`
  pode continuar referenciando esse dict; `grep -n "in sequencias"` não deve
  achar nada. Este é o passo que fecha o buraco aberto no passo 1 — até aqui o
  app rodava com o caminho antigo.
- [x] Manter o resto do contrato de `/similares`: filtro `generos`, `pagina` de
  100 e os 9 campos por música. As duas formas passam a ser equivalentes:
  `?sequencia=Bm,G,D,A` e `?sequencia=BmGDA`. Mudanças deliberadas: espaços ao
  redor dos tokens e caixa (`bm,g,d,a`) passam a ser aceitos.
- [x] Nada de `jsonify`, nada de mudar `Content-Type`; o `after_request` de CORS
  (`main.py:274-277`) continua valendo para as rotas novas.

**Verificação:** matriz mínima com o servidor local (ajustar a porta conforme o
ambiente):

| Caso | Requisição | Esperado |
|---|---|---|
| cadastro válido | `POST {"acordes":["Am","F","C","G"]}` | `201` + objeto com `id >= 6` |
| catálogo | `GET /sequencias` | `200`, array ordenado por id, 7 itens após o cadastro |
| duplicata exata | mesmo POST | `409` + `id` existente |
| duplicata legada | `POST {"acordes":["AmFCG"]}` | `409` (colisão em `chave_legado`) |
| corpo não-JSON | `POST` com `text/plain` | `400` |
| sem `acordes` / lista vazia | `{}` / `{"acordes":[]}` | `400` |
| item não-string | `{"acordes":[1]}` | `400` |
| token vazio / >12 / com espaço / com separador ou pipe / controle | variações | `400` |
| lookup com vírgulas | `?sequencia=Am,F,C,G` | `200`, conjunto da sequência nova |
| lookup legado | `?sequencia=AmFCG` | `200`, **mesmo conjunto** |
| caixa/espaços | `?sequencia=bm, g, d, a` | `200`, 199 músicas no total |
| desconhecida | `?sequencia=Zz,Zz` | `200` + `[]` |
| contrato | qualquer resposta | corpo começa com `[`/`{`, `Content-Type` `text/html`, CORS `*` |

### 5. Frontend `#/porsequencia`: catálogo, cadastro e estados

**Arquivos:** `static/assets/js/controllers/sequencia.js`,
`static/templates/sequencia.html`.

- [x] Remover os quatro literais (`sequencia.js:2-37`). No início do controller,
  chamar `carregarSequencias()`, que faz `$http.get("sequencias")` e monta
  `vm.sequenciasFamosas` no formato que o template já usa:
  `{id, acordes: [{acorde, cor: "#2E1C74"}]}`. Sem fallback hardcoded: catálogo
  velho é pior que erro visível.
- [x] Estados do catálogo: `vm.carregandoSequencias`, `vm.erroSequencias` e
  `vm.catalogoVazio`. Em erro, mostrar mensagem e botão “Tentar de novo”
  (`ng-click="Sequencia.carregarSequencias()"`); em vazio, “Nenhuma sequência
  cadastrada” (os seeds normalmente evitam esse estado, mas ele é previsto).
- [x] Formulário de cadastro: `vm.novaSequencia` (texto), `vm.cadastrando`,
  `vm.erroCadastro` e `vm.cadastrarSequencia()`. Dividir por vírgula, aplicar
  `trim`, descartar vazios e validar no cliente os mesmos limites do servidor
  (1–12 acordes, token até 12, sem espaço interno/`,`/`;`/`|`). Fazer
  `$http.post("sequencias", {acordes: tokens})`.
- [x] Em `201`: acrescentar o objeto devolvido ao catálogo (convertendo para o
  formato do `df-hex`), selecionar a sequência e chamar
  `pesquisarPorSequencia(sequencia)` para já mostrar os resultados. Em
  `400`/`409`: exibir `data.erro`; em `409`, usar o `id` devolvido apenas na
  mensagem (não cadastrar de novo). Sempre limpar `cadastrando` no `finally`
  (ou nos dois callbacks).
- [x] Manter `createChordsString` (`sequencia.js:55-61`) e a URL relativa
  (`sequencia.js:72-77`), que continuam produzindo `?sequencia=Am,F,C,G`. Não
  mexer em rota (`routes.js:17-21`) nem no carregamento do script
  (`index.html:145`).
- [x] Template: colocar o formulário acima dos hexágonos (`sequencia.html:5-14`),
  com input, botão, indicador de carregamento do cadastro e parágrafo de erro.
  Manter a lista de sequências no `ng-repeat` existente.
- [x] Corrigir `ng-hide="music.diferenca.length"` (`sequencia.html:43`):
  remover o atributo, porque a resposta de sequência não tem `diferenca` e a
  condição é sempre `undefined`. Adicionar estado vazio dos resultados
  (“Nenhuma música encontrada”) quando a busca terminou
  (`showSearchResultsCount && !isSearching && musics.length === 0`) e um
  “Buscando…” ligado a `isSearching`. Limpar `showSearchResultsCount` em
  `limparPesquisa()` para o estado vazio não reaparecer fora de contexto.
- [x] Não alterar a lista hardcoded de gêneros (`app.js:6-58`); é divergência
  pré-existente e fora do escopo.

**Verificação:** no browser, abrir `/#/porsequencia` com o backend novo:
a lista mostra **6** sequências (incluindo `Em,G` e `C,A7,Dm,G7`); o DevTools
mostra `GET /sequencias 200`. Cadastrar `Am, F, C, G` → aparece a 7ª sequência,
a busca dispara e o resultado bate com `?sequencia=Am,F,C,G`; recarregar a
página mantém a sequência (volume). Cadastrar `Bm, G, D, A` → mensagem de
duplicata. Buscar uma sequência sem matches → “Nenhuma música encontrada”.
Com throttling/rede lenta, o estado de carregamento aparece; com
`/sequencias` bloqueado no DevTools, aparece o erro com “Tentar de novo”.

### 6. Infraestrutura e documentação

**Arquivos:** `.gitignore`, `.dockerignore`, `README.md`, `AGENTS.md`;
`Dockerfile` só se a verificação mostrar necessidade.

- [x] `.gitignore`: acrescentar `db/` e `*.db`.
- [x] `.dockerignore`: acrescentar `db/` e `*.db`, para o `COPY . .`
  (`Dockerfile:8`) não copiar banco local para a imagem.
- [x] `README.md`: atualizar a descrição da stack (catálogo de sequências em
  SQLite; músicas/gêneros continuam no CSV em memória) e o comando Docker para
  `docker run -p 8080:8080 -v ciframe-data:/app/db ciframe`. Documentar que sem
  o volume `docker rm`/novo `docker run` perdem os cadastros, que
  `docker restart` preserva e que `CIFRAME_DB` sobrescreve o caminho.
- [x] `AGENTS.md`: mesma atualização na seção Stack (hoje diz “no database”),
  no comando Docker de “Run locally” e em Gotchas (banco em `/app/db`, `db/`
  ignorado, restart vs recriação).
- [x] `Dockerfile`: **não alterar por padrão**. `init_db` cria `/app/db` com
  `makedirs`; o processo roda como root e o volume nomeado é criado pelo Docker.
  Só adicionar um `RUN mkdir -p /app/db` se o teste de volume sem permissão
  falhar; registrar o motivo se isso acontecer.
- [x] Não alterar `baseline/README.md`: ele já descreve a comparação por
  conjunto (`baseline/README.md:51-79`) e continua válido.

**Verificação:** `git check-ignore -v db/sequencias.db` aponta para
`.gitignore`; um build novo não contém banco
(`docker run --rm --entrypoint ls ciframe-candidate /app/db` deve falhar antes
de o app iniciar); `docker run` com `-v ciframe-data:/app/db` cria o arquivo no
volume, `docker rm` + novo `docker run` com o mesmo volume mantém um cadastro, e
o comando sem `-v` perde o cadastro na recriação (comportamento documentado).

### 7. Verificação manual e regressão das 6 sequências

**Arquivos:** nenhum código novo; reutilizar `scripts/capture_baseline.py` e o
bloco de comparação de `docs/features/sequencias-customizadas/baseline/README.md`.

- [x] Build e execução com volume novo, para exercitar também a criação
  idempotente e os seeds:

```bash
docker build -t ciframe-candidate .
docker run -d --name ciframe-candidate -p 8080:8080 \
  -v ciframe-candidate-data:/app/db ciframe-candidate
```

- [x] Capturar as 6 sequências com o container novo. **Sempre** passar
  `--fixture-dir` para `/tmp`: o default do script é o fixture versionado e
  sobrescrevê-lo destruiria o baseline.

```bash
python3 scripts/capture_baseline.py \
  --raw-dir /tmp/opencode/baseline-candidate \
  --fixture-dir /tmp/opencode/baseline-candidate-fixture
```

- [x] Comparar por **conjunto de ids** (não por ordem) contra
  `docs/features/sequencias-customizadas/baseline/`, usando o bloco Python de
  `baseline/README.md` (“Como comparar depois da mudança”). Critério:

| id | `sequencia` | total esperado |
|---:|---|---:|
| 0 | `Bm,G,D,A` | 199 |
| 1 | `C,G,Am,F` | 296 |
| 2 | `Em,G` | 4 |
| 3 | `C,A7,Dm,G7` | 5 |
| 4 | `Gm,F` | 7 |
| 5 | `C,C7,F,Fm` | 3 |
| | **total** | **514** |

  Também conferir o formato do payload (os 9 campos por música) amostrando ids do
  fixture com `GET /musica/<id>`: o fixture versionado guarda apenas os ids, então
  a comparação campo a campo não é reproduzível e não entra no critério. `ids_sha256`
  e a ordem **não** entram no critério.
- [x] Teste manual de cadastro e busca, no container e pela UI:
  `POST {"acordes":["Am","F","C","G"]}` → 201; `GET /sequencias` mostra 7;
  `?sequencia=Am,F,C,G` e `?sequencia=AmFCG` devolvem o mesmo conjunto;
  recarregar a página mantém a sequência; `docker rm -f ciframe-candidate` e
  novo `docker run` com o mesmo volume mantém o cadastro.
- [x] Confirmar que a ordem é estável entre dois containers novos (mesmo corpo
  na página 1 de `Bm,G,D,A`) e que `/generos` continua com 52 itens ordenados.
- [x] Registrar commit, sha256 do CSV, nome do volume e totais obtidos para
  colar no `04-test-report.md` na fase de testes.

Registro desta execução:

- commit: `cf922e0` (o fix `para_dict()` entrou antes da rodada final)
- imagem: `ciframe-candidate`
- CSV: `data/top/dataset_final.csv`, sha256
  `5f94f49b945ffac76f9a114b353b51d6a07b9e6feeb1243ce5989295234b9207`
- volume: `ciframe-candidate-data`
- totais por id: 199, 296, 4, 5, 7, 3 (total 514); todos os conjuntos batem
  com `docs/features/sequencias-customizadas/baseline/`
- payload de `/musica/<id>/`: 9 campos
- persistência: `docker rm -f` + novo `docker run` com o mesmo volume mantém a
  sequência cadastrada (`Am,F,C,G`, id 6, 7 itens no catálogo, 278 resultados);
  sem `-v`, um container novo volta aos 6 seeds
- ordem estável entre dois containers novos na página 1 de `Bm,G,D,A`;
  `/generos` com 52 itens ordenados

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Inicialização do banco/mapa; normalização de matching; `generos = sorted(...)`; substituição do lookup em `seqs_famosas` pelo matcher; `GET/POST /sequencias`; lookup do `/similares` por `chave`/`chave_legado`; remoção do dict `sequencias` |
| `musica.py` | `cifra_lower` e `vocabulario` derivados no construtor; `para_dict()` mantém o payload histórico de `/musicas`/`/musica/<id>/`; `seqs_famosas` mantido temporariamente (decisão do passo 2) |
| `sequencias_db.py` (novo) | Caminho do banco, esquema, seeds 0–5, `user_version`, leitura do catálogo, inserção e exceção de duplicidade |
| `matching.py` (novo) | Normalização de entrada, montagem de `chave`/`chave_legado`, validação sintática e `casa_sequencia` |
| `static/assets/js/controllers/sequencia.js` | Catálogo via `GET /sequencias`; formulário e `POST`; estados de loading/erro/vazio; remoção dos 4 literais |
| `static/templates/sequencia.html` | Formulário acima dos hexágonos; estados de carregamento/erro/vazio; correção do `ng-hide` de `:43` |
| `.gitignore` | `db/` e `*.db` |
| `.dockerignore` | `db/` e `*.db` |
| `README.md` | Stack com SQLite; comando `docker run` com `-v ciframe-data:/app/db`; persistência e `CIFRAME_DB` |
| `AGENTS.md` | Stack, comando local e gotchas do banco/volume |
| `Dockerfile` | Sem mudança esperada; só `mkdir /app/db` se a verificação de volume exigir |
| `docs/features/sequencias-customizadas/baseline/README.md` | Sem mudança; já documenta a comparação por conjunto |

## Riscos e mitigação

| Risco | Como perceber | Mitigação |
|---|---|---|
| Matcher diverge da tag/baseline | `conferencia ... igual=False` no startup; diferença de conjunto no passo 7 | Não remover `seqs_famosas` antes do gate; comparar por conjunto; bloquear a entrega em qualquer diferença |
| Ordem alfabética muda a composição da página 1 | ids da página 1 diferentes do fixture; usuário vê outras músicas | Ordem nunca foi contrato; regressão por conjunto + total; documentar a mudança; UI continua ordenando por popularidade dentro da página |
| Banco perdido sem volume | cadastro some após `docker rm`/novo `docker run` | Documentar `-v ciframe-data:/app/db`; testar recriação no passo 6; não prometer persistência sem volume |
| Banco local copiado para a imagem | `ls /app/db` existe antes do app iniciar; build context cresce | `db/` e `*.db` no `.dockerignore`; verificar com `--entrypoint ls` |
| `POST` concorrente gera duplicata ou 500 | dois 201 para a mesma sequência, ou traceback `IntegrityError` | `UNIQUE` nas duas chaves + captura de `IntegrityError` → 409; `busy_timeout=5000`; teste de concorrência na fase 5 |
| Mapa em memória desatualizado com >1 worker | sequência cadastrada em um worker não aparece em outro | Manter 1 worker; registrar a limitação; revalidar cache/concorrência se o número de workers mudar |
| Diretório do banco sem permissão | startup falha com traceback | `makedirs` + mensagem com caminho; fail fast; testar com volume e sem volume |
| Catálogo aberto sofre abuso | crescimento de linhas, sequências sem sentido | Limites de validação (12 acordes × 12 caracteres); rate limit/login estão fora do escopo e ficam como risco aceito |
| `?sequencia` fica mais permissivo | `bm,g,d,a` e espaços passam a devolver resultados antes vazios | Mudança deliberada; documentar no README/PR; não tratar como bug |
| Custo de startup/memória cresce | tempo de boot e RSS maiores | Medir ~407 ms/alguns MB; se estourar, reavaliar armazenamento de `cifra_lower` antes de mudar a regra |
| Frontend sem fallback fica vazio se `GET /sequencias` falhar | painel sem sequências | Estado de erro explícito + “Tentar de novo”; fallback hardcoded foi descartado por ficar stale |
| Alguém “limpa” `json.dumps` para `jsonify` | `Content-Type` vira `application/json` | Revisão + teste da matriz do passo 4; a restrição está no passo 4 e no ADR |
| Fixture baseline sobrescrito pela captura | `git status` mostra mudanças em `baseline/` | Sempre usar `--fixture-dir /tmp/...` no passo 7 |
| Id 0 tratado como “não encontrado” | seed `Bm,G,D,A` some do lookup | Usar `is not None` em todos os mapas; testar explicitamente o id 0 |

### Segurança e abuso

- O `POST` é anônimo por requisito; sem rate limit, captcha ou moderação, o
  catálogo pode crescer ou receber lixo. É risco aceito e registrado no ADR
  0002, não um item a resolver nesta entrega.
- Consultas SQL sempre parametrizadas; a validação limita tamanho e caracteres,
  mas não tenta validar música.
- O banco fica fora de `static/`; o catch-all `/<path:path>` só serve
  `app.send_static_file`, então `/db/sequencias.db` não é exposto. Verificar com
  `curl -i localhost:8080/db/sequencias.db` → 404.
- Nenhum segredo novo; o caminho do banco vem de `CIFRAME_DB` ou do default.

## Fase de testes (registrada, não executada)

Nenhum teste é escrito nesta entrega e `04-test-report.md` não é preenchido
agora. Fica para a fase 5:

- **Unitários de `matching.py`:** caixa, fatia contígua, repetições,
  vocabulário contido, sequência vazia, token que só casa como substring de
  outro (`em;g` vs `em;g7`) e equivalência com a regra da tag nas 67.585 linhas
  (reaproveitar a lógica de `scripts/research_matching.py`, que é experimento,
  não teste).
- **API:** toda a matriz 201/400/409 do passo 4, `GET /sequencias` ordenado,
  lookup pelas duas chaves, desconhecida → `[]`, `pagina`/`generos` preservados,
  `Content-Type`/CORS e ausência de `jsonify`.
- **Persistência:** criação idempotente, seeds, `user_version`, reabertura,
  volume, `CIFRAME_DB`, banco futuro (`user_version > 1`) abortando.
- **Frontend:** sem harness no repo; validar manualmente os estados de
  catálogo/cadastro/busca e a correção do `ng-hide` (ou criar harness se a fase
  de testes decidir).
- **Regressão:** automatizar a captura + comparação por conjunto e totais
  (199, 296, 4, 5, 7, 3; 514). `baseline/README.md` já tem o script de
  comparação; o relatório deve registrar commit, CSV e volume usados.

### O que precisa de teste de concorrência

O `CMD` atual roda **1 worker gunicorn síncrono**, então as requisições são
serializadas no processo; o `main.py` de desenvolvimento (`app.run`) e um futuro
aumento de workers/threads tornam a concorrência real. Testar:

- Dois `POST` simultâneos da mesma sequência: exatamente um `201` e um `409`,
  sem `500` e sem duas linhas iguais.
- Vários `POST` simultâneos de sequências distintas: todos `201`, sem
  `database is locked` (coberto por `busy_timeout`).
- `POST` concorrente com `GET /similares` e `GET /sequencias`: sem `KeyError`/
  estado parcial; a sequência nova só precisa aparecer depois do `201`.
- Reinício com banco existente: seeds não duplicam e o `user_version` não é
  reescrito.
- Múltiplos workers (fora do suporte atual): documentar que cada worker tem seu
  mapa e um `POST` em um worker não é visto pelo outro; se isso for necessário
  no futuro, trocar o cache por leitura do banco ou revalidar a cada request.

## Definição de pronto

| # | Critério | Como verificar |
|---:|---|---|
| 1 | `docker build -t ciframe .` e `docker run -p 8080:8080 -v ciframe-data:/app/db ciframe` sobem; `/generos` responde 200 com 52 gêneros ordenados | passos 3 e 6 |
| 2 | Banco criado em `/app/db/sequencias.db` (ou `CIFRAME_DB`/`./db`), tabela `sequences`, seeds 0–5, `user_version=1`; reiniciar não duplica | passo 1 |
| 3 | `GET /sequencias` devolve as 6 sequências em ordem de id | passo 4 |
| 4 | **Cadastro funciona:** `POST` válido devolve 201, aparece no `GET`, sobrevive a `docker rm` + novo `docker run` com o mesmo volume | passos 4 e 6 |
| 5 | `POST` duplicado devolve 409 com o id existente; payload inválido devolve 400; nenhum caso devolve 500 | passo 4 |
| 6 | **Busca por sequência nova funciona:** `?sequencia=Am,F,C,G` e `?sequencia=AmFCG` devolvem o mesmo conjunto, e a UI busca pela sequência cadastrada | passos 4, 5 e 7 |
| 7 | **As 6 originais mantêm o mesmo conjunto:** 199, 296, 4, 5, 7, 3 (514 no total); formato dos 9 campos conferido por amostragem de ids do fixture via `GET /musica/<id>` (o fixture versionado guarda só os ids); ordem e `ids_sha256` não são critério | passo 7 |
| 8 | Ordem determinística: `/generos` ordenado e dois processos novos devolvem a mesma página 1; conjuntos/contagens de `/search` e `/similares` inalterados | passo 3 |
| 9 | Frontend lista 6 sequências do backend, cadastra com loading/erro/vazio, e o `ng-hide` de `sequencia.html:43` não esconde resultados | passo 5 |
| 10 | `db/` e `*.db` fora do Git e do build; README/AGENTS documentam o volume e o `CIFRAME_DB` | passo 6 |
| 11 | Restrições mantidas: nenhuma dependência nova, `json.dumps` em todos os endpoints, 1 worker | revisão do diff |
| 12 | Tarefas da fase de testes (incluindo concorrência) registradas, sem testes escritos nesta entrega | seção “Fase de testes” |
