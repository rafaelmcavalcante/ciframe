#!/usr/bin/env python3
# coding: utf-8
"""Reproduce main.py's CSV parsing and compare candidate matching rules.

This script is research tooling only. It does not import or modify the Flask app.
It reads data/top/dataset_final.csv with the same line-level parsing used by
main.py (main.py:49-63), rebuilds Musica.cifra/Musica.acordes (musica.py:16-18),
and compares five definitions of "sequence X appears in song Y" against the
pre-computed SEQ_FAMOSA tags.

The optional --baseline directory is the tree saved from the live container:
  /tmp/opencode/baseline/<seq_id>_<seq_key>/pagina_<n>.json
Each JSON file is one page returned by GET /similares?sequencia=...&pagina=n.

Usage:
  python3 scripts/research_matching.py
  python3 scripts/research_matching.py --baseline /tmp/opencode/baseline
  python3 scripts/research_matching.py --json-out /tmp/opencode/matching.json
"""

import argparse
import glob
import json
import os
import re
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, 'data', 'top', 'dataset_final.csv')

# main.py:40-45 and data/mapeamento_sequencias_famosas.txt:1-6
SEQUENCES = [
    ('0', 'BmGDA', ['Bm', 'G', 'D', 'A']),
    ('1', 'CGAmF', ['C', 'G', 'Am', 'F']),
    ('2', 'EmG', ['Em', 'G']),
    ('3', 'CA7DmG7', ['C', 'A7', 'Dm', 'G7']),
    ('4', 'GmF', ['Gm', 'F']),
    ('5', 'CC7FFm', ['C', 'C7', 'F', 'Fm']),
]

DEFINITIONS = OrderedDict([
    ('a_contiguous_ordered',
     'subsequencia contigua e ordenada; repeticoes e adjacencia importam'),
    ('b_ordered_gapped',
     'subsequencia ordenada com lacunas; repeticoes nao importam'),
    ('c_set_containment',
     'contencao de conjuntos; sem ordem e sem repeticao'),
    ('d_distinct_relative_order',
     'acordes distintos na ordem da primeira ocorrencia, com lacunas'),
    ('e_legacy_tag_rule',
     'regra literal de scripts/generate_data_set.py:get_famosas'),
])


def limpa_cifra(raw_cifra):
    """Exact copy of main.py:11-23."""
    cifra = []
    for m in raw_cifra:
        if m.strip() != '':
            if '|' in m:
                acorde = m.split('|')[0].split()[0]
                cifra.append(acorde)
            else:
                cifra += [token for token in m.split()]
    return cifra


def load_main_rows(path):
    """Read the CSV exactly as main.py:49-63 does, including skipping line 1.

    main.py does f.readline() before the loop even though the file has no
    header; the first data row is therefore discarded by the running app.
    """
    rows = []
    malformed = []
    with open(path, encoding='utf-8') as f:
        f.readline()  # main.py:50
        for lineno, line in enumerate(f, start=2):
            line = line.replace('"', '').replace('NA', '')[:-1]  # main.py:53
            musica = line.split(',')  # main.py:55
            try:
                musica[5] = int(musica[5].replace('.', ''))  # main.py:56
            except (IndexError, ValueError):
                malformed.append((lineno, 'popularidade', line[:80]))
                continue
            if len(musica) < 9:
                malformed.append((lineno, 'colunas', line[:80]))
                continue
            if musica[8] != '':
                cifra = limpa_cifra(musica[8].split(';'))  # main.py:58-59
            else:
                cifra = []  # main.py:61
            seqs = musica[7].split(';')  # main.py:63
            rows.append({
                'lineno': lineno,
                'id': '%s_%s' % (musica[0], musica[1]),
                'cifra': cifra,
                'acordes': list(set(cifra)),  # musica.py:17
                'seqs': seqs,
            })
    return rows, malformed


def contains_contiguous(haystack, needle):
    n = len(needle)
    if n == 0:
        return True
    return any(haystack[i:i + n] == needle
               for i in range(len(haystack) - n + 1))


def is_ordered_subsequence(haystack, needle):
    pos = 0
    for chord in haystack:
        if pos < len(needle) and chord == needle[pos]:
            pos += 1
    return pos == len(needle)


def distinct_first_occurrence(chords):
    seen = set()
    out = []
    for chord in chords:
        if chord not in seen:
            seen.add(chord)
            out.append(chord)
    return out


