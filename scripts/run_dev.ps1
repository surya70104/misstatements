<#
.SYNOPSIS
    Start the Misstatements Rollup for development, or as a seeded demonstration.

.DESCRIPTION
    scripts\run_dev.ps1 demo       The isolated preview on http://127.0.0.1:8014, seeded with
                                   the demonstration engagement. Nothing is kept: the preview
                                   runs in one transaction on oak_misstatements_test that is
                                   rolled back when it stops. This is the default.
    scripts\run_dev.ps1 backend    The API on http://127.0.0.1:8003, reloading on change.
    scripts\run_dev.ps1 frontend   The dev server on http://127.0.0.1:3003 (proxies /api to 8003).

    Run it from anywhere; paths are taken from the script's own location. It installs
    nothing and changes no setting. The backend needs backend\.venv and backend\.env, the
    frontend needs frontend\node_modules under Node 22: see "Setup on Windows" in README.md.

    The demo needs the test database created (scripts\db) and migrated, which running the
    backend tests once does, and OAK_TEST_APP_DATABASE_URL in backend\.env. It uses the
    Financial Spine test double, never the live Spine. Do not run the PostgreSQL test suite
    while the demo is open.

.PARAMETER Target
    demo (default), backend or frontend.

.PARAMETER Build
    With demo: build the frontend again even when frontend\dist exists.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('demo', 'backend', 'frontend')]
    [string]$Target = 'demo',

    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
$PreviewPort = 8014

function Assert-Backend {
    if (-not (Test-Path $Python)) {
        throw "backend\.venv is missing. See 'Setup on Windows' in README.md."
    }
    if (-not (Test-Path (Join-Path $Backend '.env'))) {
        throw "backend\.env is missing. Copy backend\.env.example to backend\.env and fill it in."
    }
}

function Invoke-Npm {
    # Node 22 through fnm when fnm is installed; otherwise whatever npm is on PATH, which
    # frontend\.npmrc refuses unless it is Node 22 or later.
    param([string[]]$Arguments)
    if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
        throw "frontend\node_modules is missing. Run 'npm install' in frontend (see README.md)."
    }
    Push-Location $Frontend
    try {
        if (Get-Command fnm -ErrorAction SilentlyContinue) {
            & fnm exec --using=22 -- npm @Arguments
        }
        else {
            & npm @Arguments
        }
        if ($LASTEXITCODE -ne 0) {
            throw "npm $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Test-Health {
    param([int]$Port)
    try {
        $answer = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri "http://127.0.0.1:$Port/api/health"
        return $answer.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Start-Demo {
    Assert-Backend
    if (Get-NetTCPConnection -LocalPort $PreviewPort -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $PreviewPort is already in use. Stop the preview that is running there first."
    }
    if ($Build -or -not (Test-Path (Join-Path $Frontend 'dist\index.html'))) {
        Write-Host 'Building the frontend...'
        Invoke-Npm -Arguments @('run', 'build')
    }

    Write-Host "Starting the isolated preview on port $PreviewPort..."
    $preview = Start-Process -FilePath $Python `
        -ArgumentList @('-u', '-m', 'tests.preview_server', '--port', "$PreviewPort") `
        -WorkingDirectory $Backend -NoNewWindow -PassThru
    try {
        $ready = $false
        for ($attempt = 0; $attempt -lt 60 -and -not $ready; $attempt++) {
            if ($preview.HasExited) {
                throw 'The preview stopped before it was ready; its message is above.'
            }
            Start-Sleep -Milliseconds 500
            $ready = Test-Health -Port $PreviewPort
        }
        if (-not $ready) {
            throw "The preview did not answer on port $PreviewPort within 30 seconds."
        }

        & $Python (Join-Path $PSScriptRoot 'seed_demo.py')
        if ($LASTEXITCODE -ne 0) {
            throw 'The demo seed stopped; its message is above.'
        }

        Write-Host ''
        Write-Host "The demo is at http://127.0.0.1:$PreviewPort. Press Ctrl+C to stop it; nothing is kept."
        Wait-Process -Id $preview.Id
    }
    finally {
        if (-not $preview.HasExited) {
            Stop-Process -Id $preview.Id -Force
        }
    }
}

switch ($Target) {
    'demo' {
        Start-Demo
    }
    'backend' {
        Assert-Backend
        Push-Location $Backend
        try {
            & $Python -m uvicorn oak_misstatements.main:create_app --factory --reload --port 8003
        }
        finally {
            Pop-Location
        }
    }
    'frontend' {
        Invoke-Npm -Arguments @('run', 'dev')
    }
}
