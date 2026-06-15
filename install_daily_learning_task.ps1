param(
    [string]$TaskName = "DingTalkDailyLearning",
    [string]$Python = "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$WorkDir = "D:\dev\learn",
    [string]$Time = "20:00"
)

$script = Join-Path $WorkDir "run_daily_learning_once.ps1"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Python `"$Python`" -WorkDir `"$WorkDir`"" `
    -WorkingDirectory $WorkDir
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "每天定时向钉钉群推送一个学习知识点" `
    -Force

Write-Host "已创建/更新计划任务：$TaskName，每天 $Time 执行。"
