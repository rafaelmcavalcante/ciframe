# Baseline de regressão — sequências hardcoded

Respostas reais do backend, capturadas no commit `40c913a` com a app rodando no
Dockerfile do repo, **antes** de qualquer mudança na feature de sequências.

Serve como critério de regressão da fase de testes: as 6 sequências de
`main.py:40-45` precisam continuar devolvendo exatamente este **conjunto** de
músicas (mesmos ids, mesmos totais), depois da migração do catálogo para o banco.
A ordem não faz parte do critério — ver a seção de comparação abaixo.

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

`/generos` devolveu 52 gêneros.

A **ordem** dos resultados não é estável entre processos: `apply_filtro`
concatena listas por gênero na ordem de `list(set(...))` (`main.py:92`,
`main.py:266-272`), que varia com a hash randomization de cada processo. Este
fixture é uma foto de uma dessas ordens; um container novo devolve os mesmos ids
em outra ordem. Por isso `ids_sha256` e a ordem dos arquivos `seq-N-ids.json`
**não** são critério de regressão.

## Como comparar depois da mudança

```
docker build -t ciframe-candidate .
docker run -d --name ciframe-candidate -p 8080:8080 ciframe-candidate
python3 scripts/capture_baseline.py --raw-dir /tmp/opencode/baseline-candidate \
  --fixture-dir /tmp/opencode/baseline-candidate-fixture
python3 - <<'PY'
import glob, json, os, sys

base = 'docs/features/sequencias-customizadas/baseline'
cand = '/tmp/opencode/baseline-candidate-fixture'
fail = 0
for path in sorted(glob.glob(os.path.join(base, 'seq-*-ids.json'))):
    name = os.path.basename(path)
    esperado = set(json.load(open(path))['ids'])
    obtido = set(json.load(open(os.path.join(cand, name)))['ids'])
    if esperado == obtido:
        print(name, 'ok', len(esperado))
        continue
    fail = 1
    print(name, 'REGRESSAO', 'faltando=%d sobrando=%d'
          % (len(esperado - obtido), len(obtido - esperado)))
sys.exit(fail)
PY
```

Diferença de conjunto em qualquer `seq-N-ids.json` = regressão nas 6 sequências
originais. O script sai com código 1 nesse caso.
