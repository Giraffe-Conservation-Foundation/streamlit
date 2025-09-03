# PowerShell script to force push all changes to GitHub
Write-Host "=== Forcing Git Sync to GitHub ===" -ForegroundColor Green

# Navigate to the repository
Set-Location "g:\My Drive\Data management\streamlit"
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Yellow

# Check git status
Write-Host "`n=== Git Status ===" -ForegroundColor Cyan
git status

# Add all files including new directories
Write-Host "`n=== Adding all files ===" -ForegroundColor Cyan
git add -A
git add .

# Show what's staged
Write-Host "`n=== Staged files ===" -ForegroundColor Cyan
git status --porcelain

# Commit with timestamp
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commitMessage = "Force update: Add ZAF Dashboard with satellite mapping - $timestamp"
Write-Host "`n=== Committing changes ===" -ForegroundColor Cyan
Write-Host "Commit message: $commitMessage" -ForegroundColor Yellow
git commit -m "$commitMessage"

# Force push to main branch
Write-Host "`n=== Force pushing to GitHub ===" -ForegroundColor Cyan
git push origin main --force

# Check final status
Write-Host "`n=== Final Git Status ===" -ForegroundColor Cyan
git status

Write-Host "`n=== COMPLETED! Check GitHub repository ===" -ForegroundColor Green
Write-Host "Repository: https://github.com/Giraffe-Conservation-Foundation/streamlit" -ForegroundColor Blue

# Pause to see results
Read-Host "Press Enter to continue..."
