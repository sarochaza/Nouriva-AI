"""Frozen inference runner: only image manifest and truth hash enter this process."""
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path
from candidate.client import CandidateClient, build_prompt
from candidate.pipeline import COMPLETE, predict
from candidate.schema import VERSION
from nutrition_engine.ingredient_matcher import IngredientMatcher
from scripts.run_experiment import validate_manifest
from src.ai import APIError, PredictionError
from src.common import ROOT, load_json, save_json, sha256, utcnow, file_error_details

METHODS = ('single', 'ensemble2')


def load_config(path=None):
    config = load_json(path or ROOT / 'config/candidate.json')
    validate_config(config)
    return config


def validate_config(config):
    if config.get('rounds') != 3 or config.get('methods') != list(METHODS):
        raise ValueError('Candidate experiment requires three rounds and only single/ensemble2')
    models = config.get('ensemble_models')
    if not isinstance(models, list) or len(models) != 2 or any(not isinstance(m, str) or not m for m in models):
        raise ValueError('Exactly two ensemble model IDs are required')
    single = config.get('single_model')
    if not isinstance(single, str) or not single:
        raise ValueError('single_model is required')
    mode = config.get('ensemble_mode')
    if mode == 'self_consistency':
        if len(set(models + [single])) != 1:
            raise ValueError('Controlled self-consistency uses the same vision model for both methods')
    elif mode == 'multi_model':
        if len(set(models)) != 2:
            raise ValueError('multi_model needs two distinct verified vision model IDs')
    else:
        raise ValueError('Unknown ensemble_mode')
    if not set(models + [single]) <= set(config.get('vision_confirmed_models', [])):
        raise ValueError('Every candidate model must have confirmed vision support')
    temp = config.get('temperature')
    if isinstance(temp, bool) or not isinstance(temp, (int, float)) or not math.isfinite(temp) or not 0 < temp <= 2:
        raise ValueError('Use a finite temperature >0 and <=2 for independent sampling')
    if config.get('fallback_policy') != 'database_per_field_then_ai_estimate_then_null':
        raise ValueError('Unexpected fallback policy')
    if config.get('aggregation') != 'arithmetic_mean_of_two_independently_calculated_contributions':
        raise ValueError('Unexpected two-member aggregation policy')
    for rates in config.get('api', {}).get('prices', {}).values():
        for field in ('input_usd_per_million', 'output_usd_per_million'):
            val = rates.get(field)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
                raise ValueError('Invalid configured token price')


def database_path(config):
    path = Path(config['database_path']).expanduser()
    return path if path.is_absolute() else ROOT / path


def code_hashes():
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p)
            for folder in ('candidate', 'src', 'nutrition_engine', 'scripts', 'fixtures', 'evaluation')
            for p in sorted((ROOT / folder).rglob('*.py'))}


def fingerprint(prepared, config, matcher, manifest):
    seal = load_json(Path(prepared) / 'truth_integrity.json')
    value = {'schema_version': 3, 'mode': manifest['mode'], 'config': config,
             'manifest_sha256': sha256(Path(prepared) / 'manifest.json'),
             'truth_sha256': seal['sha256'], 'database_sha256': sha256(matcher.path),
             'code_sha256': code_hashes(), 'prompt_version': VERSION,
             'prompt_sha256': hashlib.sha256(build_prompt(matcher).encode()).hexdigest(),
             'images': manifest['images'], 'rounds': 3, 'methods': list(METHODS), 'seed': manifest['seed']}
    value['fingerprint'] = hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return value


