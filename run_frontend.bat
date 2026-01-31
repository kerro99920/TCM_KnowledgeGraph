@echo off
echo Starting TCM Knowledge Graph Frontend...
echo.
echo Access at: http://localhost:8501
echo.
streamlit run frontend/app.py --server.port 8501
pause
