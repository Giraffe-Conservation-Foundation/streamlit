@echo off
title Git Force Push - ZAF Dashboard Update
color 0A

echo.
echo ========================================
echo    FORCING GIT PUSH - ZAF DASHBOARD
echo ========================================
echo.

:: Change to the correct directory
echo Changing to repository directory...
cd /d "g:\My Drive\Data management\streamlit"
if errorlevel 1 (
    echo ERROR: Could not change to directory
    pause
    exit /b 1
)

echo Current directory: %CD%
echo.

:: Check if this is a git repository
echo Checking if this is a git repository...
if not exist ".git" (
    echo ERROR: This is not a git repository!
    echo You need to initialize git first.
    pause
    exit /b 1
)

:: Show current git status
echo.
echo === CURRENT GIT STATUS ===
git status
echo.

:: Show git remote
echo === GIT REMOTE INFO ===
git remote -v
echo.

:: Add all files
echo === ADDING ALL FILES ===
git add -A
git add pages\3_🦒_ZAF_Dashboard.py
git add zaf_dashboard\
git add zaf_dashboard\app.py
git add zaf_dashboard\README.md
git add zaf_dashboard\requirements.txt
echo Files added.
echo.

:: Show what will be committed
echo === FILES TO BE COMMITTED ===
git status --porcelain
echo.

:: Commit the changes
echo === COMMITTING CHANGES ===
git commit -m "FORCE UPDATE: Add ZAF Dashboard with satellite mapping - %date% %time%"
if errorlevel 1 (
    echo.
    echo Note: Commit may have failed because there are no changes to commit
    echo or because files are already committed.
    echo.
)

:: Push to remote
echo === PUSHING TO GITHUB ===
git push origin main
if errorlevel 1 (
    echo.
    echo Push failed! Trying force push...
    git push origin main --force
    if errorlevel 1 (
        echo.
        echo ERROR: Force push also failed!
        echo This might be due to authentication issues.
        echo.
        echo Try running these commands manually:
        echo git config --global user.name "Your Name"
        echo git config --global user.email "your.email@example.com"
        echo.
        pause
        exit /b 1
    )
)

echo.
echo === FINAL STATUS ===
git status
echo.

echo ========================================
echo           SUCCESS!
echo ========================================
echo.
echo Repository should now be updated on GitHub:
echo https://github.com/Giraffe-Conservation-Foundation/streamlit
echo.
echo After confirming the files are on GitHub:
echo 1. Go to your Streamlit Cloud app
echo 2. Restart the app deployment
echo 3. Check if ZAF Dashboard appears at position #3
echo.
pause
