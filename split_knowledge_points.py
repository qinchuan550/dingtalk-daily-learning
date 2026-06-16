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


def fix_common_ocr(text: str) -> str:
    replacements = {
        "lmm": "1mm",
        "l435": "1435",
        "Wl": "W1",
        "W300-l": "W300-1",
        "W300-la": "W300-1a",
        "W300-lu": "W300-1u",
        "橡胶垫。板": "橡胶垫板",
        "轨距档板": "轨距挡板",
        "夹极处": "夹板处",
        "承轨槽捎肩": "承轨槽挡肩",
        "下顿": "下颚",
        "问隙": "间隙",
        "调整垂": "调整量",
        "标准轨距一现场轨距": "标准轨距-现场轨距",
        "元昨": "无砟",
        "道昨": "道砟",
        "昨肩": "砟肩",
        "穷实": "夯实",
        "劳实": "夯实",
        "秀拍": "夯拍",
        "埋人式": "埋入式",
        "放人": "放入",
        "侵人": "侵入",
        "一昧": "一味",
        "做为": "作为",
        "记录薄": "记录簿",
        "尺1、防夹木": "尺、防夹木",
        "音视频设备各、": "音视频设备、",
        "频设备各、": "频设备、",
        "轨辐轮": "轨辊轮",
        "辐轮": "辊轮",
        "辑轮": "辊轮",
        "辘轮": "辊轮",
        "辗轮": "辊轮",
        "45。角": "45°角",
        "土6mm": "±6mm",
        "侧向磨耗超max过": "侧向磨耗超过",
        "拧紧螺旋道，": "拧紧螺旋道钉，",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def fix_point_specific(question: str, answer: str) -> str:
    if question.startswith("高速铁路钢轨头部磨耗的重伤标准"):
        answer = answer.replace("50kg/m钢轨，v ≤120km/h", "50kg/m钢轨，vmax≤120km/h")
    elif question.startswith("高速铁路钢轨接头顶面或内侧错牙"):
        answer = "350km/h≥vmax＞250km/h的线路为小于等于0.8mm；250km/h≥vmax＞200km/h的线路为小于等于1mm。"
    elif question.startswith("高速铁路钢轨硬弯和焊缝低塌"):
        answer = (
            "（1）钢轨硬弯、焊缝（接头）轨顶面低塌或马鞍形磨耗："
            "350km/h≥vmax＞250km/h的线路大于0.2mm；"
            "250km/h≥vmax＞200km/h的线路大于0.3mm。\n"
            "（2）轨顶面擦伤：350km/h≥vmax＞250km/h的线路深度大于0.35mm；"
            "250km/h≥vmax＞200km/h的线路深度大于0.5mm。"
        )
    elif question.startswith("高速铁路轨道线路对曲线未被平衡超高"):
        answer = answer.replace("160km/h≥v 时不大于90mm；max200km/h≥v ＞160km/h不大于70mm；v ＞200km/h不大于60mm。max max", "160km/h≥vmax时不大于90mm；200km/h≥vmax＞160km/h不大于70mm；vmax＞200km/h不大于60mm。")
    elif question.startswith("高速铁路曲线超高顺坡"):
        answer = answer.replace("1/（10v ），在困难条件下按不大于1/（9v ）设置。max max欠超高", "1/（10vmax），在困难条件下按不大于1/（9vmax）设置。\n欠超高")
    elif question.startswith("高速铁路正线道岔（直向）与曲线之间"):
        answer = "正线曲线与道岔间夹直线长度一般条件下不应小于0.6vmax，困难条件下不应小于0.5vmax。"
    elif question.startswith("道岔尖轨、心轨后靠前不靠产生原因"):
        answer = answer.replace("框架尺寸 Cl462.4 川口、1504.3mm）过小。", "框架尺寸（1462.4mm、1504.3mm）过小。")
    return answer


def fix_point_specific_question(question: str, answer: str) -> str:
    if question == "7.5条）" and "有砟轨道无缝线路区段，对扒道床、起道、拨道作业的轨温条件规定见下表" in answer:
        return "有砟轨道无缝线路区段，对扒道床、起道、拨道作业的轨温条件如何规定？《高速铁路有砟轨道线路维修规则》（第3.7.5条）"
    return question


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


def display_source(source: str) -> str:
    source = re.sub(r"第[一二三四五六七八九十]+部分\s*", "", source)
    source = source.replace("必知必会 / ", "")
    source = source.replace("必学必练 / ", "")
    source = source.strip(" /")
    return source


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
        question = fix_common_ocr(unwrap_pdf_lines(re.sub(r"^\d+[．.]\s*", "", before).strip()))
        answer = fix_common_ocr(unwrap_pdf_lines(after.strip()))
        question = fix_point_specific_question(question, answer)
        answer = fix_point_specific(question, answer)
        content = answer
        title = question.split("？", 1)[0].strip(" ：:")[:60]
    elif kind == "实作":
        content = fix_common_ocr(re.sub(r"^\d+[．.]\s*", "", raw).strip())
        title = content.split("\n", 1)[0].strip()[:60]
    else:
        content = fix_common_ocr(unwrap_pdf_lines(re.sub(r"^\d+[．.]\s*", "", raw).strip()))
        title = content.split("\n", 1)[0].strip()[:60]

    message = build_message(title, kind, display_source(source), question, answer, content)

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
    title: str,
    kind: str,
    source: str,
    question: str,
    answer: str,
    content: str,
) -> str:
    head = f"【每日学习】高速铁路线路维修｜{kind}\n来源：{source}\n"
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
