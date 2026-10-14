"""Shared DB-first calculation and exactly two independent member aggregation."""
from candidate.schema import CORE, validate_prediction
from nutrition_engine.calculator import CORE as DB_FIELDS
from nutrition_engine.normalization import identity

COMPLETE = ('COMPLETE_DATABASE', 'COMPLETE_WITH_ESTIMATES')


def calculate(ingredients, matcher):
    pred = validate_prediction({'ingredients': ingredients})
    rows = []
    for item in pred['ingredients']:
        match = matcher.match(item['name'], item['state'])
        food = match['food'] if match['status'] == 'MATCHED' else None
        per_100g, contribution, sources = {}, {}, {}
        for field in CORE:
            db_value = food[DB_FIELDS[field]] if food else None
            value = db_value if db_value is not None else item['estimated_per_100g'][field]
            per_100g[field] = value
            sources[field] = 'DATABASE' if db_value is not None else ('AI_ESTIMATE' if value is not None else 'MISSING')
            contribution[field] = item['grams'] / 100 * value if value is not None else (0.0 if item['grams'] == 0 else None)
        key = 'food:' + food['food_id'] if food else identity(item['name']) + '|' + item['state']
        if any(row['identity'] == key for row in rows):
            raise ValueError('Duplicate canonical ingredient in one member; would double count')
        rows.append({'identity': key, 'prediction': item, 'grams': item['grams'], 'basis_g': 100,
                     'food_id': food['food_id'] if food else None, 'source_id': food['source_id'] if food else None,
                     'source_food_id': food['source_food_id'] if food else None,
                     'reference_name': food['name_en'] if food else None,
                     'reference_state': food['state'] if food else None,
                     'provenance': food['provenance'] if food else None,
                     'match_status': match['status'], 'match_reason': match['reason'],
                     'match_candidates': match.get('candidates', []), 'per_100g': per_100g,
                     'nutrient_sources': sources, 'contribution': contribution,
                     'uncertainty': item['uncertainty']})
    return summarize(rows)


def summarize(rows):
    totals = {k: None if any(r['contribution'][k] is None for r in rows)
              else round(sum(r['contribution'][k] for r in rows), 6) for k in CORE}
    complete = all(v is not None for v in totals.values())
    estimated = any('AI_ESTIMATE' in source.split('+')
                    for r in rows for source in r['nutrient_sources'].values())
    status = 'INCOMPLETE' if not complete else ('COMPLETE_WITH_ESTIMATES' if estimated else 'COMPLETE_DATABASE')
    total_mass = sum(r['grams'] for r in rows)
    # Mixed ensemble rows carry per-field source combinations as strings.
    db_mass = sum(r['grams'] * r.get('database_fraction',
                  sum(v == 'DATABASE' for v in r['nutrient_sources'].values()) / 4) for r in rows)
    db_only_mass = sum(r['grams'] for r in rows if all(v == 'DATABASE' for v in r['nutrient_sources'].values()))
    return {'status': status, 'complete': complete, 'nutrients': totals if complete else None,
            'partial_nutrients': totals, 'ingredients': rows, 'total_estimated_mass_g': total_mass,
            'database_mass_coverage': db_mass / total_mass if total_mass else None,
            'database_only_mass_coverage': db_only_mass / total_mass if total_mass else None,
            'fallback_ingredient_count': sum(any('AI_ESTIMATE' in v for v in r['nutrient_sources'].values()) for r in rows),
            'predicted_ingredient_count': len(rows)}


def combine(predictions, matcher):
    if len(predictions) != 2:
        raise ValueError('Ensemble candidate requires exactly two independent members')
    predictions = [validate_prediction(p) for p in predictions]
    members = [calculate(p['ingredients'], matcher) for p in predictions]
    maps = [{r['identity']: r for r in m['ingredients']} for m in members]
    merged, trace, ingredients = [], [], []
    for key in sorted(set(maps[0]) | set(maps[1])):
        present = [m[key] for m in maps if key in m]
        representative = present[0]
        grams = sum(r['grams'] for r in present) / 2
        contributions = {}
        source_labels = {}
        effective = {}
        for field in CORE:
            values = [m[key]['contribution'][field] if key in m else 0.0 for m in maps]
            contributions[field] = sum(values) / 2 if all(v is not None for v in values) else None
            source_labels[field] = '+'.join(sorted({r['nutrient_sources'][field] for r in present}))
            effective[field] = contributions[field] * 100 / grams if contributions[field] is not None and grams else None
        item = {**representative['prediction'], 'grams': grams,
                'confidence': sum(r['prediction']['confidence'] for r in present) / 2,
                'estimated_per_100g': effective,
                'evidence': representative['prediction']['evidence'] if len(present) == 2 and
                    present[0]['prediction']['evidence'] == present[1]['prediction']['evidence'] else 'uncertain',
                'uncertainty': 'Two-member mean; absent identity contributes 0g. ' +
                    '; '.join(r['prediction']['uncertainty'] for r in present)}
        db_weight = sum(r['grams'] * sum(v == 'DATABASE' for v in r['nutrient_sources'].values()) / 4 for r in present) / 2
        merged.append({**representative, 'prediction': item, 'grams': grams, 'contribution': contributions,
                       'per_100g': effective, 'nutrient_sources': source_labels,
                       'database_fraction': db_weight / grams if grams else 0,
                       'uncertainty': item['uncertainty'], 'support_count': len(present),
                       'member_rows': [m.get(key) for m in maps]})
        ingredients.append(item)
        trace.append({'identity': key, 'support_count': len(present),
                      'member_grams': [m[key]['grams'] if key in m else 0 for m in maps], 'mean_grams': grams})
    return {'prediction': {'dish_name': predictions[0]['dish_name'], 'ingredients': ingredients},
            'nutrition': summarize(merged), 'members': [{'prediction': p, 'nutrition': n}
                for p, n in zip(predictions, members)], 'merge_trace': trace}


def predict(image, method, config, client, matcher):
    if method == 'single':
        pred = client.chat(config['single_model'], image, 'candidate', temperature=config['temperature'])
        pred = validate_prediction(pred)
        return {'prediction': pred, 'nutrition': calculate(pred['ingredients'], matcher),
                'members': [], 'merge_trace': []}
    if method != 'ensemble2':
        raise ValueError('Candidate method must be single or ensemble2')
    # Sequential HTTP requests avoid rate bursts; no output from one enters the other prompt.
    models = config['ensemble_models']
    if len(models) != 2:
        raise ValueError('Exactly two configured ensemble members required')
    pred = [client.chat(model, image, 'candidate', temperature=config['temperature']) for model in models]
    return combine(pred, matcher)
