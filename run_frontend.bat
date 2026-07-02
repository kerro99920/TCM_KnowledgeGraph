@echo off
rem 启动 Streamlit 前端（依赖 uv，无需手动装环境）
cd /d %~dp0
echo Frontend: http://localhost:8501  (backend must be running: run_api.bat)
uv run --no-project --with "streamlit>=1.35" streamlit run frontend/app.py --server.port 8501
pause
