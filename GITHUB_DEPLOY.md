# GitHub 部署清单

目标：把每日学习机器人部署到 GitHub Actions，每天北京时间 20:00 自动向钉钉群发送 1 条知识点。

## 1. 新建 GitHub 仓库

登录 GitHub 后新建一个仓库，例如：

```text
dingtalk-daily-learning
```

仓库可以是 Public 或 Private。

## 2. 上传文件

使用本目录里的 `github_upload_package.zip`：

1. 解压 `github_upload_package.zip`。
2. 打开 GitHub 仓库页面。
3. 点击 `Add file` -> `Upload files`。
4. 把解压后的全部文件拖进去。
5. 确认仓库里存在这个路径：

```text
.github/workflows/dingtalk_daily_learning.yml
```

这个路径是 GitHub Actions 自动运行的关键。

如果后续修改了文件，可以重新生成上传包：

```powershell
powershell -ExecutionPolicy Bypass -File .\make_github_upload_package.ps1
```

## 3. 配置钉钉机器人 Secrets

进入仓库：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

必须新增：

```text
DINGTALK_WEBHOOK
```

值填写钉钉自定义机器人的 Webhook。

如果钉钉机器人开启了“加签”，再新增：

```text
DINGTALK_SECRET
```

值填写加签密钥。

## 4. 手动测试

进入仓库：

```text
Actions -> DingTalk Daily Learning -> Run workflow
```

运行成功后，钉钉群应收到当天知识点。

## 5. 自动运行

workflow 已配置：

```yaml
cron: "0 12 * * *"
```

GitHub Actions 使用 UTC 时间，UTC 12:00 对应北京时间 20:00。

## 6. 常见问题

- 没收到消息：先看 Actions 运行日志，重点检查 `Validate DingTalk config` 和 `Send daily knowledge point`。
- 提示缺少 `DINGTALK_WEBHOOK`：说明 Secrets 没填或名字拼错。
- 提示签名错误：检查 `DINGTALK_SECRET` 是否和钉钉机器人加签密钥一致。
- Actions 页面看不到 workflow：检查 `.github/workflows/dingtalk_daily_learning.yml` 路径是否正确。
