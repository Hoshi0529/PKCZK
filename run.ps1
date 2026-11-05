$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.11 was not found at '$python'. Install Python or update the path in run.ps1."
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run (Join-Path $projectRoot "ChosePokemon.py") --server.port 8765
exit $LASTEXITCODE
