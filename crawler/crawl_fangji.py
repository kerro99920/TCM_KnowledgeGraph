# -*- coding: utf-8 -*-
"""
爬取中医百科-中医方剂列表，保存为 Excel（方剂名称、网址）
"""
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# 目标页面
BASE_URL = "https://zhongyibaike.com"
TARGET_URL = "https://zhongyibaike.com/wiki/%E4%B8%AD%E5%8C%BB%E6%96%B9%E5%89%82"

# 请求头，模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 排除项：导航分类、页脚链接等，只保留方剂
EXCLUDE_NAMES = frozenset({
    "中医理论", "中医保健", "中医食疗", "中药大全", "中医方剂", "中医书籍",
    "关于我们", "版权声明", "服务条款",
})


def fetch_page(url: str) -> str | None:
    """请求页面，返回 HTML 文本。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def parse_fangji_links(html: str) -> list[tuple[str, str]]:
    """
    从页面 HTML 中解析出所有方剂链接。
    返回: [(方剂名称, 完整网址), ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    # 方剂详情页都是 /wiki/xxx 形式，且站内链接
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = (a.get_text() or "").strip()

        # 只保留站内 wiki 链接，且排除当前列表页本身
        if not href.startswith("/wiki/") and "zhongyibaike.com/wiki/" not in href:
            continue
        # 排除“中医方剂”列表页（当前页）
        if "%E4%B8%AD%E5%8C%BB%E6%96%B9%E5%89%82" in href:
            continue
        # 排除导航分类、页脚等非方剂链接
        if text in EXCLUDE_NAMES:
            continue
        # 无有效名称的不要（如分类标题）
        if not text or len(text) > 50:
            continue

        # 转为绝对 URL
        if href.startswith("/"):
            full_url = BASE_URL + href
        else:
            full_url = href

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        results.append((text, full_url))

    return results


def save_to_excel(data: list[tuple[str, str]], out_path: Path) -> None:
    """将 (方剂名称, 网址) 列表保存为 Excel。"""
    df = pd.DataFrame(data, columns=["方剂名称", "网址"])
    df.to_excel(out_path, index=False, engine="openpyxl")
    print(f"已保存到: {out_path}，共 {len(df)} 条。")


def main():
    script_dir = Path(__file__).resolve().parent
    out_path = script_dir / "中医方剂列表.xlsx"

    print(f"正在请求: {TARGET_URL}")
    html = fetch_page(TARGET_URL)
    if not html:
        return

    rows = parse_fangji_links(html)
    if not rows:
        print("未解析到任何方剂链接，请检查页面结构或选择器。")
        return

    save_to_excel(rows, out_path)


if __name__ == "__main__":
    main()
