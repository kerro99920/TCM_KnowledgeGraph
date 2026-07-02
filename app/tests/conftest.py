"""pytest 配置：将 src 布局加入 sys.path，免安装即可运行单元测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
