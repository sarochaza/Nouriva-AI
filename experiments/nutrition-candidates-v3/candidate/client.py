"""Same image prompt and instrumented transport for all candidate members."""
import json
from src.ai import GroqClient
from candidate.schema import VERSION, parse_prediction

PROMPT = '''Estimate the ingredients and edible serving mass in this food photograph for a research pilot.
Return a single JSON object, no markdown. Do not ask for true weights or labels.
Mass is grams AS PRESENTED in the photograph (cooked rice mass is not uncooked dry mass).
Use English ingredient names and optionally Thai names. Identify preparation only when supported.
Allowed states: raw, cooked, fried, boiled, roasted, steamed, grilled, baked, dried, unspecified.
Distinguish directly visible ingredients, inferred hidden oil/sauces, and uncertain identities.
Do not invent a precise species/cut/variety when the image cannot identify it. Explain uncertainty.
Avoid duplicate ingredients and do not double-count oil included in a composite ingredient.
For each ingredient provide PROVISIONAL nutrient estimates per 100g of that preparation:
kcal, protein_g, carbs_g, fat_g. These estimates are uncertain: use null if unable to estimate.
A local database will override each available nutrient; provisional estimates are only a fallback.
Never claim your estimates are measured or database values. Do not return a self-calculated meal total.
Schema: {"dish_name":"description","ingredients":[{"name":"ingredient","name_th":"",
"state":"cooked","grams":100,"evidence":"visible","confidence":0.7,
"uncertainty":"identity and mass estimated from image",
"estimated_per_100g":{"kcal":130,"protein_g":2.7,"carbs_g":28,"fat_g":0.3}}]}.
Each evidence value is visible, inferred, or uncertain. Confidence is a number 0..1.
The following small catalog lists reviewed local names/states, without nutrient values.
Use a listed identity ONLY if it actually describes the photographed ingredient/preparation.
If it does not match, use your own precise name/state; never force a wrong database match.
'''


def build_prompt(matcher):
    catalog = {}
    for (alias, state), links in sorted(matcher.aliases.items()):
        if alias.isascii():
            for link in links:
                food = matcher.by_id[link['food_id']]
                catalog[(food['food_id'], state)] = {'name': food['name_en'], 'state': state,
                                                  'alias': alias}
    return PROMPT + json.dumps(list(catalog.values()), ensure_ascii=False)


class CandidateClient(GroqClient):
    def __init__(self, api, matcher, transport=None, sleep=None):
        prompt = build_prompt(matcher)

        def prompt_builder(stage, prior):
            if stage != 'candidate' or prior is not None:
                raise ValueError('Candidate members must be independent with no prior prediction')
            return prompt

        super().__init__(api, transport, sleep, prediction_parser=parse_prediction,
                         prompt_builder=prompt_builder, prompt_version=VERSION)
