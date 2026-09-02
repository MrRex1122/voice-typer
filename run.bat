@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] creating venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [err] venv creation failed
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo [setup] installing dependencies...
    python -m pip install --upgrade pip
    if errorlevel 1 (
        echo [err] pip upgrade failed
        pause
        exit /b 1
    )
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [err] pip install failed
        pause
        exit /b 1
    )
    echo [setup] done. launching in background...
) else (
    call .venv\Scripts\activate.bat
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0voice_typer.py"
) else (
    start "" python "%~dp0voice_typer.py"
)

endlocal