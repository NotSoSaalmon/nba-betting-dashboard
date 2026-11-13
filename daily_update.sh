#!/bin/bash
cd /Users/rasheedwhiters/nba_project
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_betting_data.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_injuries.py
/Users/rasheedwhiters/nba_project/venv/bin/python fetch_odds.py
/Users/rasheedwhiters/nba_project/venv/bin/python grade_picks.py

git add *.csv model_engine.py grade_picks.py fetch_injuries.py app.py
git commit -m "Daily 5AM data refresh, injuries, & auto-grading"
git push origin main
