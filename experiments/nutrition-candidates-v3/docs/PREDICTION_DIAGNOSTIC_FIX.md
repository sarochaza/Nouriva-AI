# Prediction and Windows file diagnostics patch

Apply after the running experiment has finished. This patch adds specific schema
failure messages and safe file error details. It does not change the prompt,
model, database, nutrient calculation, schema acceptance rules, ensemble size,
or selection thresholds. Previously saved failures cannot reveal the original
raw response because that response was not retained.

The JSON writer uses a closed, unique temporary file in the destination folder
and makes at most seven replacement attempts on PermissionError, waiting up to
1.26 seconds in total. Other OS errors are propagated without retry. Permanent
file failures still fail. A file checkpoint failure after an API response no
longer triggers a network retry or another paid request.

## PowerShell: apply in the existing project folder

Download Noura-Prediction-Diagnostic-Fix.zip to Downloads. Stop any other process
that writes this project's results before applying. You can first preserve the
current code for the frozen v2 run:

```powershell
$backup = Join-Path $PWD.Path ("backups\before-diagnostic-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item .\src, .\candidate, .\tests -Destination $backup -Recurse
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Noura-Prediction-Diagnostic-Fix.zip" -DestinationPath $PWD.Path -Force
.\.venv\Scripts\python.exe -m unittest discover -q
if ($LASTEXITCODE -ne 0) { throw 'Local tests failed; inspect the output before making API calls.' }
```

## One-image probe first (real API usage)

```powershell
$manifest = Get-Content -LiteralPath '.\data\prepared\smoke-v3\manifest.json' -Raw | ConvertFrom-Json
$nouraImage = ($manifest.images | Where-Object { $_.dish_id -eq 'dish_1561491121' }).image_path
if (-not $nouraImage) { throw 'Selected dish was not found in the prepared manifest.' }
.\.venv\Scripts\python.exe -m candidate.check --probe-image "$nouraImage"
Get-Content -LiteralPath '.\results\setup\real_vision_probe.json' -Raw | ConvertFrom-Json |
    Select-Object status, error_type, error | Format-List
```

A successful new response does not establish why an older response failed.
If a probe fails, inspect its specific error and call_metadata validation_error.
For example, a missing uncertainty field differs from invalid JSON syntax or
an out-of-range per-100g estimate. Diagnose that actual message before changing
acceptance rules or the prompt.

## Fresh run after diagnostics are resolved

Code hashes are frozen. After this patch use a NEW RunId; the old smoke-real-v2
cannot be resumed using changed code. Its records and report remain available.

```powershell
powershell -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Smoke -DatasetPath 'C:\Users\CHOMP2O\food-nutrients' -RunId smoke-real-v3
```

This makes nominally 45 real responses plus retries. Choose the new run only
after the one-image diagnosis. Mock verifies the workflow and cannot select a
nutrition agent. Failed trials have missing accuracy values, never zero error.

## Validation

88 automated tests pass on Linux, including simulated temporary/permanent file
replacement failures, preserving old records, not retrying non-permission OS
errors, preserving billed usage on schema failures, saving probe failure details,
and not issuing another API call on a checkpoint PermissionError. Native Windows
and real responses require your local run; they are not claimed as tested here.
