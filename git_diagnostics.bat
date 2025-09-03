@echo off
title Git Diagnostics
color 0E

echo ========================================
echo           GIT DIAGNOSTICS
echo ========================================
echo.

cd /d "g:\My Drive\Data management\streamlit"
echo Current directory: %CD%
echo.

echo === GIT VERSION ===
git --version
echo.

echo === GIT CONFIG ===
git config --list --show-origin
echo.

echo === GIT REMOTE ===
git remote -v
echo.

echo === GIT BRANCH ===
git branch -a
echo.

echo === GIT STATUS ===
git status
echo.

echo === CHECKING FOR .git DIRECTORY ===
if exist ".git" (
    echo .git directory EXISTS
    dir .git
) else (
    echo .git directory MISSING - This is not a git repository!
)
echo.

echo === CHECKING ZAF FILES ===
if exist "pages\3_🦒_ZAF_Dashboard.py" (
    echo ✓ ZAF Dashboard launcher found
) else (
    echo ✗ ZAF Dashboard launcher MISSING
)

if exist "zaf_dashboard\app.py" (
    echo ✓ ZAF Dashboard app found
) else (
    echo ✗ ZAF Dashboard app MISSING
)

if exist "zaf_dashboard\README.md" (
    echo ✓ ZAF Dashboard README found
) else (
    echo ✗ ZAF Dashboard README MISSING
)

if exist "zaf_dashboard\requirements.txt" (
    echo ✓ ZAF Dashboard requirements found
) else (
    echo ✗ ZAF Dashboard requirements MISSING
)
echo.

echo === GIT LOG (Last 5 commits) ===
git log --oneline -5
echo.

echo ========================================
echo         DIAGNOSTICS COMPLETE
echo ========================================
pause