def legacy_tag_rule(cifra, seq):
    """Literal port of scripts/generate_data_set.py:7-24 (get_famosas).

    generate_data_set.py works on the raw ';'-joined string, lowercases it,
    checks string containment of the sequence, then requires every chord in
    the whole song to be one of the sequence's chords.
    """
    raw = ';'.join(cifra).lower()
    wanted = ';'.join(seq).lower()
    if wanted not in raw:
        return False
    tokens = wanted.split(';')
    return all(chord in tokens for chord in raw.split(';'))


def matches(definition, cifra, seq):
    if definition == 'a_contiguous_ordered':
        return contains_contiguous(cifra, seq)
    if definition == 'b_ordered_gapped':
        return is_ordered_subsequence(cifra, seq)
    if definition == 'c_set_containment':
        return set(seq) <= set(cifra)
    if definition == 'd_distinct_relative_order':
        return is_ordered_subsequence(distinct_first_occurrence(cifra), seq)
    if definition == 'e_legacy_tag_rule':
        return legacy_tag_rule(cifra, seq)
    raise ValueError(definition)


def normalize_case(chords):
    return [chord.lower() for chord in chords]


def score(predicted, actual):
    tp = len(predicted & actual)
    fp = len(predicted - actual)
    fn = len(actual - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn,
            'precision': precision, 'recall': recall,
            'exact': predicted == actual}


