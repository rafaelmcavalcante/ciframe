#!/usr/bin/env python3
# coding: utf-8
"""Capture the current /similares responses for the six hardcoded sequences.

This is the regression baseline for migrating the sequence catalog out of
main.py's dict. It expects the app to be running (default http://localhost:8080).

Usage:
  python3 scripts/capture_baseline.py --raw-dir /tmp/baseline --fixture-dir docs/features/sequencias-customizadas/baseline

The raw directory keeps every page as returned by the API plus the manifest.
The fixture directory keeps a compact version (ordered id list per sequence plus
the manifest) that is meant to be committed.
"""
import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request

SEQS = [
    ('0', 'BmGDA', 'Bm,G,D,A'),
    ('1', 'CGAmF', 'C,G,Am,F'),
    ('2', 'EmG', 'Em,G'),
    ('3', 'CA7DmG7', 'C,A7,Dm,G7'),
    ('4', 'GmF', 'Gm,F'),
    ('5', 'CC7FFm', 'C,C7,F,Fm'),
]
MAX_PAGES = 6
CSV_PATH = 'data/top/dataset_final.csv'
DOCKER_IMAGE = 'ciframe-baseline'


def get(base_url, path):
    with urllib.request.urlopen(base_url + path, timeout=300) as r:
        body = r.read().decode('utf-8')
        return r.status, r.headers.get('Content-Type'), body


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    try:
        return subprocess.check_output(['git'] + list(args), cwd=repo, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def docker_image_id(image):
    try:
        return subprocess.check_output(
            ['docker', 'inspect', '--format', '{{.Id}}', image],
            text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def capture(base_url, repo, raw_dir, fixture_dir):
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(fixture_dir, exist_ok=True)

    status, ctype, generos_body = get(base_url, '/generos')
    with open(os.path.join(raw_dir, 'generos.json'), 'w') as f:
        f.write(generos_body)

    csv_file = os.path.join(repo, CSV_PATH)
    manifest = {
        'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'base_url': base_url,
        'commit': git(repo, 'rev-parse', 'HEAD'),
        'branch': git(repo, 'rev-parse', '--abbrev-ref', 'HEAD'),
        'docker_image': {'tag': DOCKER_IMAGE, 'id': docker_image_id(DOCKER_IMAGE)},
        'csv_path': CSV_PATH,
        'csv_sha256': sha256_bytes(open(csv_file, 'rb').read()),
        'generos': {
            'status': status,
            'content_type': ctype,
            'count': len(json.loads(generos_body)),
            'body_sha256': sha256_bytes(generos_body.encode('utf-8')),
        },
        'sequences': {},
    }

    for seq_id, key, param in SEQS:
        seq_dir = os.path.join(raw_dir, '%s_%s' % (seq_id, key))
        os.makedirs(seq_dir, exist_ok=True)
        pages = {}
        ids = []
        for pagina in range(1, MAX_PAGES + 1):
            path = '/similares?sequencia=%s&pagina=%d' % (param, pagina)
            status, ctype, body = get(base_url, path)
            with open(os.path.join(seq_dir, 'pagina_%d.json' % pagina), 'w') as f:
                f.write(body)
            items = json.loads(body)
            ids.extend(item['id_unico_musica'] for item in items)
            pages[str(pagina)] = {
                'status': status,
                'content_type': ctype,
                'count': len(items),
                'body_sha256': sha256_bytes(body.encode('utf-8')),
            }
            if not items:
                break
        manifest['sequences'][seq_id] = {
            'sequencia_param': param,
            'api_key': key,
            'pages': pages,
            'total': len(ids),
            'unique_ids': len(set(ids)),
            'ids_sha256': sha256_bytes('\n'.join(ids).encode('utf-8')),
        }
        with open(os.path.join(fixture_dir, 'seq-%s-ids.json' % seq_id), 'w') as f:
            json.dump({'sequencia_param': param, 'api_key': key, 'ids': ids},
                      f, indent=2, ensure_ascii=False)
            f.write('\n')

    for target in (raw_dir, fixture_dir):
        with open(os.path.join(target, 'manifest.json'), 'w') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write('\n')

    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8080')
    parser.add_argument('--repo', default=os.getcwd())
    parser.add_argument('--raw-dir', default='/tmp/baseline')
    parser.add_argument('--fixture-dir',
                        default='docs/features/sequencias-customizadas/baseline')
    args = parser.parse_args()

    manifest = capture(args.base_url, args.repo, args.raw_dir, args.fixture_dir)
    totals = {k: v['total'] for k, v in manifest['sequences'].items()}
    print(json.dumps(totals))
    print('generos:', manifest['generos']['count'])


if __name__ == '__main__':
    main()
