# -*- coding: utf-8 -*-
"""
遍历 中药大全列表.xlsx，按行读取网址，抓取每个网址的全部中药相关正文并保存为单个 txt 文件。
提取主内容区所有小节（名称、来源、性味、性状、功效、用法用量、注意禁忌、药方等），支持断点续传与格式整理。
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

EXCEL_NAME = "中药大全列表.xlsx"
OUTPUT_DIR_NAME = "中药详情"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 1.0

# 名称小节之后的这些标题出现时，视为已离开“名称”区，不再过滤别名行
NAME_SECTION_END_HEADERS = frozenset({
    "来源", "种植", "炮制", "性状", "效果", "性味", "功效",
    "用法用量", "注意禁忌", "主治", "经脉", "原形态", "生境分布",
})

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


def _collect_block_texts(node) -> list[str]:
    """递归收集块级元素文本：有块级子节点则递归，否则整块取一段（块内空格连接）。"""
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
    """整理换行与标点。"""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"。\s*(\d+)\.\s*", r"。\n\1. ", text)
    text = re.sub(r"。\s+", "。\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


def _remove_number_hash(text: str) -> str:
    """删除“1 #”“2 #”等整行，以及文中出现的数字+# 片段。"""
    if not text:
        return text
    lines = text.split("\n")
    result = []
    for line in lines:
        # 整行仅为“数字 + #”则跳过
        if re.fullmatch(r"\s*\d+\s*#\s*", line.strip()):
            continue
        # 行内去掉“数字 #”或“数字  #”等
        line = re.sub(r"\s*\d+\s*#\s*", " ", line)
        line = re.sub(r"  +", " ", line).strip()
        if line:
            result.append(line)
    return "\n".join(result)


def _is_single_alias_line(line: str) -> bool:
    """
    判断是否为“名称”下那种单独占一行的短别名（如：辽细辛、华细辛、小辛，每行一个词）。
    条件：整行仅为 2～4 个汉字，无空格、无标点。
    """
    if not line:
        return False
    stripped = line.strip()
    # 恰好 2～4 个汉字，且无其它字符（排除“名称”等标题在下面逻辑里做）
    return 2 <= len(stripped) <= 4 and bool(re.fullmatch(r"[\u4e00-\u9fff]+", stripped))


def _remove_name_section_alias_lines(text: str) -> str:
    """
    在“名称”小节内，去掉单独占一行的短别名（如每行一个：辽细辛、华细辛、小辛、少辛 ...），其余保留。
    """
    if not text.strip():
        return text
    lines = text.split("\n")
    result = []
    in_name_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == "名称":
            in_name_section = True
            result.append(line)
            continue
        if stripped and stripped in NAME_SECTION_END_HEADERS:
            in_name_section = False
            result.append(line)
            continue
        # 只删：名称小节内、且该行是“单独一个 2～4 字中文”的别名行
        if in_name_section and _is_single_alias_line(stripped):
            continue
        result.append(line)
    return "\n".join(result)


def extract_full_content(html: str) -> str:
    """从 HTML 中提取主内容区全部正文（所有小节），块内不换行、块间换行。"""
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
        raw = root.get_text(separator=" ", strip=True)
        if raw:
            blocks = [raw]
    text = _normalize_format("\n\n".join(blocks))
    text = _remove_number_hash(text)  # 删除“1 #”“2 #”等整行及文中该片段
    return _remove_name_section_alias_lines(text)


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

        text = extract_full_content(html)
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