def load_baseline(path):
    """Return {seq_id: set(ids)} from the live /similares pages."""
    out = {}
    if not path or not os.path.isdir(path):
        return out
    for seq_id, seq_key, _ in SEQUENCES:
        ids = []
        pattern = os.path.join(path, '%s_%s' % (seq_id, seq_key), 'pagina_*.json')
        for filename in sorted(glob.glob(pattern),
                               key=lambda p: int(re.search(r'pagina_(\d+)', p).group(1))):
            with open(filename, encoding='utf-8') as f:
                page = json.load(f)
            if not isinstance(page, list):
                continue
            ids.extend(item['id_unico_musica'] for item in page)
        out[seq_id] = set(ids)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default=CSV_PATH)
    parser.add_argument('--baseline', default='/tmp/opencode/baseline')
    parser.add_argument('--json-out', default=None)
    args = parser.parse_args()

    rows, malformed = load_main_rows(args.csv)
    actual = {seq_id: set() for seq_id, _, _ in SEQUENCES}
    for row in rows:
        for seq_id, _, _ in SEQUENCES:
            if seq_id in row['seqs']:
                actual[seq_id].add(row['id'])

    results = OrderedDict()
    for definition in DEFINITIONS:
        per_seq = OrderedDict()
        total = {'tp': 0, 'fp': 0, 'fn': 0, 'actual': 0, 'predicted': 0}
        for seq_id, seq_key, seq in SEQUENCES:
            predicted = set(row['id'] for row in rows
                            if matches(definition, row['cifra'], seq))
            per_seq[seq_id] = score(predicted, actual[seq_id])
            per_seq[seq_id]['predicted'] = len(predicted)
            per_seq[seq_id]['actual'] = len(actual[seq_id])
            for key in ('tp', 'fp', 'fn', 'actual', 'predicted'):
                total[key] += per_seq[seq_id][key]
        total['precision'] = (total['tp'] / (total['tp'] + total['fp'])
                              if total['tp'] + total['fp'] else 0.0)
        total['recall'] = (total['tp'] / (total['tp'] + total['fn'])
                           if total['tp'] + total['fn'] else 0.0)
        total['exact'] = all(r['exact'] for r in per_seq.values())
        results[definition] = {'per_sequence': per_seq, 'total': total}

    # The literal rule must reproduce every SEQ_FAMOSA tag row by row.
    legacy_disagreements = []
    for row in rows:
        predicted = set(seq_id for seq_id, _, seq in SEQUENCES
                        if legacy_tag_rule(row['cifra'], seq))
        actual_row = set(sid for sid, _, _ in SEQUENCES if sid in row['seqs'])
        if predicted != actual_row:
            legacy_disagreements.append((row['id'], sorted(actual_row),
                                         sorted(predicted)))

    baseline = load_baseline(args.baseline)

    # Normalization experiment: case-insensitive versions of a and c.
    normalization = OrderedDict()
    for seq_id, seq_key, seq in SEQUENCES:
        ci = normalize_case(seq)
        norm = {
            'contiguous_ci': sum(matches('a_contiguous_ordered',
                                         normalize_case(row['cifra']), ci)
                                 for row in rows),
            'contiguous_cs': sum(matches('a_contiguous_ordered',
                                         row['cifra'], seq) for row in rows),
            'set_ci': sum(matches('c_set_containment',
                                  normalize_case(row['cifra']), ci)
                          for row in rows),
            'set_cs': sum(matches('c_set_containment',
                                  row['cifra'], seq) for row in rows),
        }
        normalization[seq_id] = norm

    all_tokens = Counter(chord for row in rows for chord in row['cifra'])
    case_groups = {}
    for chord in all_tokens:
        case_groups.setdefault(chord.lower(), set()).add(chord)
    collisions = {k: sorted(v) for k, v in case_groups.items() if len(v) > 1}

    lines = []
    lines.append('# Research matching experiment')
    lines.append('')
    lines.append('csv=%s' % args.csv)
    lines.append('rows_loaded=%d (main.py skips the first data line)' % len(rows))
    lines.append('malformed=%d' % len(malformed))
    lines.append('rows_with_seq_tag=%d' % sum(1 for row in rows if any(
        sid in row['seqs'] for sid, _, _ in SEQUENCES)))
    lines.append('legacy_rule_row_agreement=%d/%d disagree=%d' % (
        len(rows) - len(legacy_disagreements), len(rows),
        len(legacy_disagreements)))
    lines.append('distinct_chord_tokens=%d' % len(all_tokens))
    lines.append('case_collision_groups=%d' % len(collisions))
    lines.append('')
    lines.append('| seq | chords | definition | actual | predicted | TP | FP | FN | precision | recall | exact set |')
    lines.append('|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|')
    for seq_id, seq_key, _ in SEQUENCES:
        for definition in DEFINITIONS:
            r = results[definition]['per_sequence'][seq_id]
            lines.append('| %s | %s | %s | %d | %d | %d | %d | %d | %.4f | %.4f | %s |' % (
                seq_id, seq_key, definition, r['actual'], r['predicted'],
                r['tp'], r['fp'], r['fn'], r['precision'], r['recall'],
                'yes' if r['exact'] else 'no'))
    lines.append('')
    lines.append('| definition | TP | FP | FN | precision | recall | exact seqs |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|')
    for definition, data in results.items():
        t = data['total']
        exact = sum(1 for r in data['per_sequence'].values() if r['exact'])
        lines.append('| %s | %d | %d | %d | %.4f | %.4f | %d/6 |' % (
            definition, t['tp'], t['fp'], t['fn'], t['precision'],
            t['recall'], exact))
    lines.append('')
    if baseline:
        lines.append('## Baseline cross-check (live /similares ids vs experiment)')
        lines.append('')
        lines.append('| seq | baseline ids | tags | legacy rule | exact baseline=tags |')
        lines.append('|---|---:|---:|---:|:---:|')
        for seq_id, seq_key, seq in SEQUENCES:
            base = baseline.get(seq_id, set())
            rule = set(row['id'] for row in rows
                       if legacy_tag_rule(row['cifra'], seq))
            lines.append('| %s | %d | %d | %d | %s |' % (
                seq_id, len(base), len(actual[seq_id]), len(rule),
                'yes' if base == actual[seq_id] else 'no'))
        lines.append('')
    lines.append('## Normalization check (case-insensitive vs case-sensitive)')
    lines.append('')
    lines.append('| seq | contiguous CS | contiguous CI | set CS | set CI |')
    lines.append('|---|---:|---:|---:|---:|')
    for seq_id, seq_key, _ in SEQUENCES:
        n = normalization[seq_id]
        lines.append('| %s | %d | %d | %d | %d |' % (
            seq_id, n['contiguous_cs'], n['contiguous_ci'],
            n['set_cs'], n['set_ci']))
    lines.append('')
    lines.append('case-collision examples: %s' % json.dumps(
        dict(list(collisions.items())[:10]), ensure_ascii=False))
    lines.append('')

    output = '\n'.join(lines)
    print(output)

    if args.json_out:
        payload = {
            'csv': args.csv,
            'rows_loaded': len(rows),
            'malformed': malformed,
            'legacy_rule_disagreements': legacy_disagreements,
            'sequences': [{'id': i, 'key': k, 'chords': s}
                          for i, k, s in SEQUENCES],
            'definitions': DEFINITIONS,
            'results': results,
            'baseline': {k: sorted(v) for k, v in baseline.items()},
            'normalization': normalization,
            'case_collision_groups': len(collisions),
        }
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print('\nwrote %s' % args.json_out)


if __name__ == '__main__':
    main()
