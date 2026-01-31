"""
Convert prescription_extraction.json to Alpaca format and save as prescription_alpaca.json.
Input comes from original text in crawler/prescription_details, output is extracted JSON string.
"""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.path_utils import get_file_path

INSTRUCTION = "请从以下中医文本中抽取知识谱图结构,包括实体与关系."
RESULT_JSON = "extraction/prescription_extraction.json"
FOLDER = "crawler/prescription_details"
OUTPUT_JSON = "extraction/prescription_alpaca.json"


def convert_to_alpaca(result_json_path: str, folder_path: str, output_path: str) -> None:
    with open(result_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out_list = data.get("out_list", [])

    folder = Path(folder_path)
    files = sorted([f for f in folder.iterdir() if f.is_file()])
    n = min(len(files), len(out_list))

    alpaca_list = []
    for i in range(n):
        try:
            text = files[i].read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            text = ""
        alpaca_list.append({
            "instruction": INSTRUCTION,
            "input": text,
            "output": json.dumps(out_list[i], ensure_ascii=False),
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alpaca_list, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(alpaca_list)} 条 -> {output_path}")


if __name__ == "__main__":
    result_path = get_file_path(RESULT_JSON)
    folder_path = get_file_path(FOLDER)
    output_path = get_file_path(OUTPUT_JSON)
    convert_to_alpaca(result_path, folder_path, output_path)
