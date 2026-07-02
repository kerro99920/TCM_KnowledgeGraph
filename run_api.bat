@echo off
rem 启动 FastAPI 后端（首次运行会自动安装依赖）
cd /d %~dp0
echo API: http://localhost:8000  (docs: http://localhost:8000/docs)
uv run --project app tcm serve
pause
