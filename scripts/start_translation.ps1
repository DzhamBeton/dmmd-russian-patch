param(
    [string]$Model = "qwen3.5:9b",
    [int]$BatchSize = 4,
    [int]$Context = 8192,
    [int]$Limit = 0
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $ProjectRoot "translations\source.jsonl"
$Output = Join-Path $ProjectRoot "translations\ru-machine.jsonl"
$ReviewedSeed = Join-Path $ProjectRoot "translations\early-reviewed.jsonl"
$LogDirectory = Join-Path $ProjectRoot "logs"
$Stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Log = Join-Path $LogDirectory "translation_$Stamp.log"

New-Item -ItemType Directory -Force $LogDirectory | Out-Null
Set-Location $ProjectRoot

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama was not found in PATH. Start or install Ollama first."
}
if (-not (Test-Path -LiteralPath $Source)) {
    throw "Source catalog was not found: $Source"
}
if (-not (Test-Path -LiteralPath $Output) -and (Test-Path -LiteralPath $ReviewedSeed)) {
    Copy-Item -LiteralPath $ReviewedSeed -Destination $Output
    Write-Host "Seeded output with the existing reviewed early scenes."
}

Write-Host "Model: $Model"
Write-Host "Output: $Output"
Write-Host "Log: $Log"
Write-Host "Stop with Ctrl+C. Run again to resume from the output and cache."

$Arguments = @(
    "-u", "scripts\translate_ollama.py",
    $Source, $Output,
    "--model", $Model,
    "--batch-size", $BatchSize,
    "--num-ctx", $Context,
    "--checkpoint-every", 100
)
if ($Limit -gt 0) {
    $Arguments += @("--limit", $Limit)
}

& python @Arguments 2>&1 | Tee-Object -FilePath $Log -Append
$TranslationExitCode = $LASTEXITCODE
Write-Host ""
if ($TranslationExitCode -eq 0) {
    Write-Host "Translation complete. Run scripts\start_editor.ps1 to review it." -ForegroundColor Green
} else {
    Write-Host "Translation stopped with exit code $TranslationExitCode. Details: $Log" -ForegroundColor Yellow
}
exit $TranslationExitCode
