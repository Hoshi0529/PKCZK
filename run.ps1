$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"

if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
} elseif (-not (Test-Path -LiteralPath $python)) {
    throw "Python was not found. Create the project's .venv or install Python 3.11 at '$python'."
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run (Join-Path $projectRoot "streamlit_app.py") --server.port 8765
exit $LASTEXITCODE
