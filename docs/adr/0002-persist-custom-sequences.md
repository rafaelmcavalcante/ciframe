# Persistir sequências de acordes customizadas em SQLite local

Até aqui o deciframe não tinha banco: as seis sequências de acordes eram um
dicionário literal em `main.py`, e a busca por sequência dependia de uma tag
`SEQ_FAMOSA` pré-calculada no CSV (`main.py:40-45`, `main.py:203-223`). O
enunciado agora exige que qualquer visitante cadastre uma sequência nova e que o
catálogo sobreviva a reinícios, sem migrar músicas ou gêneros para o banco e sem
sair do container único definido no ADR 0001.

Decidimos introduzir **SQLite** (o `sqlite3` da biblioteca padrão) como a única
forma de persistência, com um arquivo em `/app/db/sequencias.db` e uma tabela
`sequences` contendo id, a lista ordenada de acordes, a chave canônica, a chave
sem vírgulas (compatibilidade com o formato antigo de URL) e a data de criação.
As seis sequências atuais entram como seeds com ids 0–5; o restante do catálogo
cresce por `POST /sequencias`. Músicas e gêneros continuam vindo do CSV em
memória, e a busca continua sendo calculada em tempo real sobre `musica.cifra`,
sem tabela de resultados pré-computados e sem depender da tag do CSV.

A escolha do SQLite vem de ele ser embarcado: não exige um processo de servidor,
não muda o `Dockerfile` além do diretório do arquivo, não adiciona dependência
ao `requirements.txt` e cabe no container único que o ADR 0001 fixou. Ele também
dá o que TinyDB e `shelve` não dão sem trabalho extra: `UNIQUE`, `NOT NULL`,
transações e uma forma declarativa de evitar sequências duplicadas. Postgres
resolveria isso com folga, mas exigiria instalar servidor e driver, inicializar
data dir e rodar um segundo processo — exatamente o que o container único
proíbe. O catálogo é pequeno e tem pouca escrita, então o limite de um escritor
por vez do SQLite não é um problema com o único worker gunicorn atual.

O arquivo fica em `/app/db`, e não em `/app/data`, porque o CSV está em
`/app/data/top/dataset_final.csv` e é copiado para a imagem pelo `COPY . .` do
`Dockerfile`. Montar o volume em `/app/data` esconderia o diretório inteiro e a
aplicação não encontraria o dataset no startup; `/app/db` separa o estado
mutável do conteúdo imutável da imagem. Para sobreviver a `docker rm` e a um
novo `docker run`, o comando documentado passa a ser
`docker run -p 8080:8080 -v ciframe-data:/app/db ciframe`. Sem o volume,
`docker restart` ainda preserva o arquivo na camada gravável, mas recriar o
container o perde; o volume nomeado é mais portátil do que um bind mount e não
depende de caminho do host.

A regra de matching é a mesma para as seis sequências antigas e para as novas: a
sequência precisa aparecer como fatia contígua da cifra e a música inteira só
pode usar acordes do vocabulário da sequência, comparando sem diferenciar
maiúsculas. É a reprodução da regra que gerou a tag `SEQ_FAMOSA`
(`scripts/generate_data_set.py:7-24`), e foi a única das definições testadas que
reproduziu o baseline — as demais geraram milhares de falsos positivos. Calcular
essa regra em tempo real para todas as sequências elimina a dependência da tag,
uniformiza o comportamento e deixa qualquer sequência cadastrada pesquisável
sem novo deploy. O custo medido é de cerca de 17 ms por busca para sequências de
quatro acordes, com a normalização de caixa e vocabulário feita uma vez no
startup. A contrapartida é que sequências novas também são estritas e tendem a
devolver poucas músicas; relaxar o vocabulário só para elas criaria duas
semânticas para o mesmo botão e foi descartado.

Uma consequência aceita é que a **ordem** dos resultados deixa de fazer parte do
contrato. O app atual já não é determinístico nesse ponto: a lista de gêneros
nasce de um `set` e a iteração varia entre processos por hash randomization, de
modo que o baseline versionado é uma foto de uma ordem que um processo novo não
reproduz. A regressão das seis sequências passa a ser comparada por conjunto de
ids e contagem (199, 296, 4, 5, 7 e 3; 514 no total), não por ordem. Para não
deixar essa instabilidade escondida, os gêneros passam a ser ordenados
alfabeticamente, o que torna a ordem determinística e é uma mudança de
comportamento observável em `/similares`, `/search` e `/generos`; conjuntos e
contagens não mudam. Outros trade-offs conhecidos: o catálogo é aberto e
anônimo, então pode crescer ou ser abusado sem rate limit (fora do escopo);
não há framework de migração, apenas criação idempotente e `user_version`; o
banco não é embarcado na imagem, e um `docker rm` sem o volume perde os
cadastros; e a tag `SEQ_FAMOSA` continua sendo lida do CSV por enquanto, mas
deixa de ser a fonte de verdade da busca.
