# Windows SQLite cleanup patch

This patch fixes unclosed transient SQLite connections responsible for WinError 32 in test_ambiguous_measure_requires_review, test_negative_source_nutrient_quarantined_not_zero and test_verified_thai_name_searchable. It preserves transaction commits/rollbacks.

Extract this PATCH zip directly into your existing Noura-Nutrition-Agent-Candidates-v3 project folder (overwrite listed code/test files). No .env, datasets, config or nutrition database files are included.

Then run:
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Mock -RunId mock-windows-fixed-v1

Use a new RunId for existing frozen runs because code hashes changed. Current Linux verification: 76 tests pass, including 4 real connection-lifecycle regressions. Native Windows rerun and real API remain unverified here. Expected FAILED lines inside simulation tests do not mean the overall test suite failed; check the final OK/FAILED summary.
