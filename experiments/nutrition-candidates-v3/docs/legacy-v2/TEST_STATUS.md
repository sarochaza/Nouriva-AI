# Test status — 2026-10-13

**MOCK TEST PASSED / REAL API NOT VERIFIED**

- `python -m unittest discover -v`: 45 unique Unit/Integration/Regression tests passed. Full captured output: `test-results.txt`.
- Python 3.12.14, Linux execution environment. Core requires Python 3.10+ and stdlib only.
- Command-line Mock smoke: 5 synthetic colored-square images × 3 methods × 3 rounds = 45 completed evaluations. SUCCESS=45. 105 nominal/mock calls. Logs in `results/mock/software-validation`. These are software checks, not AI food-recognition results.
- SQLite integrity check: ok. Foods=13,661. Usable complete-core references=13,590. Measures=9,816. Recipe components=18,584.
- Source reconciliation: 54,485 populated nutrient values checked against raw USDA ZIPs. No substantive mismatches; 98 CSV-precision differences retained in audit. AUSNUT 9,816 rows reconciled against uploaded XLSX. Four provided manifest hashes verified.
- Independent read-only review completed. All four Important findings reproduced and fixed with regression tests: dry heat vs drying, final ensemble validation, common-success ingredient denominator, interrupted-call retention. Intended-use frying descriptors also handled.
- Compile check passed for all Python modules.
- Groq transport tested with injected offline HTTP responses for payload isolation, 429 retry and token retention on malformed prediction. No real service request.
- User's full local dataset not accessed. Actual publisher metadata schema inspected, fixtures conform to that schema. Loader validates the local dataset before selection.
- Windows native PowerShell runtime unavailable here. PowerShell wrappers use literal paths, direct `.venv\Scripts\python.exe`, array arguments and UTF-8 BOM for Windows PowerShell 5.1. **Native Windows execution not verified.**
- Original Thai scan not transcribed. Verified-row importer tested with synthetic human-review records, not claimed as verified Thai food values.

Packaged extraction validation is recorded in `PACKAGING_VERIFICATION.json`. Request checkpoints retain known calls on interrupt and mark unfinished trials FAILED/IN_PROGRESS. Unknown provider billing remains unknown.
