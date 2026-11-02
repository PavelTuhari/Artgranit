@echo off
rem TexFlow — установка на Windows двойным щелчком. Права администратора не нужны.
setlocal
cd /d "%~dp0"
set PY=
where py >nul 2>nul && (py -3 -c "import sys,tkinter;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set PY=py -3)
if not defined PY (where python >nul 2>nul && (python -c "import sys,tkinter;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set PY=python))
if not defined PY (
  echo Python 3.10+ с Tkinter не найден. Пробую установить Python 3.12 через winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Не получилось. Скачайте Python с https://www.python.org/downloads/ ^(отметьте "Add python.exe to PATH"^)
    start "" https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set PY=py -3
)
%PY% "%~dp0install\install.py" %*
if errorlevel 1 pause
