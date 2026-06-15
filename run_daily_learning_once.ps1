param(
    [string]$Python = "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$WorkDir = "D:\dev\learn"
)

$logDir = Join-Path $WorkDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "dingtalk_daily_learning.log"
$script = Join-Path $WorkDir "dingtalk_daily_learning_bot.py"

Add-Content -Path $logFile -Encoding UTF8 -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') start ====="
Push-Location $WorkDir
try {
    & $Python $script 2>&1 | ForEach-Object {
        Add-Content -Path $logFile -Encoding UTF8 -Value $_
    }
    Add-Content -Path $logFile -Encoding UTF8 -Value "exit_code=$LASTEXITCODE"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    Add-Content -Path $logFile -Encoding UTF8 -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') end ====="
}
