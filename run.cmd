@echo off
setlocal
set "PYTHONUTF8=1"
set "PROJECT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PROJECT_PYTHON%" (
    echo Project Python was not found. Set up .venv using README.md.
    exit /b 1
)
"%PROJECT_PYTHON%" -m streamlit run "%~dp0Login.py" %*
exit /b %errorlevel%
