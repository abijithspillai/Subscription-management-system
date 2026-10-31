@echo off
setlocal
echo ========================================================
echo   Pushing 2-Hour Milestone to GitHub
echo   Repo: https://github.com/abijithspillai/Subscription-management-system
echo   Author: aadi-in (adithyasijo12@gmail.com)
echo ========================================================
echo.

set GIT_CMD="%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
where git >nul 2>nul
if %ERRORLEVEL% equ 0 set GIT_CMD=git

%GIT_CMD% push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Code successfully pushed to GitHub!
) else (
    echo.
    echo [NOTE] If prompted, sign in via browser or paste your GitHub Personal Access Token.
)

pause
