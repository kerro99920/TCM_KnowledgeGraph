# TCM Knowledge Graph (中医知识图谱)

基于 LLM + Neo4j 的中医知识图谱构建与问答系统。

**单一实现**：核心代码全部在 `app/`（FastAPI + LangGraph Text2Cypher），`frontend/` 是纯 HTTP 薄客户端（Streamlit），不直连数据库或 LLM。

## 系统架构

```
┌──────────┐   ┌───────────────┐   ┌─────────┐
│ Crawler  │──>│ TripleExtract │──>│ Alpaca  │
│ (爬虫)   │   │ (LLM 三元组)  │   │  JSON   │
└──────────┘   └───────────────┘   └────┬────┘
                                        │ tcm db import-alpaca
                                        v （实体对齐 + UNWIND/MERGE）
┌──────────┐   ┌───────────────┐   ┌─────────┐
│Streamlit │──>│    FastAPI    │──>│  Neo4j  │
│ (前端)   │HTTP│  + LangGraph  │   │ (图谱)  │
└──────────┘   │  Text2Cypher  │   └─────────┘
               │  + CypherGuard│
               └───────────────┘
```

问答链路：意图路由 → 实体识别（别名归一化）→ Text2Cypher（只读校验 + 白名单）→ 图谱增强回答。

## 快速开始

依赖 [uv](https://docs.astral.sh/uv/)，无需手动创建虚拟环境。

```bash
# 1. 配置环境变量
cp .env.example .env   # 填入 MODEL_API_KEY / NEO4J_PASSWORD 等

# 2. 启动 Neo4j（本机或 Docker）

# 3. 启动后端 API（http://localhost:8000，文档 /docs）
uv run --project app tcm serve        # Windows 可直接双击 run_api.bat

# 4. 启动前端（http://localhost:8501）
uv run --no-project --with "streamlit>=1.35" streamlit run frontend/app.py
                                      # Windows 可直接双击 run_frontend.bat
```

### 数据构建流程

```bash
# 爬取原始文本（可选，已有文本可跳过）
uv run --project app tcm crawl medicine --limit 100

# LLM 抽取三元组 → Alpaca JSON
uv run --project app tcm extract triples data/raw/medicines -o data/medicine_alpaca.json

# 导入 Neo4j（实体对齐 + 批量 UNWIND/MERGE，可加 --clear 先清库）
uv run --project app tcm db import-alpaca data/medicine_alpaca.json

# 查看图谱规模
uv run --project app tcm db status
```

### CLI 一览

| 命令 | 说明 |
|------|------|
| `tcm serve` | 启动 FastAPI 服务 |
| `tcm chat` | 终端交互问答（与 API 同一链路） |
| `tcm crawl medicine/prescription` | 爬取原始文本 |
| `tcm extract triples <dir> -o <json>` | 三元组抽取（输出 Alpaca 格式） |
| `tcm db import-alpaca <json...>` | 导入图谱（`--clear` 先清库） |
| `tcm db status / query / clear` | 图谱统计 / 只读查询 / 清库 |

## 统一 Schema

唯一权威定义在 `app/src/tcm_kgraph/graph_schema.py`（抽取、导入、Text2Cypher、API 全部引用它）。

### 节点标签（唯一键属性均为 `name`）

| 标签 | 说明 | 主要属性 |
|------|------|----------|
| `Herb` | 中药材 | name, alias, property_flavor(性味), meridian(归经), effect, indication, dosage, usage, taboo, origin, place, processing, traits |
| `Formula` | 方剂 | name, alias, effect, indication, usage, taboo |
| `Disease` | 疾病 | name |
| `Symptom` | 症状 | name |
| `Effect` | 功效 | name |
| `Source` | 文献出处 | name |

### 关系类型（方向固定）

| 关系 | 三元组模式 | 说明 |
|------|-----------|------|
| `HAS_INGREDIENT` | (Formula)→(Herb) | 方剂包含药材（属性 dosage/role） |
| `TREATS_DISEASE` | (Herb\|Formula)→(Disease) | 治疗疾病 |
| `ALLEVIATES_SYMPTOM` | (Herb\|Formula)→(Symptom) | 缓解症状 |
| `HAS_EFFECT` | (Herb\|Formula)→(Effect) | 具有功效 |
| `HAS_SYMPTOM` | (Disease)→(Symptom) | 疾病表现症状 |
| `FROM_SOURCE` | (Herb\|Formula)→(Source) | 出自文献 |

### 实体对齐

导入与查询时对实体名做归一化：NFKC → 去空白 → 异体字映射（蔘→参 等）→ 别名表（北芪→黄芪、元胡→延胡索 等），见 `graph_schema.ENTITY_ALIASES`。

### 安全防线（Text2Cypher）

LLM 生成的 Cypher 必须通过 `database/cypher_guard.py` 校验后才执行：

- 只读：禁止 CREATE/MERGE/DELETE/SET/REMOVE/CALL/LOAD 等写操作与过程调用；
- 白名单：节点标签与关系类型必须在统一 schema 内；
- 兜底：无 LIMIT 自动追加 `LIMIT 50`；拒绝反引号标识符。

`/api/v1/knowledge/query` 与 `tcm db query` 也走同一防线。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | 智能问答（返回回答 + 实际执行的 Cypher + 来源） |
| GET | `/api/v1/knowledge/schema` | 统一 schema 定义 |
| GET | `/api/v1/knowledge/stats` | 图谱规模统计 |
| GET | `/api/v1/knowledge/entity/{label}/{name}` | 实体详情（含出入边，名称自动对齐） |
| POST | `/api/v1/knowledge/search` | 名称模糊检索 |
| POST | `/api/v1/knowledge/query` | 只读 Cypher（经安全校验） |
| GET | `/health` | 健康检查 |

## 目录结构

```
├── .env.example              # 环境变量模板（MODEL_* / NEO4J_*）
├── run_api.bat / run_frontend.bat
├── frontend/app.py           # Streamlit 薄客户端（仅 HTTP 调后端）
├── docs/复习笔记.md          # 知识图谱/Cypher/Text2Cypher 复习笔记
└── app/                      # 唯一核心实现
    ├── pyproject.toml
    ├── src/tcm_kgraph/
    │   ├── graph_schema.py   # ★ 统一 schema + 别名表 + 白名单
    │   ├── agents/           # LangGraph 问答工作流
    │   ├── api/              # FastAPI 路由
    │   ├── cli/              # typer CLI（serve/chat/crawl/extract/db）
    │   ├── crawlers/         # 异步爬虫
    │   ├── database/         # Neo4j 客户端 + cypher_guard 安全防线
    │   ├── extraction/       # LLM 三元组抽取 + 提示词
    │   ├── ingest/           # Alpaca JSON 批量导入
    │   ├── llm/              # LLM 客户端
    │   └── models/           # API DTO
    └── tests/                # 单元测试（uv run --no-project --with pytest python -m pytest tests/unit）
```

## 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `MODEL_API_KEY` | LLM API 密钥（OpenAI 兼容） | `sk-xxx` |
| `MODEL_BASE_URL` | API 基础 URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | 模型名称 | `qwen3-max` |
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j 账号 | `neo4j` / `...` |
| `TCM_API_BASE` | 前端调用的后端地址（可选） | `http://127.0.0.1:8000` |

## 许可证

MIT，详见 [LICENSE](LICENSE)。
