@echo off
:: Bu script Windows ishga tushganda botni avtomatik ishga tushiradi.
:: Task Scheduler orqali sozlash uchun shu faylni ishlating.

set TASK_NAME=TelegramBot_24_7
set BAT_PATH=c:\Users\sanja\OneDrive\Desktop\telegram bot\start_bot.bat

:: Eski taskni o'chirish (mavjud bo'lsa)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Yangi task yaratish - tizim ishga tushganda avtomatik boshlaydi
schtasks /create /tn "%TASK_NAME%" /tr "cmd /c \"%BAT_PATH%\"" /sc onlogon /rl highest /f

echo.
echo ============================================
echo  Bot 24/7 ishga sozlandi!
echo  Task nomi: %TASK_NAME%
echo  Windows qayta yoqilganda bot avtomatik ishga tushadi.
echo ============================================
echo.
pause
