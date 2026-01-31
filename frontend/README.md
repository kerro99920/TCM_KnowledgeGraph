# TCM Knowledge Graph Frontend

基于 Streamlit 的中医知识图谱前端界面。

## 功能

- 🏠 **首页**: 系统概览和统计数据
- 🔍 **知识查询**: 中药、方剂、疾病查询，支持自定义 Cypher
- 💬 **智能问答**: 基于知识图谱的 RAG 问答
- 📊 **图谱统计**: 实体和关系分布可视化
- ⚙️ **系统设置**: 数据库连接状态检查

## 运行

```bash
# 从项目根目录运行
cd F:\LLM\Tcm_KnowledgeGraph
streamlit run frontend/app.py

# 或指定端口
streamlit run frontend/app.py --server.port 8501
```

## 依赖

确保已安装 streamlit:

```bash
pip install streamlit
```

## 截图

启动后访问: http://localhost:8501