def run(prepared, config, run_dir, mock=False, rounds=None, methods=None, retry_failed=False, client_factory=None):
    validate_config(config)
    prepared, run_dir = Path(prepared), Path(run_dir)
    manifest = load_json(prepared / 'manifest.json')
    validate_manifest(manifest, mock)
    rounds = [1, 2, 3] if rounds is None else rounds
    methods = list(METHODS) if methods is None else methods
    if not rounds or len(set(rounds)) != len(rounds) or any(r not in (1, 2, 3) for r in rounds):
        raise ValueError('Rounds must be unique selections from 1,2,3')
    if not methods or len(set(methods)) != len(methods) or any(m not in METHODS for m in methods):
        raise ValueError('Methods must be single/ensemble2 without duplicates')
    matcher = IngredientMatcher(database_path(config), config['source_priority'])
    count = 0
    try:
        freeze = fingerprint(prepared, config, matcher, manifest)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / 'frozen.json'
        if path.exists():
            if load_json(path)['fingerprint'] != freeze['fingerprint']:
                raise ValueError('Frozen run changed: use a new RunId after changing config/code/DB/selection')
        else:
            save_json(path, {**freeze, 'created_at': utcnow()})
        for rnd in rounds:
            for idx, image in enumerate(manifest['images']):
                order = methods if (rnd + idx) % 2 else list(reversed(methods))
                for method in order:
                    output = run_dir / 'records' / ('round_' + str(rnd)) / (image['dish_id'] + '_' + method + '.json')
                    previous = load_json(output) if output.exists() else None
                    if previous and (previous['status'] in COMPLETE or not retry_failed):
                        continue
                    if previous:
                        save_json(output.parent / 'history' / (output.stem + '_' + str(previous.get('trial_attempt', 1)) + '.json'), previous)
                    if client_factory:
                        client = client_factory()
                    elif mock:
                        from fixtures.candidate_mock import MockCandidateClient
                        client = MockCandidateClient()
                    else:
                        client = CandidateClient(config['api'], matcher)
                    start = time.perf_counter()
                    record = {'schema_version': 3, 'mode': freeze['mode'], 'round': rnd, 'method': method,
                              'dish_id': image['dish_id'], 'fingerprint': freeze['fingerprint'],
                              'status': 'FAILED', 'started_at': utcnow(), 'prediction': None, 'nutrition': None,
                              'nominal_model_calls': 1 if method == 'single' else 2,
                              'trial_attempt': previous.get('trial_attempt', 1) + 1 if previous else 1,
                              'error_type': 'IN_PROGRESS', 'error': 'Unfinished trial'}

                    def checkpoint():
                        record['call_metadata'] = (previous.get('call_metadata', []) if previous else []) + list(client.events)
                        record['latency_seconds'] = time.perf_counter() - start
                        record['cumulative_latency_seconds'] = record['latency_seconds'] + (previous.get('cumulative_latency_seconds', 0) if previous else 0)
                        save_json(output, record)

                    client.on_event = checkpoint
                    checkpoint()
                    interrupted = False
                    try:
                        result = predict(image['image_path'], method, config, client, matcher)
                        record.update(result)
                        record.update(status=result['nutrition']['status'], error_type=None, error=None)
                    except (APIError, PredictionError, ValueError) as exc:
                        record.update(error_type='API_ERROR' if isinstance(exc, APIError) else 'PREDICTION_ERROR', error=str(exc))
                    except KeyboardInterrupt:
                        interrupted = True
                        record.update(error_type='INTERRUPTED', error='Interrupted; attempts kept. Resume with --retry-failed.')
                    except Exception as exc:
                        record.update(error_type='INTERNAL_ERROR', error=type(exc).__name__,
                                      error_details=file_error_details(exc))
                    record['current_attempt_call_count'] = len(client.events)
                    checkpoint()
                    count += 1
                    print(f"[{record['mode']}] round={rnd} {image['dish_id']} {method}: {record['status']} calls={len(client.events)}", flush=True)
                    if interrupted:
                        raise KeyboardInterrupt
                    if not mock and record['status']=='FAILED' and any(e.get('http_status') in (401,403) for e in client.events):
                        save_json(run_dir/'run_status.json',{'status':'STOPPED_ACCESS_DENIED',
                                  'saved_trials_this_invocation':count,'error':record['error'],
                                  'reason':'Resolve API authentication/access before continuing; remaining trials were not called.'})
                        print('STOPPED_ACCESS_DENIED: '+str(record['error']),flush=True)
                        return count
    finally:
        matcher.close()
    return count


def main():
    parser = argparse.ArgumentParser(description='Single versus exactly two independent ensemble members; inference only')
    parser.add_argument('--mode', choices=['mock', 'real'], default='mock')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--run-id', default='candidate-smoke-v3')
    parser.add_argument('--round', dest='rounds', type=int, nargs='+')
    parser.add_argument('--method', dest='methods', choices=METHODS, nargs='+')
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_id):
        parser.error('RunId must use letters, numbers, underscore or hyphen')
    config = load_config(args.config)
    mock = args.mode == 'mock'
    prepared = args.prepared or ROOT / ('fixtures/prepared-v3' if mock else 'data/prepared/smoke-v3')
    if mock and not (prepared / 'manifest.json').exists():
        from src.dataset import prepare_dataset
        from fixtures.make_fixture import make_fixture
        prepare_dataset(make_fixture(ROOT / 'fixtures/dataset'), prepared, 5, config['seed'], mock=True)
    count = run(prepared, config, ROOT / 'results' / args.mode / args.run_id, mock,
                args.rounds, args.methods, args.retry_failed)
    print(f'{count} new candidate trials written. Evaluate separately with candidate.evaluate.')


if __name__ == '__main__':
    main()
