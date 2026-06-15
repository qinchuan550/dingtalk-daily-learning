# -*- coding: utf-8 -*-
"""
钉钉群机器人每日学习推送。

常用命令：
1. 预览今天要发的内容：
   python dingtalk_daily_learning_bot.py --dry-run
2. 发送今天的内容：
   python dingtalk_daily_learning_bot.py
3. 常驻运行，每天 20:00 自动发送：
   python dingtalk_daily_learning_bot.py --daemon --send-time 20:00
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


PLACEHOLDER_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=dfb2f6e31ebb3d56cef29da887f53ba321e84ac9d30c5a99f83b840ff4080c6c"


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config(path: str | Path) -> dict:
    config = {
        "webhook_url": "",
        "secret": "",
        "start_date": "2026-06-15",
        "title": "高速铁路线路维修每日学习",
        "max_message_chars": 3800,
        "at_mobiles": [],
        "is_at_all": False,
    }
    config_path = Path(path)
    if config_path.exists():
        config.update(load_json(config_path))

    env_map = {
        "DINGTALK_WEBHOOK": "webhook_url",
        "DINGTALK_SECRET": "secret",
        "LEARNING_START_DATE": "start_date",
        "LEARNING_TITLE": "title",
        "MAX_MESSAGE_CHARS": "max_message_chars",
    }
    for env_name, key in env_map.items():
        value = os.getenv(env_name)
        if value:
            config[key] = value

    at_mobiles = os.getenv("AT_MOBILES")
    if at_mobiles:
        config["at_mobiles"] = [item.strip() for item in at_mobiles.split(",") if item.strip()]

    is_at_all = os.getenv("IS_AT_ALL")
    if is_at_all:
        config["is_at_all"] = is_at_all.lower() in {"1", "true", "yes", "y"}

    return config


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []
    webhook_url = str(config.get("webhook_url", "")).strip()
    if not webhook_url or PLACEHOLDER_WEBHOOK in webhook_url or "Webhook" in webhook_url:
        errors.append("还没有填写钉钉机器人 Webhook。GitHub Actions 请配置 Repository secret: DINGTALK_WEBHOOK")
    elif not webhook_url.startswith("https://oapi.dingtalk.com/robot/send?access_token="):
        errors.append("webhook_url 看起来不像钉钉自定义机器人 Webhook")

    start_date = str(config.get("start_date", "")).strip()
    try:
        dt.date.fromisoformat(start_date)
    except ValueError:
        errors.append("start_date 必须是 YYYY-MM-DD 格式")

    at_mobiles = config.get("at_mobiles", [])
    if not isinstance(at_mobiles, list):
        errors.append("at_mobiles 必须是手机号字符串数组")

    try:
        max_chars = int(config.get("max_message_chars", 3800))
        if max_chars < 500:
            errors.append("max_message_chars 建议不小于 500")
    except (TypeError, ValueError):
        errors.append("max_message_chars 必须是数字")
    return errors


def pick_point(points: list[dict], start_date: str, target_date: dt.date) -> tuple[int, dict]:
    start = dt.date.fromisoformat(start_date)
    index = (target_date - start).days % len(points)
    return index + 1, points[index]


def signed_webhook(webhook_url: str, secret: str | None) -> str:
    if not secret:
        return webhook_url
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


def build_payload(config: dict, point_index: int, total: int, point: dict) -> dict:
    title = config.get("title", "每日学习")
    text = point["message"]
    text += f"\n\n今日进度：{point_index}/{total}"
    max_chars = int(config.get("max_message_chars", 3800))
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n（内容较长，已自动截断；完整内容见 knowledge_points.md）"

    at_mobiles = config.get("at_mobiles", [])
    is_at_all = bool(config.get("is_at_all", False))
    if at_mobiles:
        text += "\n\n" + " ".join(f"@{mobile}" for mobile in at_mobiles)

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text.replace("\n", "\n\n"),
        },
        "at": {
            "atMobiles": at_mobiles,
            "isAtAll": is_at_all,
        },
    }


def send_dingtalk(webhook_url: str, payload: dict, secret: str | None = None) -> dict:
    url = signed_webhook(webhook_url, secret)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def send_once(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    errors = validate_config(config)
    if errors and not args.dry_run:
        raise ValueError("配置未完成：\n- " + "\n- ".join(errors))

    points = load_json(args.points)
    target_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    start_date = config.get("start_date", "2026-06-15")

    point_index, point = pick_point(points, start_date, target_date)
    payload = build_payload(config, point_index, len(points), point)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    webhook_url = config.get("webhook_url", "").strip()
    result = send_dingtalk(webhook_url, payload, config.get("secret") or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def daemon_loop(args: argparse.Namespace) -> None:
    send_hour, send_minute = map(int, args.send_time.split(":", 1))
    sent_dates: set[str] = set()
    print(f"已启动每日学习机器人，发送时间：{send_hour:02d}:{send_minute:02d}")
    while True:
        now = dt.datetime.now()
        today_key = now.date().isoformat()
        should_send = now.hour == send_hour and now.minute == send_minute
        if should_send and today_key not in sent_dates:
            send_once(args)
            sent_dates.add(today_key)
        time.sleep(20)


def main() -> None:
    parser = argparse.ArgumentParser(description="每日 20:00 推送一个学习知识点到钉钉群")
    parser.add_argument("--config", default="config.json", help="配置文件")
    parser.add_argument("--points", default="knowledge_points.json", help="知识点 JSON")
    parser.add_argument("--date", help="指定发送日期，格式 YYYY-MM-DD；默认今天")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不发送")
    parser.add_argument("--validate-config", action="store_true", help="检查配置是否已可发送")
    parser.add_argument("--daemon", action="store_true", help="常驻运行，按 --send-time 定时发送")
    parser.add_argument("--send-time", default="20:00", help="daemon 模式发送时间，默认 20:00")
    args = parser.parse_args()

    if args.validate_config:
        errors = validate_config(load_config(args.config))
        if errors:
            raise SystemExit("配置未完成：\n- " + "\n- ".join(errors))
        print("配置检查通过")
    elif args.daemon:
        daemon_loop(args)
    else:
        send_once(args)


if __name__ == "__main__":
    main()
