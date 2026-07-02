"""Streamlit 前端：所有数据均通过 FastAPI 后端获取，不直连 Neo4j/LLM。"""

import os

import requests
import streamlit as st

API_BASE = os.getenv("TCM_API_BASE", "http://127.0.0.1:8000")
START_HINT = "后端未启动？在项目根目录执行: uv run --project app tcm serve"

st.set_page_config(
    page_title="中医知识图谱",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


def api(method: str, path: str, **kwargs):
    """调用后端 API，返回 (data, error)。"""
    try:
        resp = requests.request(method, f"{API_BASE}{path}", timeout=180, **kwargs)
    except requests.exceptions.ConnectionError:
        return None, f"无法连接后端 API（{API_BASE}）。{START_HINT}"
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试。"
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        return None, f"请求失败（{resp.status_code}）: {detail}"
    return resp.json(), None


@st.cache_data(ttl=3600)
def load_schema():
    data, err = api("GET", "/api/v1/knowledge/schema")
    return data, err


with st.sidebar:
    st.title("🌿 中医知识图谱")
    st.caption(f"后端: {API_BASE}")
    st.markdown("---")
    page = st.radio(
        "功能导航",
        ["首页", "知识查询", "智能问答", "Cypher 查询", "系统状态"],
    )

if page == "首页":
    st.header("中医知识图谱系统")
    st.markdown(
        "基于 **Neo4j + LLM (LangGraph Text2Cypher)** 的中医知识图谱问答系统。\n\n"
        "- **知识查询**: 按实体类型与名称查询图谱（自动别名对齐）\n"
        "- **智能问答**: 自然语言问题 → Cypher 检索 → 图谱增强回答\n"
        "- **Cypher 查询**: 只读 Cypher（经安全校验）\n"
    )

    stats, err = api("GET", "/api/v1/knowledge/stats")
    if err:
        st.warning(err)
    else:
        schema, _ = load_schema()
        zh = {k: v["zh"] for k, v in (schema or {}).get("labels", {}).items()}
        cols = st.columns(len(stats["labels"]) + 1)
        for col, (label, count) in zip(cols, stats["labels"].items()):
            col.metric(f"{zh.get(label, label)} {label}", count)
        cols[-1].metric("关系总数", stats["total_relations"])

        st.subheader("关系分布")
        st.bar_chart(stats["relations"])

elif page == "知识查询":
    st.header("知识查询")

    schema, err = load_schema()
    if err:
        st.error(err)
        st.stop()

    labels = schema["labels"]
    label = st.selectbox(
        "实体类型",
        options=list(labels),
        format_func=lambda x: f"{labels[x]['zh']} ({x})",
    )
    name = st.text_input("实体名称", placeholder="例如：黄芪、四君子汤（支持常见别名，如 北芪）")

    if st.button("查询", type="primary") and name:
        data, err = api("GET", f"/api/v1/knowledge/entity/{label}/{name}")
        if err:
            st.warning(err)
            # 精确匹配失败时走模糊检索
            hits, err2 = api(
                "POST",
                "/api/v1/knowledge/search",
                json={"query": name, "entity_types": [label], "limit": 10},
            )
            if not err2 and hits:
                st.info("你可能想找：" + "、".join(h["name"] for h in hits))
        else:
            st.success(f"{labels[label]['zh']}：{data['entity_id']}")

            props = {k: v for k, v in data["data"].items() if v and k != "name"}
            if props:
                st.subheader("属性")
                for k, v in props.items():
                    st.write(f"**{k}**: {v}")

            related = data.get("related_entities", [])
            if related:
                st.subheader("关联关系")
                out_rels = [r for r in related if r["direction"] == "out"]
                in_rels = [r for r in related if r["direction"] == "in"]
                col1, col2 = st.columns(2)
                with col1:
                    st.caption("出边（本实体 → 其他）")
                    for r in out_rels:
                        st.write(f"- [{r['rel']}] → {r['name']} ({r.get('label', '')})")
                with col2:
                    st.caption("入边（其他 → 本实体）")
                    for r in in_rels:
                        st.write(f"- {r['name']} ({r.get('label', '')}) → [{r['rel']}]")

elif page == "智能问答":
    st.header("智能问答")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("cypher"):
                with st.expander("查看图谱检索 Cypher"):
                    st.code(msg["cypher"], language="cypher")

    if prompt := st.chat_input("请输入您的问题，例如：四君子汤由哪些药组成？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("检索图谱并生成回答..."):
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ][-8:]
                data, err = api(
                    "POST",
                    "/api/v1/chat",
                    json={"message": prompt, "history": history},
                )
            if err:
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
            else:
                st.markdown(data["message"])
                if data.get("graph_query"):
                    with st.expander("查看图谱检索 Cypher"):
                        st.code(data["graph_query"], language="cypher")
                if data.get("sources"):
                    names = {s.get("name") for s in data["sources"] if s.get("name")}
                    if names:
                        st.caption("来源实体: " + "、".join(sorted(names)))
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data["message"],
                    "cypher": data.get("graph_query"),
                })

    if st.session_state.messages and st.button("清空对话"):
        st.session_state.messages = []
        st.rerun()

elif page == "Cypher 查询":
    st.header("Cypher 查询（只读）")
    st.caption("写操作（CREATE/DELETE/SET 等）与白名单外的标签/关系将被拒绝；无 LIMIT 时自动补 LIMIT 50。")

    cypher = st.text_area(
        "Cypher 语句",
        placeholder="MATCH (f:Formula)-[:HAS_INGREDIENT]->(h:Herb) RETURN f.name, collect(h.name) LIMIT 10",
        height=120,
    )
    if st.button("执行查询", type="primary") and cypher:
        data, err = api("POST", "/api/v1/knowledge/query", json={"cypher": cypher})
        if err:
            st.error(err)
        else:
            results = data["raw_results"]
            st.caption(f"实际执行: `{data['executed_cypher']}`")
            if results:
                st.success(f"返回 {len(results)} 条记录")
                st.dataframe(results)
            else:
                st.info("查询无结果")

elif page == "系统状态":
    st.header("系统状态")

    health, err = api("GET", "/health")
    if err:
        st.error(err)
    else:
        status = health.get("status", "unknown")
        (st.success if status == "healthy" else st.warning)(f"服务状态: {status}")
        st.write(f"- 版本: {health.get('version')}")
        for comp, s in health.get("components", {}).items():
            icon = "✅" if s == "healthy" else "❌"
            st.write(f"- {comp}: {icon} {s}")

    schema, err = load_schema()
    if not err:
        st.subheader("统一 Schema")
        st.json(schema)

st.markdown("---")
st.caption("TCM Knowledge Graph | FastAPI + LangGraph + Neo4j")
