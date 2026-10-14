"""Fixed pre-registered prompts. Ground truth and reference nutrition never enter a prompt."""
VERSION='noura-image-ingredients-v2.0'
COMMON='''You estimate ingredients and serving mass from a food photograph for research.
Return only a JSON object. Do not return calories, protein, carbohydrate, fat or nutrient reference values.
Use English ingredient names, optional Thai names. Be precise about species, cut and preparation when visibly supported.
Do not invent a precise species, cut, sauce or variety that cannot be identified. Use state unspecified when uncertain.
Mass in grams means edible weight AS PRESENTED, not uncooked dry weight of a cooked ingredient.
Allowed states: raw, cooked, fried, boiled, roasted, steamed, grilled, baked, dried, unspecified.
Distinguish evidence visible (directly seen), inferred (plausible hidden oil/sauce), uncertain (unclear identity).
Each ingredient must include name, name_th (may be empty), state, grams, evidence, confidence (0..1), uncertainty (text).
Avoid duplicate ingredients and distinguish cooking oil from intrinsic food fat. Do not double count oil already in a composite food.
Schema: {"dish_name":"description","ingredients":[{"name":"ingredient","name_th":"","state":"raw","grams":100,"evidence":"visible","confidence":0.7,"uncertainty":"portion estimated from image"}]}.
Do not ask for labels, actual measured weights, image filenames or external ground truth.
'''
TASKS={
 'single':'Identify the ingredients and estimate their serving masses from this image.',
 'vision':'Vision Agent: identify visible components and plausible hidden additions. Give initial rough mass estimates and uncertainty.',
 'portion':'Portion Agent: independently examine the image and refine ingredient serving masses. The prior Vision estimate is fallible. You may correct identities and preparation. Explain uncertainty in the JSON fields.',
 'critic':'Critic Agent: inspect the image, then review both prior AI estimates for identity errors, implausible mass, incompatible preparation and double counting. Return the corrected final ingredient JSON.',
 'ensemble':'Identify the ingredients and estimate their serving masses from this image independently.'
}
