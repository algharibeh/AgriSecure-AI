@echo off
rem AgriSecure-AI: reproduce every result with one double-click (Windows).
rem Nothing needs to be installed. The repository carries python.org's embeddable
rem Python 3.9.13 (tools\python-3.9.13-embed-amd64.zip) and pip's bootstrap
rem script (tools\get-pip.py); see tools\README.md. On the first run this file
rem unpacks that Python into tools\python, gives it pip, installs the pinned
rem requirements into it (about 120 MB from the Python Package Index, so an
rem internet connection is needed once), and then runs reproduce.py with it.
rem Later runs reuse tools\python. A clone that already has a .venv with
rem requirements.ok keeps using that. The tractor recording ships in
rem data\tumosan_raw\FIELD_FILES.zip and reproduce.py unpacks it; the C self-test
rem runs if gcc, cc or clang is on the PATH and is skipped otherwise.
rem Extra arguments are passed on, e.g.   reproduce.bat --skip-sil
rem This file must keep Windows (CRLF) line endings: cmd.exe cannot find the
rem labels below in a file with Unix line endings.
setlocal
cd /d "%~dp0"
if not exist ".venv\requirements.ok" goto bundled
set "PY=.venv\Scripts\python.exe"
goto run

:bundled
set "PYDIR=tools\python"
set "PY=%PYDIR%\python.exe"
if exist "%PYDIR%\requirements.ok" goto run
rem Windows limits most paths to 260 characters and the installed packages need
rem about 150 of them below this folder, so warn when the folder path is long.
powershell -NoProfile -Command "exit [int]((Get-Location).Path.Length -gt 100)"
if errorlevel 1 (
  echo   note: this folder path is long. If the installation below fails with "No such file
  echo   or directory", move the whole folder to a short path such as C:\AgriSecure-AI and run again.
)
if exist "%PY%" goto ensurepip

echo First run: unpacking the bundled Python 3.9.13 into %PYDIR% ...
if not exist "tools\python-3.9.13-embed-amd64.zip" goto nozip
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath 'tools\python-3.9.13-embed-amd64.zip' -DestinationPath '%PYDIR%' -Force"
if errorlevel 1 goto unpackfail
if not exist "%PY%" goto unpackfail
rem let the interpreter see its own Lib\site-packages (the package ships with 'import site' commented out)
rem (-I on every call below keeps pip and the run inside this folder, ignoring per-user Python packages)
(echo python39.zip& echo .& echo import site) > "%PYDIR%\python39._pth"

:ensurepip
"%PY%" -I -m pip --version >nul 2>&1
if not errorlevel 1 goto install
echo Installing pip into the bundled Python ...
"%PY%" -I tools\get-pip.py --no-warn-script-location --disable-pip-version-check
if errorlevel 1 goto pipfail

:install
echo Installing the pinned packages from requirements.txt into %PYDIR% (about 120 MB; resumes if interrupted) ...
"%PY%" -I -m pip install --disable-pip-version-check --no-warn-script-location --only-binary=:all: --timeout 120 --retries 10 -r requirements.txt
if errorlevel 1 goto pipfail
echo ok> "%PYDIR%\requirements.ok"
echo Environment ready.
echo.

:run
"%PY%" -I -u reproduce.py --pause %*
endlocal
goto :eof

:nozip
echo tools\python-3.9.13-embed-amd64.zip is missing. Download the repository again, or fetch
echo https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip into the tools folder.
pause
endlocal
exit /b 2

:unpackfail
echo Could not unpack the bundled Python. Unzip tools\python-3.9.13-embed-amd64.zip by hand into
echo the folder tools\python (so that tools\python\python.exe exists) and run this file again.
pause
endlocal
exit /b 2

:pipfail
echo.
echo Could not install the pinned packages. If the message above is a download timeout, check
echo the internet connection and double-click this file again to resume. If it says "No such
echo file or directory", the folder path is too long for Windows: move the whole folder to a
echo short path such as C:\AgriSecure-AI, delete tools\python there, and run again.
pause
endlocal
exit /b 2
