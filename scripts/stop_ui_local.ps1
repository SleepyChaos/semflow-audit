$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ((Split-Path $root -Leaf) -ne 'semflow-audit-ui') { throw 'This launcher requires the independent UI checkout.' }
$statePath = Join-Path $root 'artifacts\local\processes.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($entry in $state.PSObject.Properties) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.Value)"
        if ($proc -and $proc.CommandLine -and $proc.CommandLine.Contains($root)) {
            & taskkill.exe /PID $entry.Value /T /F | Out-Null
        }
    }
    Remove-Item -LiteralPath $statePath
}
Set-Location $root
& docker compose --project-name semflow-audit-ui stop
if ($LASTEXITCODE -ne 0) { throw 'Could not stop independent Docker services.' }
Write-Host 'Independent UI stopped; database and audit artifacts preserved.'
