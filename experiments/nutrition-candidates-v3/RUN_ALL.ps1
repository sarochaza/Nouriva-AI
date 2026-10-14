param(
    [string]$DatasetPath = '',
    [string]$RunId = 'candidate-pilot-v3',
    [switch]$RetryFailed
)
& (Join-Path $PSScriptRoot 'START_HERE.ps1') -Mode Pilot -DatasetPath $DatasetPath -RunId $RunId -RetryFailed:$RetryFailed
