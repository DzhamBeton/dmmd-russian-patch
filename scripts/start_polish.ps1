param(
    [string]$Model = "translategemma:12b",
    [int]$Limit = 100,
    [int]$Context = 4096
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InputCatalog = Join-Path $ProjectRoot "translations\ru-machine.jsonl"
$OutputCatalog = Join-Path $ProjectRoot "translations\ru-polished.jsonl"
$LogDirectory = Join-Path $ProjectRoot "logs"
$Stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Log = Join-Path $LogDirectory "polish_$Stamp.log"
$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $Ollama) {
    $OllamaPath = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $OllamaPath) { $Ollama = $OllamaPath }
}
if (-not $Ollama) { throw "Ollama was not found." }

New-Item -ItemType Directory -Force $LogDirectory | Out-Null
Set-Location $ProjectRoot
Write-Host "Post-editor model: $Model"
Write-Host "Output: $OutputCatalog"
Write-Host "Log: $Log"
Write-Host "Limit: $Limit (use -Limit 0 for the full catalog after reviewing the test)"

$Arguments = @("-u", "scripts\polish_ollama.py", $InputCatalog, $OutputCatalog, "--model", $Model, "--num-ctx", $Context)
if ($Limit -gt 0) { $Arguments += @("--limit", $Limit) }
& python @Arguments 2>&1 | Tee-Object -FilePath $Log -Append
$PolishExitCode = $LASTEXITCODE
if ($PolishExitCode -eq 0) {
    $ReviewedCatalog = "$OutputCatalog.reviewed"
    & python "scripts\apply_overrides.py" $OutputCatalog $ReviewedCatalog --overrides "config\system-overrides.json" 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Move-Item -LiteralPath $ReviewedCatalog -Destination $OutputCatalog -Force
    Write-Host "Applied reviewed non-texture UI strings."
    $NormalizedCatalog = "$OutputCatalog.normalized"
    & python "scripts\normalize_leading_lines.py" $OutputCatalog $NormalizedCatalog --strip-all 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Move-Item -LiteralPath $NormalizedCatalog -Destination $OutputCatalog -Force
}
exit $PolishExitCode
