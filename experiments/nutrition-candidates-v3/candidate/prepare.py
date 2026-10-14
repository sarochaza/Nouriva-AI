"""Prepare or safely reuse the same fixed local images and sealed expected values."""
import argparse
from pathlib import Path
from scripts.run_experiment import validate_manifest
from src.common import ROOT, load_json, save_json, sha256
from src.dataset import prepare_dataset


def prepare(dataset_root, out, count=5, seed=20261014, metadata=None, fields=None, mock=False):
    root, out = Path(dataset_root).expanduser().resolve(), Path(out)
    if not mock and (root / 'SYNTHETIC_TEST_ONLY.txt').exists():
        raise ValueError('Synthetic fixtures cannot be prepared as a real experiment')
    source = {'dataset_root': str(root), 'count': count, 'seed': seed,
              'explicit_metadata': str(Path(metadata).resolve()) if metadata else None,
              'explicit_fields': fields, 'mode': 'MOCK' if mock else 'REAL'}
    if (out / 'manifest.json').exists():
        prior = load_json(out / 'preparation_source.json') if (out / 'preparation_source.json').exists() else None
        if prior != source:
            raise ValueError('Prepared selection belongs to different inputs; choose a new --out / -PreparedPath')
        audit = load_json(out / 'dataset_audit.json')
        if sha256(audit['metadata_path']) != audit['metadata_sha256']:
            raise ValueError('Local metadata changed after preparation; choose a new prepared directory')
        if sha256(out / 'ground_truth.json') != load_json(out / 'truth_integrity.json')['sha256']:
            raise ValueError('Prepared ground truth changed')
        manifest = load_json(out / 'manifest.json')
        validate_manifest(manifest, mock)
        return manifest['images'], audit
    images, audit = prepare_dataset(root, out, count, seed, metadata, fields, mock)
    save_json(out / 'preparation_source.json', source)
    return images, audit


def main():
    parser = argparse.ArgumentParser(description='Select fixed local test images; no downloading or inference')
    parser.add_argument('--dataset-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'data/prepared/smoke-v3')
    parser.add_argument('--count', type=int, choices=[5, 30], default=5)
    parser.add_argument('--seed', type=int, default=20261014)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--schema', type=Path)
    args = parser.parse_args()
    images, audit = prepare(args.dataset_root, args.out, args.count, args.seed, args.metadata,
                            load_json(args.schema) if args.schema else None)
    print(f'Prepared/reused {len(images)} fixed images. Valid metadata rows={audit["valid_records"]}; invalid={audit["invalid_records"]}')
    print('Manifest: ' + str(args.out / 'manifest.json'))
    print('Expected labels: ' + str(args.out / 'ground_truth.json'))


if __name__ == '__main__':
    main()
