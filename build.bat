@echo off
echo Building LimbicJourney...
"C:/Users/drewm/AppData/Local/Programs/Python/Python313/python.exe" -m PyInstaller LimbicJourney.spec --noconfirm
echo.
echo Done. Executable is in dist\LimbicJourney\LimbicJourney.exe
pause
