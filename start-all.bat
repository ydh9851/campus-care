@echo off
setlocal

set "ROOT=%~dp0"

echo ============================================================
echo   CampusCare - Launch all services
echo ============================================================
echo.

echo [1/3] Starting Java backend  (port 8080) ...
start "CampusCare-Java" /D "%ROOT%campus-care-java" cmd /k "mvn spring-boot:run"

echo [2/3] Starting Python AI     (port 8000) ...
start "CampusCare-Python" /D "%ROOT%campus-care-python" cmd /k ".venv\Scripts\python.exe -m uvicorn main:app --port 8000"

echo [3/3] Starting frontend      (port 5173) ...
start "CampusCare-UI" /D "%ROOT%campus-care-ui" cmd /k "npm run dev"

echo.
echo All three services are launching in separate windows.
echo.
echo   Frontend : http://localhost:5173
echo   Java API : http://localhost:8080/swagger-ui.html
echo   Python   : http://localhost:8000/docs
echo.
echo Note: MySQL (3306) and Redis (6379) must be running as Windows
echo services. They normally start automatically at boot.
echo.
echo To stop: close each window, or press Ctrl+C in each window.
echo.
pause
