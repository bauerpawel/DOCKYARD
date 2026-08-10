@echo off
setlocal
rem Sets up the venv if needed, then rebuilds templates.json and the site from
rem apps/ and stacks/. Does not touch Docker Hub - run `gallery fetch-metadata`
rem separately (or let the scheduled refresh-dockerhub workflow do it) to
rem refresh cache/dockerhub.json.
cd /d "%~dp0"

set VENV_DIR=.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ==^> Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 goto :error
)

call "%VENV_DIR%\Scripts\activate.bat"

echo ==^> Installing dependencies...
pip install -q -e .
if errorlevel 1 goto :error

echo ==^> Building templates.json and the website...
python -m gallery build %*
if errorlevel 1 goto :error

echo ==^> Validating templates.json...
python -m gallery validate
if errorlevel 1 goto :error

echo Done. templates.json and docs/ are up to date.
exit /b 0

:error
echo.
echo Build failed - see errors above.
exit /b 1
