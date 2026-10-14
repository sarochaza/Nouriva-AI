# Implementation plan
Spec: ../specs/2026-10-13-nutrition-benchmark-design.md
Execution: inline. Isolated new directory, no existing git checkout.

## Task 1: Database and engine
Tests first for raw/cooked separation, missing != zero, no arbitrary substitutions, known-weight arithmetic and provenance. Build SQLite tables foods, aliases, measures, recipe_components and sources from audited inputs. Preserve distinct source records, collapse only identical same-source IDs and flag duplicates across sources. Verify source archives and normalized CSV against existing database.
Expected: database audit reconciles 13,661 original foods, 9,816 measures and 18,584 recipe rows; engine tests pass.

## Task 2: Dataset and predictions
Tests first for real schema fields, safe paths, ID mapping, no label access, duplicate IDs, malformed/missing labels, staged agents and two-of-three median consensus. Keep old API payload concept and safe JSON validation, expand states/evidence and record every attempt.
Expected: tests pass offline, no network inference.

## Task 3: Frozen runs and evaluation
Tests first for 45 planned evaluations, all statuses, freeze mutation rejection, resumability and metrics on known toy numbers. Separate mock from real and no zero-filling failures.
Expected: complete mock smoke 5 images x 3 methods x 3 rounds, 105 nominal calls; partial/failure tests and metric checks pass.

## Task 4: Delivery
Thai README, PowerShell scripts, source policy, audit and coverage reports, blank real result templates, fixture test output. Run unittest suite, packaged ZIP extraction smoke and fresh review. Record Windows native and real Groq limitations precisely.
Expected: deliver ZIP containing no secrets or full external image dataset.

## Review focus
Ground truth leakage through filenames/context, state mismatch, inappropriate fuzzy substitutes, missing-value propagation, partial coverage, failed API usage loss, trial freeze/resume, equal-resource reporting, Windows paths and eval exclusions.
