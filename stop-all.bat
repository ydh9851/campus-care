@echo off
setlocal

echo ============================================================
echo   CampusCare - Stop all services
echo ============================================================
echo.

echo Stopping services on ports 8080 (Java), 8000 (Python), 5173 (UI)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8080,8000,5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host ('Killed PID ' + $_) }"

echo.
echo Done. All CampusCare services stopped.
echo MySQL and Redis are system services and were left running.
echo.
pause
