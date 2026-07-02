@echo off
cd /d "%~dp0"
echo Installing dependencies (if needed)...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo pip failed. Trying: py -m pip install -r requirements.txt
  py -m pip install -r requirements.txt -q
)
echo.
echo Starting website at http://127.0.0.1:5000
echo Your browser should open automatically. Press Ctrl+C here to stop the server.
echo.
python app.py
if errorlevel 1 py app.py
pause
