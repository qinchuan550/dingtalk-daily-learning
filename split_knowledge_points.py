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

        page_numbers = [int(x) for x in re.findall(r"<<<PAGE:(\d+)>>>", raw)]
        raw = re.sub(r"\n?<<<PAGE:\d+>>>\n?", "\n", raw).strip()
        raw = normalize_inline(raw)
        first_page = nearest_page(page_offsets, start)
        last_page = page_numbers[-1] if page_numbers else first_page
        raw = trim_section_tail(raw)
        # 第三部分是考核表格，表内扣分项也使用“1．/2．”编号。
        # 这里先只保留红线和必知必会，第三部分按实作项目单独切分。
        if first_page >= 101:
            continue
        if 12 <= first_page < 101 and "答：" not in raw:
            continue

        blocks.append(
            {
                "number": int(match.group(1)),
                "page_start": first_page,
                "page_end": last_page,
                "raw": raw,
            }
        )

    blocks.extend(find_practice_blocks(stream, page_offsets))
    return blocks


def trim_section_tail(raw: str) -> str:
    """去掉夹在两个编号条目之间的章节标题尾巴。"""
    for marker in (
        "\n第二部分 必知必会",
        "\n第三部分 必学必练",
        "\n第一章 安全知识",
        "\n第二章 基础知识",
        "\n第三章 基础规章",
        "\n第四章 常见故障及应急处置",
    ):
        if marker in raw:
            raw = raw.split(marker, 1)[0].strip()
    return raw


def find_practice_blocks(stream: str, page_offsets: list[tuple[int, int]]) -> list[dict]:
    """第三部分按 20 个“xx作业”项目拆分，而不是按表格扣分项拆分。"""
    practice_start = stream.find("第三部分 必学必练")
    if practice_start < 0:
        return []

    practice_stream = stream[practice_start:]
    matches = list(
        re.finditer(
            r"(?m)^((?:[1-9]|1\d|20))[．.]\s*([^\n]*作业)\s*$",
            practice_stream,
        )
    )
    blocks: list[dict] = []
    for i, match in enumerate(matches):
        abs_start = practice_start + match.start()
        abs_end = practice_start + (matches[i + 1].start() if i + 1 < len(matches) else len(practice_stream))
        raw = stream[abs_start:abs_end].strip()
        page_numbers = [int(x) for x in re.findall(r"<<<PAGE:(\d+)>>>", raw)]
        raw = re.sub(r"\n?<<<PAGE:\d+>>>\n?", "\n", raw).strip()
        raw = normalize_inline(raw)
        first_page = page_numbers[0] if page_numbers else nearest_page(page_offsets, abs_start)
        last_page = page_numbers[-1] if page_numbers else first_page
        blocks.append(
            {
                "number": int(match.group(1)),
                "page_start": first_page,
                "page_end": last_page,
                "raw": raw,
            }
        )
    return blocks


def nearest_page(page_offsets: list[tuple[int, int]], position: int) -> int:
    current = 1
    for offset, page in page_offsets:
        if position >= offset:
            current = page
        else:
            break
    return current


def classify_block(block: dict) -> str:
    raw = block["raw"]
    page = block["page_start"]
    if "答：" in raw:
        return "问答"
    if page >= 101:
        return "实作"
    return "红线"


def infer_section(page: int, raw: str) -> str:
    if page <= 11:
        return "第一部分 红线知识"
    if page <= 100:
        if page <= 31:
            return "第二部分 必知必会 / 第一章 安全知识"
        if page <= 40:
            return "第二部分 必知必会 / 第二章 基础知识"
        if page <= 94:
            return "第二部分 必知必会 / 第三章 基础规章"
        return "第二部分 必知必会 / 第四章 常见故障及应急处置"
    title = re.match(r"^\d+[．.]\s*([^\n]+)", raw)
    if title:
        return f"第三部分 必学必练 / {title.group(1).strip()}"
    return "第三部分 必学必练"


def make_point(index: int, block: dict) -> dict:
    raw = block["raw"]
    kind = classify_block(block)
    source = infer_section(block["page_start"], raw)

    question = ""
    answer = ""
    title = ""
    content = raw

    if kind == "问答":
        before, after = raw.split("答：", 1)
        question = unwrap_pdf_lines(re.sub(r"^\d+[．.]\s*", "", before).strip())
        answer = unwrap_pdf_lines(after.strip())
        title = question.split("？", 1)[0].strip(" ：:")[:60]
    elif kind == "实作":
        content = re.sub(r"^\d+[．.]\s*", "", raw).strip()
        title = content.split("\n", 1)[0].strip()[:60]
    else:
        content = unwrap_pdf_lines(re.sub(r"^\d+[．.]\s*", "", raw).strip())
        title = content.split("\n", 1)[0].strip()[:60]

    message = build_message(index, title, kind, source, question, answer, content)

    return {
        "id": f"kp-{index:03d}",
        "source_file": DEFAULT_PDF,
        "source_section": source,
        "source_pages": [block["page_start"], block["page_end"]],
        "type": kind,
        "title": title,
        "question": question,
        "answer": answer,
        "content": content,
        "message": message,
    }


def build_message(
    index: int,
    title: str,
    kind: str,
    source: str,
    question: str,
    answer: str,
    content: str,
) -> str:
    head = f"【每日学习】高速铁路线路维修\n第 {index} 个知识点｜{kind}\n来源：{source}\n"
    if kind == "问答":
        return f"{head}\n【问题】{question}\n\n【答案】{answer}"
    if kind == "实作":
        return f"{head}\n【实作项目】{title}\n\n{content}"
    return f"{head}\n【红线/禁止行为】{content}"


def write_markdown(points: list[dict], output_path: Path) -> None:
    lines = ["# 高速铁路线路维修每日学习知识点", ""]
    for i, point in enumerate(points, start=1):
        pages = point["source_pages"]
        lines.extend(
            [
                f"## {i}. {point['title']}",
                "",
                f"- 类型：{point['type']}",
                f"- 来源：{point['source_section']}",
                f"- 页码：{pages[0]}-{pages[1]}",
                "",
            ]
        )
        if point["type"] == "问答":
            lines.extend([f"**问题：** {point['question']}", "", f"**答案：** {point['answer']}", ""])
        else:
            lines.extend([point["content"], ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="拆解 PDF 为每日学习知识点")
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="PDF 文件路径")
    parser.add_argument("--json", default="knowledge_points.json", help="JSON 输出路径")
    parser.add_argument("--markdown", default="knowledge_points.md", help="Markdown 输出路径")
    parser.add_argument("--text", default="extracted_text.md", help="抽取文本输出路径")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(f"找不到 PDF：{pdf_path}")

    pages = extract_pages(pdf_path)
    Path(args.text).write_text(
        "\n\n".join(f"<!-- page {p.page} -->\n{p.text}" for p in pages),
        encoding="utf-8",
    )

    blocks = find_numbered_blocks(pages)
    points = [make_point(i, block) for i, block in enumerate(blocks, start=1)]

    Path(args.json).write_text(json.dumps(points, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(points, Path(args.markdown))
    print(f"已生成 {len(points)} 个知识点：{args.json}, {args.markdown}")


if __name__ == "__main__":
    main()
