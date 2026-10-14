param(
    [ValidateSet('Mock', 'Setup', 'Smoke', 'Pilot', 'Evaluate', 'Analyze')]
    [string]$Mode = 'Mock',
    [string]$DatasetPath = '',
    [string]$RunId = '',
    [string]$ConfigPath = 'config\candidate.json',
    [string]$PreparedPath = '',
    [string]$MetadataPath = '',
    [string]$SchemaPath = '',
    [string]$ImagePath = '',
    [switch]$RetryFailed
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$PythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        throw 'Install Python 3.10+ and add Python to PATH.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create .venv.' }
}
function Invoke-NouraPython {
    param([string[]]$CommandArgs)
    & $PythonPath @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "Python step failed ($LASTEXITCODE). Read the message above." }
}
Invoke-NouraPython -CommandArgs @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)')
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $DatasetPath) { $DatasetPath = $Config.default_dataset_root }
Invoke-NouraPython -CommandArgs @('-m', 'candidate.check', '--config', $ConfigPath)
if ($Mode -eq 'Setup') {
    Write-Host 'Setup checked. Add GROQ_API_KEY to .env. Active config: config/candidate.json.'
    return
}
if ($Mode -eq 'Mock') {
    if (-not $RunId) { $RunId = 'mock-local-v3' }
    Invoke-NouraPython -CommandArgs @('-m', 'unittest', 'discover')
    Invoke-NouraPython -CommandArgs @('-m', 'candidate.run', '--mode', 'mock', '--config', $ConfigPath, '--run-id', $RunId)
    $MockRun = Join-Path 'results\mock' $RunId
    Invoke-NouraPython -CommandArgs @('-m', 'candidate.evaluate', '--run-dir', $MockRun, '--truth', 'fixtures\prepared-v3\ground_truth.json')
    Write-Host "Software workflow completed. No real model accuracy measured. Open $MockRun\comparison\report.html"
    return
}
$Selection = if ($Mode -eq 'Pilot') { 'pilot-v3' } else { 'smoke-v3' }
$Count = if ($Mode -eq 'Pilot') { '30' } else { '5' }
if (-not $RunId) { $RunId = "candidate-$Selection" }
if (-not $PreparedPath) { $PreparedPath = Join-Path 'data\prepared' $Selection }
$RealRun = Join-Path 'results\real' $RunId
if ($Mode -eq 'Analyze') {
    if (-not $ImagePath) { throw 'Use -ImagePath with a new local food image.' }
    $Winner = Join-Path $RealRun 'comparison\winner_selection.json'
    Invoke-NouraPython -CommandArgs @('-m', 'candidate.analyze', '--selection', $Winner, '--image', $ImagePath, '--out', (Join-Path $RealRun 'new_image_analysis.json'))
    return
}
if ($Mode -ne 'Evaluate') {
    if (-not (Test-Path -LiteralPath $DatasetPath -PathType Container)) {
        throw "Local dataset folder not found: $DatasetPath. Supply -DatasetPath. Images are not included in this ZIP."
    }
    $PrepareArgs = @('-m', 'candidate.prepare', '--dataset-root', $DatasetPath, '--count', $Count,
        '--seed', [string]$Config.seed, '--out', $PreparedPath)
    if ($MetadataPath) { $PrepareArgs += @('--metadata', $MetadataPath) }
    if ($SchemaPath) { $PrepareArgs += @('--schema', $SchemaPath) }
    Invoke-NouraPython -CommandArgs $PrepareArgs
    Write-Host "REAL API run: $Count images, 2 methods, 3 rounds. Nominal responses: $([int]$Count * 9), plus retries."
    $RunArgs = @('-m', 'candidate.run', '--mode', 'real', '--config', $ConfigPath,
        '--prepared', $PreparedPath, '--run-id', $RunId)
    if ($RetryFailed) { $RunArgs += '--retry-failed' }
    Invoke-NouraPython -CommandArgs $RunArgs
}
Invoke-NouraPython -CommandArgs @('-m', 'candidate.evaluate', '--run-dir', $RealRun,
    '--truth', (Join-Path $PreparedPath 'ground_truth.json'))
Write-Host "Open $RealRun\comparison\report.html"
Write-Host "Winner decision: $RealRun\comparison\winner_selection.json"
