$ErrorActionPreference = 'Stop'
$systemRoot = Split-Path $PSScriptRoot -Parent
$root = Split-Path $systemRoot -Parent
if ((Split-Path $root -Leaf) -ne 'semflow-audit-ui') { throw 'This launcher requires the independent UI checkout.' }
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = Join-Path $systemRoot '.venv\Scripts\python.exe' }
if (!(Test-Path -LiteralPath $python)) { throw 'Install the independent virtual environment first. See LOCAL_SETUP.md.' }
& $python -X utf8 "$systemRoot\scripts\prepare_ui_local.py"
if ($LASTEXITCODE -ne 0) { throw 'Independent configuration failed.' }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:SWC_NATIVE_BINDING_CACHE = Join-Path $env:USERPROFILE '.semflow-swc-cache'
$env:PATH = "$root\.tools\codeql;$(Split-Path $python -Parent);$env:PATH"
$logs = Join-Path $root 'artifacts\local'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$statePath = Join-Path $logs 'processes.json'
$state = @{}
if (Test-Path -LiteralPath $statePath) {
    $old = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($entry in $old.PSObject.Properties) { $state[$entry.Name] = $entry.Value }
}
function Start-ServiceProcess($name, $executable, $arguments, $directory) {
    if ($state.ContainsKey($name)) {
        $oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($state[$name])"
        if ($oldProcess -and $oldProcess.CommandLine -and $oldProcess.CommandLine.Contains($root)) { return }
    }
    $proc = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $directory -WindowStyle Hidden -RedirectStandardOutput "$logs\$name.out.log" -RedirectStandardError "$logs\$name.err.log" -PassThru
    $state[$name] = $proc.Id
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
}
function Test-DockerReady {
    $ErrorActionPreference = 'Continue'
    & docker info --format '{{.ServerVersion}}' *> $null
    return ($LASTEXITCODE -eq 0)
}
if (!(Test-DockerReady)) {
    Start-Process -FilePath 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -WindowStyle Hidden
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 2
        if (Test-DockerReady) { $ready = $true; break }
    }
    if (!$ready) { throw 'Docker Desktop did not become ready.' }
}
& docker compose --env-file "$root\.env" -f "$systemRoot\compose.yml" --project-name semflow-audit-ui up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Independent database/Redis startup failed.' }
Push-Location "$systemRoot\backend"
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Independent migration failed.' }
    & $python -m app.initial_data
    if ($LASTEXITCODE -ne 0) { throw 'Independent workspace initialization failed.' }
    & $python -m app.jobs.bootstrap
    if ($LASTEXITCODE -ne 0) { throw 'Independent workflow initialization failed.' }
} finally { Pop-Location }
Start-ServiceProcess 'api' $python '-m uvicorn app.main:app --host 127.0.0.1 --port 8001' "$systemRoot\backend"
Start-ServiceProcess 'worker' $python '-m celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO' "$systemRoot\backend"
Start-ServiceProcess 'frontend' 'D:\node.exe' "`"$systemRoot\frontend\node_modules\vite\bin\vite.js`" --host 127.0.0.1 --port 5174 --strictPort" "$systemRoot\frontend"
foreach ($url in @('http://127.0.0.1:8001/api/v1/utils/health-check/', 'http://127.0.0.1:5174')) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; $ready = $true; break } catch { Start-Sleep -Seconds 1 }
    }
    if (!$ready) { throw "Service unavailable: $url. Check $logs" }
}
Write-Host 'Semflow UI V2: http://127.0.0.1:5174'
