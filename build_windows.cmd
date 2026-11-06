@echo off
cd /d "%~dp0"
echo Building LED Placement Studio (one-file Windows exe)...
python -m pip install --upgrade pip pyinstaller
pyinstaller --noconfirm --clean ^
  --name "LED_Placement_Studio" ^
  --windowed ^
  --onefile ^
  --icon "assets\icon.png" ^
  --add-data "styles;styles" ^
  --add-data "assets;assets" ^
  main.py
echo.
echo Done. Look in dist\LED_Placement_Studio.exe
pause
