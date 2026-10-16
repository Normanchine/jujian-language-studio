$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonLauncher) {
    throw 'Python 3.11 64-bit is required. Install it from python.org, then rerun setup.ps1.'
}

& py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.11 was not found. Install Python 3.11 64-bit and rerun setup.ps1.'
}
& py -3.11 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 must be 64-bit.' }

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the .venv environment.' }
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install project dependencies.' }

Write-Host 'Setup complete. Run .\run.cmd to start the app.'
} finally {
    Pop-Location
}
