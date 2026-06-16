# -*- coding: utf-8 -*-
"""
钉钉群机器人每日学习推送。

常用命令：
1. 预览今天要发的内容：
   python dingtalk_daily_learning_bot.py --dry-run
2. 发送今天的内容：
   python dingtalk_daily_learning_bot.py
3. 常驻运行，每天 13:00 自动发送：
   python dingtalk_daily_learning_bot.py --daemon --send-time 13:00
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


PLACEHOLDER_WEBHOOK = "填入你的钉钉机器人Webhook"


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_points(path: str | Path) -> list[dict]:
    points = load_json(path)
    if not isinstance(points, list) or not points:
        raise ValueError("knowledge_points.json 必须是非空 JSON 数组")
    for index, point in enumerate(points, start=1):
        if not isinstance(point, dict):
            raise ValueError(f"第 {index} 条知识点不是 JSON 对象")
        if not point.get("message"):
            raise ValueError(f"第 {index} 条知识点缺少 message 字段")
    return points


def load_config(path: str | Path) -> dict:
    config = {
        "webhook_url": "",
        "webhook_urls": [],
        "secret": "",
        "start_date": "2026-06-15",
        "title": "高速铁路线路维修每日学习",
        "random_seed": "dingtalk-daily-learning",
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
        "LEARNING_RANDOM_SEED": "random_seed",
        "MAX_MESSAGE_CHARS": "max_message_chars",
    }
    for env_name, key in env_map.items():
        value = os.getenv(env_name)
        if value:
            config[key] = value

    webhook_urls = os.getenv("DINGTALK_WEBHOOKS")
    if webhook_urls:
        config["webhook_urls"] = split_multi_value(webhook_urls)

    at_mobiles = os.getenv("AT_MOBILES")
    if at_mobiles:
        config["at_mobiles"] = [item.strip() for item in at_mobiles.split(",") if item.strip()]

    is_at_all = os.getenv("IS_AT_ALL")
    if is_at_all:
        config["is_at_all"] = is_at_all.lower() in {"1", "true", "yes", "y"}

    return config


def split_multi_value(value: str) -> list[str]:
    items: list[str] = []
    for line in value.replace(";", "\n").replace(",", "\n").splitlines():
        item = line.strip()
        if item:
            items.append(item)
    return items


def get_webhook_urls(config: dict) -> list[str]:
    urls: list[str] = []
    configured_urls = config.get("webhook_urls", [])
    if isinstance(configured_urls, str):
        urls.extend(split_multi_value(configured_urls))
    elif isinstance(configured_urls, list):
        urls.extend(str(item).strip() for item in configured_urls if str(item).strip())

    single_url = str(config.get("webhook_url", "")).strip()
    if single_url:
        urls.append(single_url)

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []
    webhook_urls = get_webhook_urls(config)
    if not webhook_urls:
        errors.append("还没有填写钉钉机器人 Webhook。GitHub Actions 请配置 Repository secret: DINGTALK_WEBHOOK 或 DINGTALK_WEBHOOKS")
    for index, webhook_url in enumerate(webhook_urls, start=1):
        if PLACEHOLDER_WEBHOOK in webhook_url or "Webhook" in webhook_url:
            errors.append(f"第 {index} 个 webhook 仍是占位文本")
        elif not webhook_url.startswith("https://oapi.dingtalk.com/robot/send?access_token="):
            errors.append(f"第 {index} 个 webhook 看起来不像钉钉自定义机器人 Webhook")

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


def pick_point(points: list[dict], start_date: str, target_date: dt.date, random_seed: str) -> tuple[int, dict]:
    start = dt.date.fromisoformat(start_date)
    day_number = max((target_date - start).days, 0)
    cycle = day_number // len(points)
    offset = day_number % len(points)
    order = sorted(
        range(len(points)),
        key=lambda i: hashlib.sha256(
            f"{random_seed}:{cycle}:{points[i].get('id', i)}".encode("utf-8")
        ).hexdigest(),
    )
    index = order[offset]
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

    points = load_points(args.points)
    target_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    start_date = config.get("start_date", "2026-06-15")

    random_seed = str(config.get("random_seed", "dingtalk-daily-learning"))
    point_index, point = pick_point(points, start_date, target_date, random_seed)
    payload = build_payload(config, point_index, len(points), point)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    results = []
    for index, webhook_url in enumerate(get_webhook_urls(config), start=1):
        result = send_dingtalk(webhook_url, payload, config.get("secret") or None)
        results.append({"index": index, "result": result})
    print(json.dumps(results, ensure_ascii=False, indent=2))


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
    parser = argparse.ArgumentParser(description="每日 13:00 推送一个学习知识点到钉钉群")
    parser.add_argument("--config", default="config.json", help="配置文件")
    parser.add_argument("--points", default="knowledge_points.json", help="知识点 JSON")
    parser.add_argument("--date", help="指定发送日期，格式 YYYY-MM-DD；默认今天")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不发送")
    parser.add_argument("--validate-config", action="store_true", help="检查配置是否已可发送")
    parser.add_argument("--validate-points", action="store_true", help="检查知识点 JSON 是否完整")
    parser.add_argument("--daemon", action="store_true", help="常驻运行，按 --send-time 定时发送")
    parser.add_argument("--send-time", default="13:00", help="daemon 模式发送时间，默认 13:00")
    args = parser.parse_args()

    if args.validate_points:
        points = load_points(args.points)
        print(f"知识点检查通过：{len(points)} 条")
    elif args.validate_config:
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
