"""Prediction schema with provisional nutrition values, never expected labels."""
import json
import math
from src.ai import PredictionError, validate_prediction as validate_ingredients

CORE = ('kcal', 'protein_g', 'carbs_g', 'fat_g')
VERSION = 'noura-candidate-image-v3.0'


def validate_prediction(value):
    result = validate_ingredients(value)
    for original, item in zip(value['ingredients'], result['ingredients']):
        estimate = original.get('estimated_per_100g')
        if estimate is None:
            estimate = dict.fromkeys(CORE)
        if not isinstance(estimate, dict):
            raise PredictionError('estimated_per_100g must be an object or null')
        clean = {}
        for field in CORE:
            v = estimate.get(field)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or
                                  not math.isfinite(v) or not 0 <= v <= (1000 if field == 'kcal' else 100)):
                raise PredictionError('Invalid provisional per-100g value: ' + field)
            clean[field] = float(v) if v is not None else None
        macros = [clean[k] for k in CORE[1:]]
        if all(v is not None for v in macros) and sum(macros) > 105:
            raise PredictionError('Provisional macros exceed edible mass per 100g')
        item['estimated_per_100g'] = clean
    return result


def parse_prediction(text):
    try:
        value = json.loads(text, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        return validate_prediction(value)
    except json.JSONDecodeError as exc:
        raise PredictionError(f'Invalid candidate prediction JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}') from exc
    except (ValueError, TypeError) as exc:
        raise PredictionError('Invalid candidate prediction JSON') from exc
