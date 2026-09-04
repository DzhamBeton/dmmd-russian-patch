$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "start_polish.ps1"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class DmmdAwake {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
"@

$Continuous = [uint32]2147483648
$SystemRequired = [uint32]1

Set-Location $ProjectRoot
Write-Host "DMMD: full TranslateGemma post-edit"
Write-Host "The computer will be kept awake while this window is running."
Write-Host "You may stop safely with Ctrl+C; the next launch will continue from the checkpoint."
Write-Host ""

try {
    [void][DmmdAwake]::SetThreadExecutionState([uint32]($Continuous -bor $SystemRequired))
    & $Runner -Model "translategemma:12b" -Limit 0
    exit $LASTEXITCODE
}
finally {
    [void][DmmdAwake]::SetThreadExecutionState($Continuous)
}
