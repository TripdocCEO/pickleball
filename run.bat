@echo off
REM ── 정관 피클볼 클럽 — 로컬 서버 실행 ──
cd /d "%~dp0"

if not exist ".venv" (
  echo [1/3] 가상환경 생성...
  uv venv || python -m venv .venv
)

echo [2/3] 패키지 설치 확인...
".venv\Scripts\python.exe" -c "import fastapi" 2>nul || uv pip install fastapi "uvicorn[standard]" pytest httpx

echo [3/3] 초기 데이터 확인...
".venv\Scripts\python.exe" server\seed.py

echo.
echo ==========================================
echo   사이트   http://localhost:8000
echo   API 문서 http://localhost:8000/api/docs
echo   종료하려면 Ctrl+C
echo ==========================================
echo.

".venv\Scripts\python.exe" -m uvicorn server.main:app --host 127.0.0.1 --port 8000
