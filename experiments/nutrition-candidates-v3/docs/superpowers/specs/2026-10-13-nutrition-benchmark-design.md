# Design authority
User requirements: ../.. /USER_REQUIREMENTS_TH.md. User expressly authorizes immediate implementation and questions only for essential blockers.

A local Python workspace with SQLite reference database, conservative state-aware ingredient matching, three image estimators and one deterministic calculator. Dataset preparation reads and validates local Hugging Face JSONL, selects unique plate groups with a seed, and writes separate inference manifest and private evaluation labels. Inference receives only image bytes and prior AI estimates. Invalid, partial and missing outputs are never complete estimates.

Groq adapter uses configurable vision model IDs, JSON response validation, bounded retries and redacted errors. Immutable run fingerprint covers configuration, selected image hashes, code, prompts, aliases and database. Mock runs use synthetic fixtures only and live in a different output namespace. Evaluation reports both available-case and common-success comparisons, per-round metrics and resource totals.

USDA normalized data and FSANZ measure data retained with attribution. Thai scan not redistributed or automatically transcribed. Verified-row import requires source page, reviewer, units and explicit approval.
