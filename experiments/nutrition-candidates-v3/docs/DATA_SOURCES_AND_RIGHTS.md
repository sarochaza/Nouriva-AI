# Data sources, attribution and redistribution

Checked 2026-10-13. This document records the actual packaged data sources. It does not grant rights to unrelated images or third-party material.

| Source | Use in this workspace | Rights evidence | Included |
|---|---|---|---|
| USDA FoodData Central SR Legacy 2018-04 | Ingredient references | USDA states public domain, CC0 1.0 | Original user-supplied USDA ZIP and derived reference data |
| USDA Foundation 2025-12 | Ingredient references | Same USDA policy | Original user-supplied ZIP and derived data; negative source carbs quarantined |
| USDA FNDDS 2021–2023, downloaded archive 2024-10-31 | Food references and recipe component support | Same USDA policy | Original user-supplied ZIP, derived recipes and NDB crosswalk |
| FSANZ AUSNUT 2023 Food measures | Portion weights and volumes, not nutrients | FSANZ copyright page defaults to CC BY 4.0 except logos and third-party material | User-supplied measure CSV transformed into SQLite. No FSANZ logo or original XLSX distributed |
| Food Composition Table of Thai Foods, September 2018 | Future manually verified Thai rows | Uploaded scan did not establish an explicit redistribution licence | No original PDF or unverified transcription distributed. Only its title/hash and empty import template |
| Hugging Face mmathys/food-nutrients | Local image benchmark and source labels | Dataset card uses the generic tag `cc`, without a precise CC variant on the inspected card | No real images or labels redistributed. Loader operates on the user's local copy |
| Synthetic fixture | Software and arithmetic tests | Created for this workspace | Five colored-square PNGs and synthetic test labels only |

USDA attribution: U.S. Department of Agriculture, Agricultural Research Service. FoodData Central. Source type and release are retained per row.

FSANZ attribution: Food Standards Australia New Zealand. AUSNUT 2023 Food measures. Modified into a normalized SQLite portion table. This use does not imply FSANZ endorsement. The general policy excludes third-party material. Follow any more specific restrictions attached to particular records before publishing a derived external dataset.

Primary source URLs:

- [USDA API Guide, Licensing](https://fdc.nal.usda.gov/api-guide/)
- [USDA downloadable data](https://fdc.nal.usda.gov/download-datasets/)
- [FSANZ AUSNUT 2023 data files](https://www.foodstandards.gov.au/science-data/food-nutrient-databases/ausnut/data-files)
- [FSANZ copyright](https://www.foodstandards.gov.au/legal-policies/copyright)
- [Dataset card](https://huggingface.co/datasets/mmathys/food-nutrients)
- [Publisher metadata.jsonl](https://huggingface.co/datasets/mmathys/food-nutrients/blob/main/metadata.jsonl)
- [Groq Vision and JSON mode](https://console.groq.com/docs/vision)

The old workspace's Nutrition5k README reports CC BY 4.0 for original Nutrition5k. That statement alone is not treated as proof of the precise licence of every transformed Hugging Face distribution. This package does not download or repackage either image dataset.

Source manifests are hash evidence supplied with the data and checked against the actual uploaded files. Release labels and download filenames are retained separately. A file called `survey_food_csv_2024-10-31` contains FNDDS 2021–2023 records, not a new nutrient reference period inferred from its filename.

Compact repaired delivery: the original USDA ZIP archives are not bundled in this edition. Derived CSV/SQLite data and attribution remain included. Source ZIPs can be copied from the user original archive when raw-source reconciliation is required.
