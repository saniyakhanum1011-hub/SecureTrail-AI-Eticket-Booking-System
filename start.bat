@echo off
title SecureTrail — Smart E-Ticket System
cd /d %~dp0

echo ============================================
echo  SecureTrail — AI Fraud Detection Platform
echo ============================================

echo [1/4] Installing Python dependencies...
pip install -r backend\requirements.txt -q

echo [2/4] Generating synthetic dataset...
python ml\generate_dataset.py

echo [3/5] Training fraud detection model...
python ml\train_model.py

echo [4/5] Training scanner document model...
python ml\train_scanner.py

echo [5/5] Building frontend...
python build_frontend.py

echo.
echo Starting server on http://localhost:5000
start cmd /k "cd /d %~dp0 && python backend\app.py"
timeout /t 3 /nobreak >nul
start "" "http://localhost:5000"
echo.
echo SecureTrail is running! Press any key to exit this window.
pause >nul
