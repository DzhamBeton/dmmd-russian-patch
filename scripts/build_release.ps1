param([string]$Version = "0.1.0")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$Dist = Join-Path $Root "dist\DMMD-Rus-v$Version"

if (-not (Test-Path -LiteralPath $Compiler)) { throw "Не найден компилятор C#: $Compiler" }
if (-not (Test-Path -LiteralPath (Join-Path $Root "release\payload\dx.dmpatch"))) { throw "Сначала соберите release payload" }

New-Item -ItemType Directory -Path (Join-Path $Dist "payload") -Force | Out-Null
& $Compiler /nologo /target:winexe /optimize+ /platform:anycpu /win32manifest:"$Root\installer\app.manifest" /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /out:"$Dist\DMMD-Rus-Patcher.exe" "$Root\installer\Program.cs"
if ($LASTEXITCODE -ne 0) { throw "Ошибка компиляции патчера" }

Copy-Item -LiteralPath "$Root\release\payload\script.dmpatch","$Root\release\payload\font.dmpatch","$Root\release\payload\dx.dmpatch" -Destination (Join-Path $Dist "payload") -Force
Copy-Item -LiteralPath "$Root\README.md" -Destination (Join-Path $Dist "README.txt") -Force

$Checksums = Get-ChildItem $Dist -Recurse -File | ForEach-Object {
    $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $Relative = $_.FullName.Substring($Dist.Length + 1).Replace('\','/')
    "$Hash  $Relative"
}
$Checksums | Set-Content -LiteralPath (Join-Path $Dist "SHA256SUMS.txt") -Encoding ascii

$Archive = Join-Path $Root "dist\DMMD-Rus-v$Version.zip"
if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
Compress-Archive -Path "$Dist\*" -DestinationPath $Archive -CompressionLevel Optimal
$ArchiveHash = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
"$ArchiveHash  $(Split-Path -Leaf $Archive)" | Set-Content -LiteralPath "$Archive.sha256" -Encoding ascii
Get-Item $Archive
