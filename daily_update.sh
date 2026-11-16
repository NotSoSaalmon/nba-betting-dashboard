#!/bin/bash
cd /Users/rasheedwhiters/nba_project
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_betting_data.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_injuries.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_odds.py
/Users/rasheedwhiters/nba_project/venv/bin/python grade_picks.py
/Users/rasheedwhiters/nba_project/venv/bin/python tune_weights.py

git add *.csv *.json model_engine.py grade_picks.py tune_weights.py fetch_injuries.py app.py
git commit -m "Daily 5AM refresh, auto-grading, & self-calibration"
git push origin main
