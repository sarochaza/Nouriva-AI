"""Local preflight; network requests happen only with explicit flags."""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from contextlib import closing
from candidate.client import CandidateClient
from candidate.pipeline import predict
from candidate.run import load_config, database_path
from nutrition_engine.ingredient_matcher import IngredientMatcher
from src.ai import GroqClient, APIError, PredictionError
from src.common import read_env, save_json, sha256, ROOT


def main():
    parser = argparse.ArgumentParser(description='Check shared SQLite and candidate configuration')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--dataset-root', type=Path)
    parser.add_argument('--list-models', action='store_true', help='Authenticated network request; does not prove vision capability')
    parser.add_argument('--probe-image', type=Path, help='One actual vision request, with provisional estimates, using your key')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10+ required')
    cfg = load_config(args.config)
    db = database_path(cfg)
    if not db.is_file():
        raise SystemExit('Packaged database missing; re-extract the workspace ZIP')
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        foods = conn.execute('SELECT COUNT(*) FROM foods').fetchone()[0]
        sources = dict(conn.execute('SELECT source_id, COUNT(*) FROM foods GROUP BY source_id'))
        aliases = conn.execute('SELECT COUNT(*) FROM aliases').fetchone()[0]
    if integrity != 'ok':
        raise SystemExit('SQLite integrity failed')
    read_env()
    key = os.environ.get('GROQ_API_KEY', '')
    evidence = {'python': sys.version.split()[0], 'sqlite_integrity': integrity,
                'foods': foods, 'aliases': aliases, 'sources': sources,
                'database_sha256': sha256(db), 'api_key_present': bool(key) and not key.startswith('PASTE_'),
                'candidate_methods': cfg['methods'], 'ensemble_members': len(cfg['ensemble_models']),
                'ensemble_mode': cfg['ensemble_mode'], 'real_api_validation': 'NOT_RUN'}
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if args.dataset_root:
        if not args.dataset_root.is_dir():
            raise SystemExit('Dataset folder not found: ' + str(args.dataset_root))
        from src.dataset import load_dataset
        rows, audit = load_dataset(args.dataset_root)
        save_json(ROOT / 'data/external_dataset/local_dataset_check.json', audit)
        print(f'Valid local records: {len(rows)}, invalid: {audit["invalid_records"]}, distinct plates: {len({r["plate_group"] for r in rows})}')
        if not rows:
            raise SystemExit('No valid local rows; inspect data/external_dataset/local_dataset_check.json')
    if args.list_models:
        print('\n'.join(GroqClient(cfg['api']).list_models()))
        print('Model listing is not proof of vision support. Read the official vision documentation.')
    if args.probe_image:
        matcher = IngredientMatcher(db, cfg['source_priority'])
        client = CandidateClient(cfg['api'], matcher)
        try:
            result = predict(args.probe_image, 'single', cfg, client, matcher)
            save_json(ROOT / 'results/setup/real_vision_probe.json', {**result, 'call_metadata': client.events})
            print('One real candidate vision response received; calculation status=' + result['nutrition']['status'])
        except (APIError, PredictionError) as error:
            save_json(ROOT / 'results/setup/real_vision_probe.json',
                      {'status':'FAILED','error_type':'API_ERROR' if isinstance(error,APIError) else 'PREDICTION_ERROR',
                       'error':str(error),'call_metadata':client.events})
            raise SystemExit('Vision probe failed: '+str(error)) from None
        finally:
            matcher.close()


if __name__ == '__main__':
    main()
