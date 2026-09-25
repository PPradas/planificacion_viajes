@echo off
cd /d "%~dp0"
pip install flask --quiet
python app.py
