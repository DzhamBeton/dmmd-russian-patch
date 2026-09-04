param(
    [string]$Catalog = "translations\ru-machine.jsonl",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath $Catalog)) {
    if (Test-Path -LiteralPath "translations\early-reviewed.jsonl") {
        Copy-Item -LiteralPath "translations\early-reviewed.jsonl" -Destination $Catalog
    } else {
        Copy-Item -LiteralPath "translations\source.jsonl" -Destination $Catalog
    }
    Write-Host "Created working catalog: $Catalog"
}

Write-Host "Editor URL: http://127.0.0.1:$Port"
Write-Host "Stop the server with Ctrl+C"
python -u editor\server.py $Catalog --port $Port
