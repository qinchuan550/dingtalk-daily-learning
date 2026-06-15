# 钉钉每日学习机器人

这个目录用于把 `高速铁路线路维修.pdf` 拆成每日学习知识点，并通过钉钉群机器人每天 20:00 推送一条。

## 1. 生成知识点

```powershell
& "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\split_knowledge_points.py
```

会生成：

- `knowledge_points.json`：机器人使用
- `knowledge_points.md`：人工检查版
- `extracted_text.md`：PDF 抽取文本备查

## 2. 配置钉钉机器人

复制 `config.example.json` 为 `config.json`，填写钉钉群机器人的 `webhook_url`。

如果钉钉机器人启用了“加签”，把密钥填到 `secret`；没有启用则留空。

## 3. 预览与发送

预览今天要发的内容：

```powershell
& "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\dingtalk_daily_learning_bot.py --dry-run
```

发送今天的内容：

```powershell
& "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\dingtalk_daily_learning_bot.py
```

检查配置是否已经能真实发送：

```powershell
& "C:\Users\93156\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\dingtalk_daily_learning_bot.py --validate-config
```

## 4. 每天 20:00 自动发送

用 Windows 计划任务定时运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_daily_learning_task.ps1
```

计划任务会每天 20:00 执行一次 `dingtalk_daily_learning_bot.py`。

运行日志会写入 `logs\dingtalk_daily_learning.log`。

## 5. 挂到 GitHub Actions

仓库里已经放好 `.github/workflows/dingtalk_daily_learning.yml`。它会在每天北京时间 20:00 自动运行。

### 上传方式

如果本机没有安装 Git，可以直接在 GitHub 网页操作：

1. 新建一个空仓库。
2. 解压 `github_upload_package.zip`。
3. 把解压后的所有文件上传到仓库根目录。
4. 确认仓库里能看到 `.github/workflows/dingtalk_daily_learning.yml`，这个路径必须保留，不能只上传成 `dingtalk_daily_learning.yml`。

也可以把仓库地址发给 Codex，后续由 GitHub 连接器写入文件。

更详细的部署步骤见 `GITHUB_DEPLOY.md`。

如果修改过文件，可以重新生成上传包：

```powershell
powershell -ExecutionPolicy Bypass -File .\make_github_upload_package.ps1
```

### 配置 Secrets

在 GitHub 仓库里设置：

- `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
- 新增 `DINGTALK_WEBHOOK`：填钉钉机器人 Webhook
- 如开启加签，新增 `DINGTALK_SECRET`：填加签密钥

可选变量：

- `LEARNING_START_DATE`：开始推送日期，默认 `2026-06-15`
- `LEARNING_TITLE`：钉钉消息标题
- `AT_MOBILES`：要 @ 的手机号，多个用英文逗号分隔
- `IS_AT_ALL`：填 `true` 表示 @ 所有人

注意：本地 `config.json` 已加入 `.gitignore`，不要把真实 webhook 提交到 GitHub。

### 手动测试

进入仓库的 `Actions` 页面，选择 `DingTalk Daily Learning`，点击 `Run workflow`。如果配置正确，钉钉群会收到当天知识点。
