# TCM Knowledge Graph (中医知识图谱)

基于 LLM 和 Neo4j 的中医知识图谱构建与问答系统。

## 功能特性

- **数据爬取**: 自动爬取中药、方剂等中医知识数据
- **知识抽取**: 利用 LLM (通义千问) 从非结构化文本中抽取实体和关系
- **图谱构建**: 将抽取的知识存储到 Neo4j 图数据库
- **语义搜索**: 基于 BGE-M3 向量模型的语义检索
- **智能问答**: 结合知识图谱的 RAG 问答系统

## 系统架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Crawler   │───>│  Extraction │───>│   Neo4j     │
│   (爬虫)    │    │  (LLM抽取)  │    │   (图数据库) │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                            v
                   ┌─────────────┐    ┌─────────────┐
                   │   FastAPI   │<───│  LangGraph  │
                   │   (API服务) │    │  (智能Agent)│
                   └─────────────┘    └─────────────┘
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/tcm-knowledge-graph.git
cd tcm-knowledge-graph
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

### 4. 下载向量模型

BGE-M3 模型约 2.2GB，需要单独下载：

```bash
# 使用 huggingface-cli
huggingface-cli download BAAI/bge-m3 --local-dir ./model/bge-m3

# 或使用 modelscope (国内用户推荐)
modelscope download --model BAAI/bge-m3 --local_dir ./model/bge-m3
```

### 5. 启动 Neo4j

确保 Neo4j 数据库已启动，并配置正确的连接信息。

### 6. 运行

```bash
# 爬取数据
python crawler/crawl_zhongyao.py
python crawler/crawl_fangji.py

# 抽取知识
python extraction/extract_zhongyao_to_json.py
python extraction/extract_fangji_to_json.py

# 转换为 Alpaca 格式
python extraction/convert_zhongyao_to_alpaca.py
python extraction/convert_fangji_to_alpaca.py

# 导入 Neo4j
python database/import_alpaca_to_neo4j.py
```

## 目录结构

```
tcm-knowledge-graph/
├── .gitignore              # Git 忽略规则
├── .env.example            # 环境变量模板
├── README.md               # 项目说明
├── requirements.txt        # Python 依赖
├── LICENSE                 # MIT 许可证
├── common/                 # 公共模块
│   ├── config.py           # 配置管理
│   ├── llm.py              # LLM 客户端
│   ├── neo4j_manager.py    # Neo4j 客户端
│   ├── embedding_model.py  # 向量嵌入模型
│   └── path_utils.py       # 路径工具
├── crawler/                # 爬虫模块
│   ├── crawl_fangji.py     # 方剂爬虫
│   ├── crawl_zhongyao.py   # 中药爬虫
│   └── fetch_*.py          # 页面抓取
├── extraction/             # 信息提取模块
│   ├── extract_graph_utils.py      # 知识抽取工具
│   ├── extract_fangji_to_json.py   # 方剂抽取
│   ├── extract_zhongyao_to_json.py # 中药抽取
│   └── convert_*_to_alpaca.py      # 格式转换
├── database/               # 数据库模块
│   └── import_alpaca_to_neo4j.py   # Neo4j 导入
├── examples/               # 示例代码
│   ├── neo4j_client.py     # Neo4j 使用示例
│   └── request_test.py     # API 请求测试
├── model/                  # 模型目录 (gitignore)
│   └── bge-m3/             # BGE-M3 向量模型
├── picture/                # 图片资源
└── app/                    # 主应用模块
    ├── src/                # 源代码
    ├── tests/              # 测试代码
    ├── docker/             # Docker 配置
    └── pyproject.toml      # 项目配置
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `MODEL_API_KEY` | 通义千问 API 密钥 | `sk-xxx` |
| `MODEL_BASE_URL` | API 基础 URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | 模型名称 | `qwen3-max` |
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | `your_password` |
| `EMBEDDING_MODEL_PATH` | 向量模型路径 | `./model/bge-m3` |

## 知识图谱 Schema

### 实体类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `Herb` | 中药材 | 人参、黄芪 |
| `Formula` | 方剂 | 四君子汤、桂枝汤 |
| `Disease` | 疾病 | 感冒、肺炎 |
| `Symptom` | 症状 | 咳嗽、发热 |
| `Effect` | 功效 | 补气、活血 |
| `Source` | 出处 | 《本草纲目》 |

### 关系类型

| 关系 | 说明 | 示例 |
|------|------|------|
| `TREATS_DISEASE` | 治疗疾病 | 桂枝汤 → 感冒 |
| `ALLEVIATES_SYMPTOM` | 缓解症状 | 人参 → 乏力 |
| `HAS_EFFECT` | 具有功效 | 黄芪 → 补气 |
| `HAS_INGREDIENT` | 包含成分 | 四君子汤 → 人参 |
| `HAS_SYMPTOM` | 具有症状 | 感冒 → 发热 |
| `FROM_SOURCE` | 出自文献 | 桂枝汤 → 《伤寒论》 |

## 技术栈

- **LLM**: 通义千问 (Qwen)
- **向量模型**: BGE-M3
- **图数据库**: Neo4j
- **Web 框架**: FastAPI
- **Agent 框架**: LangGraph
- **编程语言**: Python 3.10+

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。
