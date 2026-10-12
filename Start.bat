@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
if not exist frontend\dist\index.html (
  pushd frontend
  call npm install
  if errorlevel 1 goto fail
  call npm run build
  if errorlevel 1 goto fail
  popd
)
.venv\Scripts\python.exe launcher.py
pause
exit /b
:fail
 echo Setup failed. Check Python, Node.js and your internet connection.
 pause
 exit /b 1
