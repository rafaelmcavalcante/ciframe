# deciframe

Descubra as músicas que você já sabe tocar (e ainda não faz ideia). Busque por
título/artista, gênero, pelos acordes que você já manja, ou por sequências de
acordes famosas — o deciframe cruza isso com uma base de cifras e sugere
músicas parecidas.

Stack: backend Flask (Python) servindo uma API JSON + um frontend AngularJS
estático. Músicas e gêneros são carregados de um CSV em memória; o catálogo de
sequências de acordes fica em SQLite (`/app/db/sequencias.db` no container),
criado no startup com as seis sequências originais.

## Rodando localmente

### Com Docker

```
docker build -t ciframe .
docker run -p 8080:8080 -v ciframe-data:/app/db ciframe
```

Acesse [http://localhost:8080](http://localhost:8080).

O volume `ciframe-data` guarda o catálogo de sequências entre containers. Sem
`-v`, um `docker restart` preserva o arquivo na camada gravável do container,
mas `docker rm` + novo `docker run` perdem os cadastros. Defina `CIFRAME_DB`
para usar outro caminho de banco.

### Com virtualenv

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Acesse [http://localhost:5000](http://localhost:5000).

Fora do Docker, o catálogo fica em `./db/sequencias.db` (ignorado pelo Git). O
caminho pode ser sobrescrito com `CIFRAME_DB`.

---

Para convenções de contribuição, veja [CONTRIB.md](CONTRIB.md). Licença: [LICENSE](LICENSE).
