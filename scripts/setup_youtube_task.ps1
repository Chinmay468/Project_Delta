$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "D:\Projects\movie-shorts-pipeline\movie-shorts-pipeline\config\run_daily_youtube_upload.bat"' -WorkingDirectory "D:\Projects\movie-shorts-pipeline\movie-shorts-pipeline"
$trigger1 = New-ScheduledTaskTrigger -Daily -At "12:35PM"
$trigger2 = New-ScheduledTaskTrigger -Daily -At "10:00PM"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "DailyYouTubeNatureUpload" -Action $action -Trigger @($trigger1, $trigger2) -Settings $settings -Force
