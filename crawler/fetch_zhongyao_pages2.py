# -*- coding: utf-8 -*-
"""
遍历 中药大全列表.xlsx，按行读取网址，抓取页面正文并保存为单个 txt 文件。
仅保留：名称、来源、功效、用法用量、注意禁忌。支持断点续传。
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

EXCEL_NAME = "中药大全列表.xlsx"
OUTPUT_DIR_NAME = "中药详情"

# 需要保留的字段（与页面标题匹配）
SECTION_KEYS = ("名称", "来源", "功效", "用法用量", "注意禁忌")
# 页面中可能出现的对应标题（按优先级，匹配到即归入该字段）
SECTION_HEADING_MAP = {
    "名称": ["名称"],
    "来源": ["来源"],
    "功效": ["功效"],
    "用法用量": ["用法用量", "用法与用量", "用法"],
    "注意禁忌": ["注意禁忌", "禁忌", "注意事项"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 1.0

HEADING_TAGS = ("h1", "h2", "h3", "h4")
BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "section", "article", "header", "blockquote", "pre",
})


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """将名称转为合法文件名。"""
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


def _heading_to_key(heading_text: str) -> str | None:
    """将页面标题文本映射到我们的字段名（优先长匹配，如用法用量先于用法）。"""
    t = heading_text.strip()
    t = re.sub(r"【[^】]*】", "", t).strip()
    # 按候选长度降序，优先匹配“用法用量”再匹配“用法”
    for key, candidates in SECTION_HEADING_MAP.items():
        for c in sorted(candidates, key=len, reverse=True):
            if c == t or (len(t) <= 25 and c in t):
                return key
    return None


def _get_text_between(node, end_before) -> str:
    """从 node 的下一个兄弟开始，到 end_before 之前，收集块级文本（块内空格连接）。"""
    blocks = []
    sib = node.next_sibling
    while sib and sib != end_before:
        if getattr(sib, "name", None) in HEADING_TAGS:
            break
        if getattr(sib, "name", None) in BLOCK_TAGS:
            blocks.append(sib.get_text(separator=" ", strip=True))
        elif getattr(sib, "name", None):
            blocks.append(sib.get_text(separator=" ", strip=True))
        sib = getattr(sib, "next_sibling", None)
    return "\n\n".join(b for b in blocks if b).strip()


def _normalize_block(text: str) -> str:
    """整理一段内容的换行与标点。"""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"。\s*(\d+)\.\s*", r"。\n\1. ", text)
    text = re.sub(r"。\s+", "。\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


def extract_sections(html: str, page_name: str = "") -> dict[str, str]:
    """
    从 HTML 中只提取：名称、来源、功效、用法用量、注意禁忌。
    返回 dict，键为上述字段名，值为对应正文（无则空字符串）。
    """
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

    result = {k: "" for k in SECTION_KEYS}

    # 名称：优先用页面 h1（去掉【中药】等）
    h1 = root.find("h1")
    if h1:
        name_text = h1.get_text(separator=" ", strip=True)
        name_text = re.sub(r"【[^】]*】", "", name_text).strip()
        if name_text:
            result["名称"] = name_text

    # 遍历所有标题，按标题归类内容
    for tag in root.find_all(HEADING_TAGS):
        title_text = tag.get_text(separator=" ", strip=True)
        title_text = re.sub(r"【[^】]*】", "", title_text).strip()
        key = _heading_to_key(title_text)
        if not key:
            continue
        content = _get_text_between(tag, None)
        content = _normalize_block(content)
        if content and (not result[key] or key == "名称"):
            result[key] = content

    # 若名称仍空，用传入的 page_name（Excel 中的名称）
    if not result["名称"] and page_name:
        result["名称"] = page_name

    return result


def sections_to_text(sections: dict[str, str]) -> str:
    """将 名称/来源/功效/用法用量/注意禁忌 格式化为最终要写入的 txt 内容。"""
    lines = []
    for key in SECTION_KEYS:
        val = (sections.get(key) or "").strip()
        lines.append(f"{key}\n{val}" if val else f"{key}\n")
    return "\n\n".join(lines)


def main():
    script_dir = Path(__file__).resolve().parent
    excel_path = script_dir / EXCEL_NAME
    out_dir = script_dir / OUTPUT_DIR_NAME

    if not excel_path.exists():
        print(f"未找到 Excel: {excel_path}，请先运行 crawl_zhongyao.py 生成列表。")
        return

    df = pd.read_excel(excel_path, engine="openpyxl")
    if "网址" not in df.columns:
        print("Excel 中缺少列「网址」。")
        return

    has_name = "名称" in df.columns
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(df)
    ok, fail, skip_exist = 0, 0, 0

    for i, row in df.iterrows():
        url = row["网址"]
        if pd.isna(url) or not str(url).strip().startswith("http"):
            fail += 1
            continue
        url = str(url).strip()
        name = row["名称"] if has_name else f"中药_{i+1}"
        if pd.isna(name):
            name = f"中药_{i+1}"
        name = str(name).strip()
        fname = sanitize_filename(name) + ".txt"
        out_path = out_dir / fname

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

        sections = extract_sections(html, page_name=name)
        text = sections_to_text(sections)
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
