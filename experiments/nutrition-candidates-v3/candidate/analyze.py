"""Reuse a real selected pilot nutrition candidate without any ground truth."""
import argparse
import hashlib
from pathlib import Path
from candidate.client import CandidateClient, build_prompt
from candidate.pipeline import predict
from candidate.run import database_path, validate_config, code_hashes
from candidate.schema import VERSION
from nutrition_engine.ingredient_matcher import IngredientMatcher
from src.common import load_json, save_json, sha256, utcnow
from src.dataset import verify_image


class NutritionAgent:
    def __init__(self, selection_path):
        self.selection = load_json(selection_path)
        if self.selection.get('mode') != 'REAL' or self.selection.get('status') != 'SELECTED_FOR_PILOT' or self.selection.get('selected_method') not in ('single', 'ensemble2'):
            raise ValueError('A real candidate must pass selection criteria before reuse as the nutrition agent')
        self.config = self.selection['agent_config']
        validate_config(self.config)
        path = database_path(self.config)
        if sha256(path) != self.selection.get('database_sha256'):
            raise ValueError('Selected database changed. Repeat the experiment with a new RunId.')
        if self.selection.get('prompt_version') != VERSION or self.selection.get('code_sha256') != code_hashes():
            raise ValueError('Selected implementation or prompt version changed. Repeat the experiment with a new RunId.')
        self.matcher = IngredientMatcher(path, self.config['source_priority'])
        current_prompt = hashlib.sha256(build_prompt(self.matcher).encode()).hexdigest()
        if current_prompt != self.selection.get('prompt_sha256'):
            self.matcher.close()
            raise ValueError('Selected image prompt changed. Repeat the experiment with a new RunId.')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.matcher.close()

    def analyze(self, image, client=None):
        image = Path(image)
        verify_image(image)
        client = client or CandidateClient(self.config['api'], self.matcher)
        method = self.selection['selected_method']
        result = predict(image, method, self.config, client, self.matcher)
        return {**result, 'method': method, 'usage': 'SELECTED_PILOT_NUTRITION_AGENT',
                'created_at': utcnow(), 'image_sha256': sha256(image),
                'selection_fingerprint': self.selection.get('fingerprint'),
                'call_metadata': client.events,
                'limitations': 'Ingredients/grams from images and fallback nutrients are estimates, not measurements.'}


def main():
    parser = argparse.ArgumentParser(description='Run the selected nutrition agent on a new local image')
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('results/new_image_analysis.json'))
    args = parser.parse_args()
    with NutritionAgent(args.selection) as agent:
        result = agent.analyze(args.image)
    save_json(args.out, result)
    print('Method: ' + result['method'])
    print('Status: ' + result['nutrition']['status'])
    print('Nutrition: ' + str(result['nutrition']['nutrients']))
    print('Saved: ' + str(args.out))


if __name__ == '__main__':
    main()
