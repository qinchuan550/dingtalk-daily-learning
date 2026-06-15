# -*- coding: utf-8 -*-
"""
从《高速铁路线路维修》PDF 中抽取每日学习知识点。

输出：
- knowledge_points.json：机器人读取的结构化知识点
- knowledge_points.md：方便人工检查的 Markdown 版
- extracted_text.md：PDF 抽取文本备查
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


DEFAULT_PDF = "高速铁路线路维修.pdf"


@dataclass
class PageText:
    page: int
    text: str


def clean_page_text(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in {"高速铁路线路维修", "必 学 必 练"}:
            continue
        if re.fullmatch(r"●\s*\d+\s*●", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_pages(pdf_path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = clean_page_text(page.extract_text() or "")
            if text:
                pages.append(PageText(page=index, text=text))
    return pages


def normalize_inline(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def unwrap_pdf_lines(text: str) -> str:
    """合并 PDF 抽取造成的硬折行，保留明显的列表项换行。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merged: list[str] = []
    list_marker = re.compile(r"^(（\d+）|[①②③④⑤⑥⑦⑧⑨⑩]|第[一二三四五六七八九十]+[章节部分])")
    for line in lines:
        if not merged:
            merged.append(line)
        elif list_marker.match(line):
            merged.append(line)
        else:
            merged[-1] += line
    return "\n".join(merged).strip()


def find_numbered_blocks(page_texts: list[PageText]) -> list[dict]:
    stream_parts: list[str] = []
    page_offsets: list[tuple[int, int]] = []
    offset = 0
    for page in page_texts:
        # 正文从 PDF 第 8 页开始；前面是封面、前言、目录。
        if page.page < 8:
            continue
        marker = f"\n<<<PAGE:{page.page}>>>\n"
        stream_parts.append(marker)
        offset += len(marker)
        page_offsets.append((offset, page.page))
        stream_parts.append(page.text + "\n")
        offset += len(page.text) + 1

    stream = "".join(stream_parts)
    matches = list(re.finditer(r"(?m)^(\d{1,3})[．.]\s*", stream))
    blocks: list[dict] = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stream)
        raw = stream[start:end].strip()
        if not raw:
            continue
