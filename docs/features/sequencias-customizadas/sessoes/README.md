# Sessões do Big Pickle

Arquivo da sessão de entrega: exports JSON das sessões em que o trabalho da
atividade foi feito com o modelo `opencode/big-pickle`, como o enunciado exige.

Só os chats do Big Pickle entram aqui — sessões conduzidas com outro modelo são
ignoradas pelo script de exportação.

## Conteúdo

| Arquivo | Fase | Mensagens |
|---|---|---:|
| `sessao-20261101-ses_e6733bf1dffedZ3n4Z195lIMuZ.json` | 1 — pesquisa | 36 |
| `sessao-20261101-ses_e672873e3ffebFVCjwvHkkBcvT.json` | 2 — proposta + ADR | 47 |
| `sessao-20261101-ses_e6717fcb4ffeX3B1I6lX6GcEGh.json` | 3 — plano | 22 |
| `sessao-20261101-ses_e670ea103ffeAQDI0aifOqLJx5.json` | 4 — implementação | 123 |
| `sessao-20261101-ses_e669f3ed6ffe3SMrsv1brFsNnw.json` | 5 — testes | 75 |

O export inclui os prompts, as respostas, as chamadas de ferramenta e as
saídas — é o registro completo do processo, não um resumo.

## Como adicionar as próximas sessões

Do root do repo:

```bash
python3 scripts/export_big_pickle_sessions.py
```

O script lê `opencode session list` do projeto, exporta cada sessão e grava
`sessao-<AAAAMMDD>-<session-id>.json` aqui somente quando **todas** as mensagens
do assistente vieram de `opencode/big-pickle`. Sessões já exportadas são puladas,
então rodar de novo é seguro. Para gravar em outro lugar: `--out <pasta>`.
