param(
    [string]$Catalog = "translations\ru-polished.jsonl"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$CatalogPath = Join-Path $Root $Catalog
$Output = Join-Path $Root "dist\DMMD-Translation-Editor-v2"
$Archive = Join-Path $Root "dist\DMMD-Translation-Editor.zip"

if (-not (Test-Path -LiteralPath $CatalogPath)) {
    throw "Translation catalog not found: $CatalogPath"
}

if (Test-Path -LiteralPath $Output) {
    Remove-Item -LiteralPath $Output -Recurse -Force
}
if (Test-Path -LiteralPath $Archive) {
    Remove-Item -LiteralPath $Archive -Force
}

New-Item -ItemType Directory -Path (Join-Path $Output "editor") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Output "translations") -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $Root "editor\server.py") -Destination (Join-Path $Output "editor\server.py")
Copy-Item -LiteralPath (Join-Path $Root "editor\index.html") -Destination (Join-Path $Output "editor\index.html")
Copy-Item -LiteralPath (Join-Path $Root "editor\portable\START_EDITOR.cmd") -Destination $Output
Copy-Item -LiteralPath (Join-Path $Root "editor\portable\README_EDITOR.txt") -Destination $Output
Copy-Item -LiteralPath $CatalogPath -Destination (Join-Path $Output "translations\translation.jsonl")

# cmd.exe requires Windows line endings; Git/apply_patch may store the template with LF.
$LauncherPath = Join-Path $Output "START_EDITOR.cmd"
$Launcher = [IO.File]::ReadAllText($LauncherPath) -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText($LauncherPath, $Launcher, [Text.Encoding]::ASCII)

Compress-Archive -LiteralPath $Output -DestinationPath $Archive -CompressionLevel Optimal
Write-Host "Created: $Archive"
Write-Host "Send this archive privately. The edited file to return is translations\translation.jsonl"
