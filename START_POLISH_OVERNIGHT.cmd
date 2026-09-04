@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DMMD Russian - TranslateGemma overnight editor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_polish_night.ps1"
set "DMMD_EXIT=%ERRORLEVEL%"
echo.
if "%DMMD_EXIT%"=="0" (
  echo Редакторский проход завершён успешно.
) else (
  echo Проход остановлен или завершился с ошибкой. Код: %DMMD_EXIT%
  echo Повторный запуск продолжит работу с сохранённой точки.
)
echo.
pause
exit /b %DMMD_EXIT%
