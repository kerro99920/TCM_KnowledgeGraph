"""
Traverse crawler/medicine_details directory, call extract_tcm_knowledge to extract knowledge,
and save results as {'out_list': [...]} format JSON file.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.path_utils import get_file_path

try:
    from extraction.extract_graph_utils import extract_folder_to_outlist
except ImportError:
    from extract_graph_utils import extract_folder_to_outlist

FOLDER = "crawler/medicine_details"
OUTPUT_JSON = "extraction/medicine_extraction.json"


if __name__ == "__main__":
    folder_path = get_file_path(FOLDER)
    output_path = get_file_path(OUTPUT_JSON)
    extract_folder_to_outlist(folder_path, output_path)
    print(f"已保存: {output_path}")
