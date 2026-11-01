# Research — Custom Chord Sequences

The full investigation, with the complete tables and line references, is
[docs/features/sequencias-customizadas/01-research.md](../docs/features/sequencias-customizadas/01-research.md).
This top-level file is the research index and summarizes the cross-component
findings.

## Summary

The current app does not compute chord-sequence matches at runtime. It maps the
comma-stripped query to one of six hardcoded keys (`main.py:40-45`,
`main.py:190-197`) and filters songs by the pre-computed `SEQ_FAMOSA` tag
(`main.py:203-223`). The live baseline for the six sequences is 199, 296, 4, 5,
7 and 3 songs (514 total), capped at 100 per page (`main.py:35`,
`main.py:226-228`). Only a literal reproduction of the tag generator
(`scripts/generate_data_set.py:7-24`) matches that baseline; contiguous,
gapped, set-containment and distinct-order definitions do not. The
`#/porsequencia` frontend lists four hardcoded sequences (`sequencia.js:2-37`),
covering backend ids 0, 1, 4 and 5, so ids 2 (`Em,G`) and 3 (`C,A7,Dm,G7`) are
missing. DeepWiki confirmed the endpoint flow, the six keys and the 4-vs-6
divergence, but incorrectly claimed that SQLite, `POST /similares/cadastrar`
and runtime custom matching already exist.

## Detailed findings

### Matching and tags

- The tag is generated offline by `scripts/generate_data_set.py:7-24`: the
  sequence must appear as a contiguous substring of the `;`-joined chord
  string, and every chord in the song must belong to the sequence's chord set.
- `Musica.cifra` preserves order and repetition; `Musica.acordes` is
  `list(set(cifra))` and loses both (`musica.py:16-18`).
- There is no enharmonic, suffix or inversion normalization in `main.py`; the
  tag generator lowercases both sides (`scripts/generate_data_set.py:12`).
- The CSV has no header, so `main.py:50` discards the first data row; 67,585
  songs are loaded, 514 of them tagged.

### Baseline and experiment

- Baseline pages are in `/tmp/opencode/baseline/<id>_<key>/pagina_<n>.json`,
  with totals in `summary.json`: 199 / 296 / 4 / 5 / 7 / 3.
- The committed fixture in `docs/features/sequencias-customizadas/baseline/`
  (`manifest.json` + `seq-<id>-ids.json`) has the same totals and, for all six
  ids, the same id sets as the CSV tags and as `e_legacy_tag_rule`.
- `scripts/research_matching.py` reproduces the CSV parsing and compares five
  definitions. `e_legacy_tag_rule` gives TP=514, FP=0, FN=0 and exact sets for
  6/6 sequences; `a`, `b` and `c` have recall 1.0 but 5,945 / 28,127 / 31,102
  false positives; `d` has 301 false negatives.
- The experiment also confirms 67,585/67,585 rows agree with the CSV tags under
  the literal rule.

### Persistence options

- No database exists today: sequences are a dict (`main.py:40-45`),
  `requirements.txt:4-5` only lists Flask and gunicorn, and the Dockerfile has
  no `VOLUME` (`Dockerfile:1-12`).
- SQLite (`sqlite3` 3.46.1) and `shelve` are available in the image; TinyDB is
  not installed; Postgres/psql/psycopg are absent.
- A file in `/app` survives `docker restart` but disappears after `docker rm`
  plus a new `docker run`; a bind mount survives recreation.
- TinyDB would require a new `requirements.txt` entry; Postgres would require a
  server process and driver inside the single container, or a separate service.

### Frontend

- `#/porsequencia` is routed in `static/assets/js/routes.js:17-21` to
  `SequenciaController` and `static/templates/sequencia.html`.
- The controller builds `similares?sequencia=<chords>` with commas
  (`sequencia.js:55-77`); the backend removes the commas and looks up the exact
  key (`main.py:191-197`).
- The page has no catalog fetch, no form, no POST and no pagination; it only
  sends page 1 and therefore displays at most 100 of the 199/296 results.
- Genres in the select are also hardcoded (`static/assets/js/app.js:6-58`).

## Cross-component data flow

1. Startup: `main.py:49-98` reads the CSV, `limpa_cifra` builds ordered chord
   lists (`main.py:11-23`), `Musica` builds `cifra`, `acordes` and `seqs_famosas`
   (`musica.py:16-18`), and `musicas` is sorted by popularity.
2. Request: `GET /similares?sequencia=Bm,G,D,A` -> `replace(',', '')` ->
   `BmGDA` -> `sequencias['BmGDA'] = 0` -> scan `musicas` for `'0' in
   seqs_famosas` -> paginate 100 -> `json.dumps` (`main.py:170-228`).
3. Frontend: route -> four hardcoded cards -> GET without `pagina` -> cards
   from `vm.musics` (`sequencia.js:63-90`, `sequencia.html:40-58`).
4. Couplings: the backend dict is the only full catalog; the JS list is a
   partial copy; the CSV tag is the only matching source for sequences; the
   100-item cap is enforced in the backend but not handled by the frontend.

## Artifacts

- `scripts/research_matching.py` — stdlib-only parser and matching experiment.
- `/tmp/opencode/baseline/` — captured live responses for all pages.
- `/tmp/opencode/research_matching.json` — full experiment output.
- `docs/features/sequencias-customizadas/baseline/` — committed id fixtures and
  capture manifest for the six hardcoded sequences.
- `scripts/capture_baseline.py` — re-captures the live API into raw pages and
  the compact fixture.
