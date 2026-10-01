# Bot 24/7 ishga tushirish - PowerShell script
$taskName = "TelegramBot_24_7"
$batPath = "c:\Users\sanja\OneDrive\Desktop\telegram bot\start_bot.bat"

# Eski taskni o'chirish
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Action - BAT faylni ishga tushirish
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`""

# Trigger - Windows yoqilganda / Login qilinganda
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Task Principal - yuqori huquqlar bilan
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest

# Taskni ro'yxatdan o'tkazish
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Bot 24/7 ga sozlandi!" -ForegroundColor Green
Write-Host " Task nomi: $taskName" -ForegroundColor Cyan
Write-Host " Windows qayta yoqilganda bot avtomatik ishga tushadi." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Hozircha botni darhol ishga tushirish
Write-Host "Botni hozir ishga tushirilmoqda..." -ForegroundColor Yellow
Start-Process "cmd.exe" -ArgumentList "/c `"$batPath`"" -WindowStyle Minimized
Write-Host "Bot ishga tushdi!" -ForegroundColor Green
