$ErrorActionPreference = "Stop"

$WorkDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stage = Join-Path $WorkDir "tmp_github_upload"
$Zip = Join-Path $WorkDir "github_upload_package.zip"

if (Test-Path $Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
if (Test-Path $Zip) {
    Remove-Item -LiteralPath $Zip -Force
}

New-Item -ItemType Directory -Path $Stage | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Stage ".github\workflows") -Force | Out-Null

$RootFiles = @(
    "README.md",
    "GITHUB_DEPLOY.md",
    ".gitignore",
    "config.example.json",
    "dingtalk_daily_learning_bot.py",
    "split_knowledge_points.py",
    "knowledge_points.json",
    "knowledge_points.md",
    "install_daily_learning_task.ps1",
    "run_daily_learning_once.ps1",
    "make_github_upload_package.ps1"
)

foreach ($File in $RootFiles) {
    Copy-Item -LiteralPath (Join-Path $WorkDir $File) -Destination (Join-Path $Stage $File) -Force
}

Copy-Item `
    -LiteralPath (Join-Path $WorkDir ".github\workflows\dingtalk_daily_learning.yml") `
    -Destination (Join-Path $Stage ".github\workflows\dingtalk_daily_learning.yml") `
    -Force

Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
Remove-Item -LiteralPath $Stage -Recurse -Force

Write-Host "已生成：$Zip"
