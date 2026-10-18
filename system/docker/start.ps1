param(
    [ValidateSet('up', 'doctor', 'down', 'logs')]
    [string]$Action = 'up'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$envPath = Join-Path $root '.env.docker'
$compose = @('compose', '--env-file', $envPath, '-f', (Join-Path $root 'system/compose.full.yml'))

function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install Docker Desktop and reopen the terminal.'
}
$osType = & docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop before continuing.' }
if ($osType.Trim() -ne 'linux') { throw 'Switch Docker Desktop to Linux containers (WSL2 backend on Windows).' }
Invoke-Docker -DockerArgs @('compose', 'version')

if (-not (Test-Path $envPath)) {
    if ($Action -ne 'up') { throw 'Configuration missing. Run start.ps1 up to create .env.docker.' }
    $bytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    $template = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'compose.env.example'))
    $template = $template.Replace('POSTGRES_PASSWORD=', "POSTGRES_PASSWORD=$password")
    [IO.File]::WriteAllText($envPath, $template, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Created .env.docker with a random database password. Add AI_API_KEY and rerun. Existing local settings were preserved.'
    exit 2
}

Invoke-Docker -DockerArgs ($compose + @('config', '--quiet'))
switch ($Action) {
    'up' {
        Invoke-Docker -DockerArgs ($compose + @('up', '-d', '--build', '--wait', '--wait-timeout', '1800'))
        Write-Host 'Startup complete. Default URL: http://localhost:5181 (or APP_PORT in .env.docker).'
    }
    'doctor' {
        Invoke-Docker -DockerArgs ($compose + @('ps', '-a'))
        Write-Host 'Configuration parsed. Next: start.ps1 logs for startup failures. Registry 502/timeouts require checking Docker Desktop proxy/mirror settings.'
    }
    'down' { Invoke-Docker -DockerArgs ($compose + @('down')) }
    'logs' { Invoke-Docker -DockerArgs ($compose + @('logs', '--tail', '100', 'init', 'api', 'worker')) }
}
