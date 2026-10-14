# Verification v3

- Original regression baseline: 45 tests passed.
- Final suite after independent review fixes: 72 tests passed, Python 3.12.14.
- Offline candidate CLI: 5 synthetic images × 2 methods × 3 rounds = 30 planned/complete trials; 45 scripted responses (15 Single, 30 Ensemble).
- Mock winner result: MOCK_NOT_ELIGIBLE; selected_method=null.
- Shared SQLite: PRAGMA integrity_check=ok; 13,661 foods, 46 aliases.
- Packaged database SHA-256 equals user uploaded ZIP: 184878fc11046883d9c344ad321deeb8e3eff9f70f8c4a4c50ec50667e3aea49.
- DB-first arithmetic, missing-field fallback, null handling, raw/cooked mismatch, two-member mean, second-member failure, resume/retry history and truth tampering tests passed.
- No real model requests, API key, real local dataset or empirical food accuracy validated here.
- Windows PowerShell is not installed in the authoring environment; wrappers have been reviewed but not executed on native Windows.
- HTML report generated and content/links checked; installed Playwright has no browser binary, so a browser screenshot could not be rendered here.

Final independent review: no Critical issues, two Important issues fixed with regression tests, no Minor issues. Fixed joined source classification and selected-agent code/prompt integrity. Full suite passed (72/72). All five candidate CLI --help entry points passed. Current offline workflow again completed 30 trials/45 responses and correctly rejected mock selection. Archive extraction validation is recorded below.

Archive extraction validation: ZIP CRC passed; fresh extracted workspace passed all 72 tests and candidate.check. Its offline CLI again generated 30 complete trials, 45 scripted calls and MOCK_NOT_ELIGIBLE. No machine-specific prepared manifests or authoring run records are shipped; local selection is generated on your machine.

2026-10-14 repair: a truncated prior delivery was detected (missing ZIP central directory). Rebuilt compact standard-DEFLATE archive from the validated source workspace, with the full original SQLite database. No inference code changed. Redundant original USDA ZIP bundles omitted. Fresh extraction/test and post-save checks follow.

Fresh compact archive extracted successfully; all 72 tests passed again and candidate.check confirmed all 13,661 foods and SQLite integrity.

Windows SQLite cleanup fix: user log on Python 3.14.3 showed WinError 32 for three test cases. sqlite3 connection context managers committed/rolled back but did not close connections. Added contextlib.closing around transient connections while preserving import/test-write transactions. Closed the synthetic HTTPError fixture as test cleanup. Added four lifecycle regression tests covering real SQLite handles, rollback/commit, and every reported error case. These tests failed before the fix and passed afterward. Full suite now 76/76 on Python 3.12.14; native Windows rerun remains required. Database contents/checksum unchanged. Use a new RunId after this code update.

Groq HTTP client update: observed Cloudflare 1010 response; explicit application User-Agent and Accept headers, safe classification, HTTP response closure and first-denial circuit breaker. Four new regressions RED→GREEN; full suite 80/80. Live access after the change remains unverified.
