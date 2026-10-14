"""Offline software fixture; no actual recognition or research accuracy."""
from candidate.schema import VERSION, validate_prediction
from src.common import sha256, utcnow


class MockCandidateClient:
    def __init__(self):
        self.events = []
        self.on_event = None

    def chat(self, model, image, stage, prior=None, temperature=0.7):
        if stage != 'candidate' or prior is not None:
            raise ValueError('Independent candidate calls only')
        grams = 100 + 20 * len(self.events)
        result = validate_prediction({'dish_name': 'MOCK colored-square software fixture',
            'ingredients': [{'name': 'Carrots, raw', 'name_th': 'แครอทดิบ', 'state': 'raw', 'grams': grams,
            'evidence': 'visible', 'confidence': 0.8, 'uncertainty': 'SCRIPTED MOCK, NOT FOOD RECOGNITION',
            'estimated_per_100g': {'kcal': 50, 'protein_g': 1, 'carbs_g': 10, 'fat_g': 0.5}}]})
        self.events.append({'model': 'MOCK:' + model, 'stage': stage, 'attempt': 1,
            'prompt_version': VERSION, 'started_at': utcnow(), 'status': 'SUCCESS',
            'latency_seconds': 0, 'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20,
            'cost_usd': 0, 'image_sha256': sha256(image)})
        if self.on_event:
            self.on_event()
        return result
