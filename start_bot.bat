@echo off
title Telegram Bot - 24/7
cd /d "c:\Users\sanja\OneDrive\Desktop\telegram bot"

:restart
echo [%date% %time%] Bot ishga tushirilmoqda...
"C:\Users\sanja\AppData\Local\Programs\Python\Python313\python.exe" main.py

echo [%date% %time%] Bot to'xtadi! 5 sekunddan keyin qayta ishga tushadi...
timeout /t 5 /nobreak >nul
goto restart
