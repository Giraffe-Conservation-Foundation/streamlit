@echo off
cd /d "g:\My Drive\Data management\streamlit"
echo ===================================
echo FORCING GIT SYNC TO GITHUB
echo ===================================
echo Current directory: %CD%
echo.

echo === CHECKING GIT STATUS ===
git status
echo.

echo === ADDING ALL FILES (including new directories) ===
git add -A
git add .
git add pages/
git add zaf_dashboard/
echo.

echo === SHOWING STAGED FILES ===
git status --porcelain
echo.

echo === COMMITTING WITH FORCE ===
git commit -m "FORCE UPDATE: Add ZAF Dashboard with satellite mapping - %date% %time%"
echo.

echo === FORCE PUSHING TO GITHUB ===
git push origin main --force
echo.

echo === FINAL STATUS CHECK ===
git status
echo.

echo ===================================
echo COMPLETED! 
echo Check: https://github.com/Giraffe-Conservation-Foundation/streamlit
echo ===================================
pause
