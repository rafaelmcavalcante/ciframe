#!/usr/bin/env python3
# coding: utf-8
"""Export the Big Pickle sessions of this project into a folder.

Loads the session list of the current project, exports each session and keeps
only the ones whose assistant messages were all produced by
`opencode/big-pickle` (the model required by the activity). Sessions already
exported (same session id in the filename) are skipped.

Usage (from the repo root):
  python3 scripts/export_big_pickle_sessions.py
  python3 scripts/export_big_pickle_sessions.py --out ~/outra-pasta

The exports land in docs/features/sequencias-customizadas/sessoes and are
committed with the rest of the feature docs.
"""
import argparse
import json
import os
import subprocess
import sys
import time

MODEL_PROVIDER = 'opencode'
MODEL_ID = 'big-pickle'


def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)


def list_sessions():
    return json.loads(run(['opencode', 'session', 'list', '--format', 'json']))


def export_session(session_id, path):
    """Export to a file: capturing the export through a pipe truncates it."""
    with open(path, 'w') as handle:
        subprocess.run(['opencode', 'session', 'export', session_id],
                       stdout=handle, stderr=subprocess.DEVNULL, check=True)
    with open(path) as handle:
        return json.load(handle)


def session_models(data):
    models = set()
    for message in data.get('messages', []):
        model = message.get('model')
        if model:
            models.add((model.get('providerID'), model.get('id')))
    return models


def is_big_pickle(data):
    models = session_models(data)
    return bool(models) and models == {(MODEL_PROVIDER, MODEL_ID)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='docs/features/sequencias-customizadas/sessoes')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    exported, skipped, other = [], [], []
    tmp_path = os.path.join(args.out, '.export.tmp')

    for session in list_sessions():
        session_id = session['id']
        existing = [f for f in os.listdir(args.out) if session_id in f]
        if existing:
            skipped.append((session_id, existing[0]))
            continue

        data = export_session(session_id, tmp_path)
        if not is_big_pickle(data):
            other.append((session_id, sorted(session_models(data))))
            os.remove(tmp_path)
            continue

        created = time.strftime('%Y%m%d', time.localtime(session['created'] / 1000))
        filename = 'sessao-%s-%s.json' % (created, session_id)
        os.replace(tmp_path, os.path.join(args.out, filename))
        exported.append((filename, len(data.get('messages', []))))

    for filename, count in exported:
        print('exportada  %s  (%d mensagens)' % (filename, count))
    for session_id, filename in skipped:
        print('já existia %s  (%s)' % (session_id, filename))
    for session_id, models in other:
        print('ignorada   %s  (modelos: %s)' % (session_id, models or 'nenhum'))

    if not exported and not skipped and not other:
        print('nenhuma sessão encontrada neste projeto')
    return 0 if exported or skipped else 1


if __name__ == '__main__':
    sys.exit(main())
