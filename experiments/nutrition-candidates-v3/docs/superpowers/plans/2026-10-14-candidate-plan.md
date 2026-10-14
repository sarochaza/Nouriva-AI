# Nutrition Candidate Implementation Plan

> For agentic workers: use superpowers:executing-plans inline. No per-task delegation.

Goal: package a runnable Single vs Ensemble-2 benchmark and selected nutrition agent using the ZIP database.
Architecture: candidate modules use original dataset parser, exact database matcher and instrumented Groq transport. Existing v2 modules remain reference only; root entry points run candidate v3.
Tech stack: Python 3.10+ standard library, SQLite, Windows PowerShell; offline HTML report.
Spec: docs/superpowers/specs/2026-10-14-candidate-design.md

## Global constraints
- Exactly two candidate methods, exactly two independent ensemble responses and three rounds.
- Same image prompt, DB/calculator/fallback for every method; no expected labels in inference.
- Missing values never zero. Mock never winner. No real API calls during authoring tests.

## Review focus
- Raw/cooked mismatch must fall back rather than silently use incompatible DB food.
- A failed ensemble member must remain a failed two-member trial.
- Resumes and explicit retries preserve incurred attempts and reject frozen changes.
- Local dataset split/image paths must be resolved and invalid rows reported.
- Missing ground truth and incomplete runs cannot produce a winner.

## Task 1: Prediction and shared nutrition pipeline
Files: candidate/schema.py, candidate/client.py, candidate/pipeline.py, src/ai.py (backwards-compatible parser/prompt hooks), tests/test_candidate.py.
Interfaces: validate_prediction(dict)->dict; CandidateClient(api, matcher).chat(...); calculate(items,matcher)->nutrition; combine(members,matcher)->result.
- [x] Write tests for database precedence (150g rice=195kcal), unknown 50g sauce fallback=50kcal, missing nutrient=null, averaging absent ingredient=half mass, failed member, identical image prompt without labels.
- [x] Run tests; expect feature missing failures.
- [x] Implement schema, hooks, pipeline and two-member combination.
- [x] Run candidate tests and full original suite; expect all pass.

## Task 2: Frozen runner and evaluation
Files: candidate/run.py, candidate/evaluate.py, candidate/analyze.py, candidate/check.py, config/candidate.json, tests/test_candidate_runs.py.
Interfaces: run(prepared,config,run_dir,mock=False,...)->count; evaluate(run_dir,truth)->report + selection; analyze(image,selection)->nutrition.
- [x] Write tests for 30 planned trials and 45 calls on five images/three rounds, no truth read in inference, resume/config change guards, failed second member, mock winner rejection, manual real controlled winner and identical methods=no winner.
- [x] Run tests; expect missing features.
- [x] Implement runner, evaluator with paired dish selection, selected-agent entry point and setup preflight.
- [x] Run full suite and mock CLI; expect successful software run with no selected agent.

## Task 3: User entry points and delivery
Files: START_HERE.ps1, RUN_ALL.ps1, README.md, docs/EXPERIMENT_V3_TH.md, source manifest, saved offline HTML/CSV/JSON report.
- [x] Document local dataset command, API configuration and same-model meaning.
- [x] Run mock entire workflow plus report checks, isolated ZIP extract, CLI help and SQLite hash checks.
- [x] Whole-workspace review, fix important findings with regression tests.
- [x] Package clean ZIP with data, docs and tests and save deliverable.
