# -*- coding: utf-8 -*-
"""
遍历 中医方剂列表.xlsx，按行读取网址，抓取页面正文并保存为单个 txt 文件。
支持断点续传：已存在的 txt 会跳过。
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Excel 路径与输出目录（相对本脚本所在目录）
EXCEL_NAME = "中医方剂列表.xlsx"
OUTPUT_DIR_NAME = "方剂详情"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 1.0

# 按块提取时视为“块级”的标签，块与块之间换行，块内用空格连接
BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "section", "article", "header", "blockquote", "pre",
})


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """将方剂名称转为合法文件名（去掉非法字符、截断过长）。"""
    invalid = r'[<>:"/\\|?*\n\r\t]'
    s = re.sub(invalid, "_", name).strip()
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] if len(s) > max_len else s) or "未命名"


def fetch_page(url: str) -> str | None:
    """请求页面，返回 HTML。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        print(f"  请求失败: {e}")
        return None


def _collect_block_texts(node) -> list[str]:
    """递归收集块级元素的文本：有块级子节点则递归子节点，否则整块取一段（块内用空格连接）。"""
    blocks = []
    if not hasattr(node, "children"):
        return blocks
    for child in node.children:
        cname = getattr(child, "name", None)
        if not cname:
            continue
        if cname == "br":
            blocks.append("")
            continue
        if cname in BLOCK_TAGS:
            sub = _collect_block_texts(child)
            if sub:
                blocks.extend(sub)
            else:
                text = child.get_text(separator=" ", strip=True)
                if text:
                    blocks.append(text)
            continue
        blocks.extend(_collect_block_texts(child))
    return blocks


def _normalize_format(text: str) -> str:
    """整理换行与标点格式。"""
    # 多个换行压成至多两个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # "。 2." "。 1." 等改为换行后接序号
    text = re.sub(r"。\s*(\d+)\.\s*", r"。\n\1. ", text)
    # 句号后紧跟空格（如 "用法 。" "用法。 2."）时改为句号换行
    text = re.sub(r"。\s+", "。\n", text)
    # 每行首尾去空格，去掉空行
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


def extract_main_text(html: str) -> str:
    """从 HTML 中按块提取正文，块内不换行、块间换行，再统一整理格式。"""
    soup = BeautifulSoup(html, "html.parser")
    root = None
    for selector in [
        "#content", "main", "article",
        ".wiki-content", ".entry-content", ".post-content",
        "#mw-content-text", ".mw-parser-output",
    ]:
        root = soup.select_one(selector)
        if root:
            break
    if not root:
        root = soup.find("body") or soup
    blocks = _collect_block_texts(root)
    if not blocks:
        # 无块级结构时退化为整块文本
        raw = root.get_text(separator=" ", strip=True)
        if raw:
            blocks = [raw]
    text = "\n\n".join(blocks)
    return _normalize_format(text)


def main():
    script_dir = Path(__file__).resolve().parent
    excel_path = script_dir / EXCEL_NAME
    out_dir = script_dir / OUTPUT_DIR_NAME

    if not excel_path.exists():
        print(f"未找到 Excel: {excel_path}，请先运行 crawl_fangji.py 生成列表。")
        return

    df = pd.read_excel(excel_path, engine="openpyxl")
    if "网址" not in df.columns:
        print("Excel 中缺少列「网址」。")
        return

    has_name = "方剂名称" in df.columns
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(df)
    ok, fail, skip_exist = 0, 0, 0

    for i, row in df.iterrows():
        url = row["网址"]
        if pd.isna(url) or not str(url).strip().startswith("http"):
            fail += 1
            continue
        url = str(url).strip()
        name = row["方剂名称"] if has_name else f"方剂_{i+1}"
        if pd.isna(name):
            name = f"方剂_{i+1}"
        name = str(name).strip()
        fname = sanitize_filename(name) + ".txt"
        out_path = out_dir / fname

        # 断点续传：已存在且非空则跳过
        if out_path.exists() and out_path.stat().st_size > 0:
            skip_exist += 1
            print(f"[{i+1}/{total}] {name} ... 已存在，跳过")
            continue

        print(f"[{i+1}/{total}] {name} ... ", end="", flush=True)
        html = fetch_page(url)
        if not html:
            fail += 1
            print("跳过")
            continue

        text = extract_main_text(html)
        if not text.strip():
            print("无正文，跳过")
            fail += 1
            continue

        try:
            out_path.write_text(text, encoding="utf-8")
            ok += 1
            print("已保存")
        except Exception as e:
            fail += 1
            print(f"写入失败: {e}")

        if i < total - 1:
            time.sleep(REQUEST_DELAY)

    print(f"\n完成：成功 {ok}，已存在跳过 {skip_exist}，失败/跳过 {fail}，文件目录: {out_dir}")


if __name__ == "__main__":
    main()
