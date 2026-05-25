@echo off
echo Cleaning old build...
if exist "dist\LimbicJourney" (
    attrib -r -s -h "dist\LimbicJourney\*.*" /s /d >nul 2>&1
    rmdir /s /q "dist\LimbicJourney"
)
if exist "build\LimbicJourney" rmdir /s /q "build\LimbicJourney"

echo Building LimbicJourney...
"C:/Users/drewm/AppData/Local/Programs/Python/Python313/python.exe" -m PyInstaller LimbicJourney.spec --noconfirm
echo.
echo Done. Executable is in dist\LimbicJourney\LimbicJourney.exe
pause
