#!/bin/bash
cd /Users/rasheedwhiters/nba_project
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_betting_data.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_injuries.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_odds.py
/Users/rasheedwhiters/nba_project/venv/bin/python grade_picks.py
/Users/rasheedwhiters/nba_project/venv/bin/python tune_weights.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_nfl_data.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_nfl_odds.py

git add *.csv *.json *.py
git commit -m "Daily 5AM NBA & NFL data refresh"
git push origin main
