# Baseline de regressão — sequências hardcoded

Respostas reais do backend, capturadas no commit `40c913a` com a app rodando no
Dockerfile do repo, **antes** de qualquer mudança na feature de sequências.

Serve como critério de regressão da fase de testes: as 6 sequências de
`main.py:40-45` precisam continuar devolvendo exatamente esta lista de músicas,
na mesma ordem, depois da migração do catálogo para o banco.

## Como foi capturado

```
docker build -t ciframe-baseline .
docker run -d --name ciframe-baseline -p 8080:8080 ciframe-baseline
python3 scripts/capture_baseline.py
```

O script só lê a API pública (`/generos` e `/similares?sequencia=...`). Os
arquivos aqui são a versão compacta (lista ordenada de `id_unico_musica` por
sequência + manifesto); as páginas JSON cruas ficam no `--raw-dir` escolhido.

## Conteúdo

| Arquivo | O que é |
|---|---|
| `manifest.json` | commit, branch, sha256 do CSV e da imagem, status/content-type/sha256 de cada página e total por sequência |
| `seq-0-ids.json` ... `seq-5-ids.json` | ids das músicas, na ordem retornada pela API |

## Totais no baseline

| id | `sequencia` | músicas |
|---|---|---:|
| 0 | `Bm,G,D,A` | 199 |
| 1 | `C,G,Am,F` | 296 |
| 2 | `Em,G` | 4 |
| 3 | `C,A7,Dm,G7` | 5 |
| 4 | `Gm,F` | 7 |
| 5 | `C,C7,F,Fm` | 3 |
| | **total** | **514** |

`/generos` devolveu 52 gêneros. A captura é determinística: duas execuções
seguidas produzem as mesmas listas, na mesma ordem.

## Como comparar depois da mudança

```
docker build -t ciframe-candidate .
docker run -d --name ciframe-candidate -p 8080:8080 ciframe-candidate
python3 scripts/capture_baseline.py --raw-dir /tmp/opencode/baseline-candidate \
  --fixture-dir /tmp/opencode/baseline-candidate-fixture
diff -r /tmp/opencode/baseline-candidate-fixture docs/features/sequencias-customizadas/baseline
```

Diferença em qualquer `seq-N-ids.json` = regressão nas 6 sequências originais.
