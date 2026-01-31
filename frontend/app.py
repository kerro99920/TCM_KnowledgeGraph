"""
TCM Knowledge Graph - Frontend Application
基于 Streamlit 的中医知识图谱前端界面
"""

import streamlit as st
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.neo4j_manager import neo4j_client
from common.llm import my_llm

# Page configuration
st.set_page_config(
    page_title="中医知识图谱",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E7D32;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .entity-tag {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        margin: 0.25rem;
        border-radius: 15px;
        background-color: #E8F5E9;
        color: #2E7D32;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/traditional-medicine.png", width=80)
    st.title("中医知识图谱")
    st.markdown("---")

    page = st.radio(
        "功能导航",
        ["🏠 首页", "🔍 知识查询", "💬 智能问答", "📊 图谱统计", "⚙️ 系统设置"]
    )

# Main content
if page == "🏠 首页":
    st.markdown('<h1 class="main-header">🏥 中医知识图谱系统</h1>', unsafe_allow_html=True)

    st.markdown("""
    ### 欢迎使用中医知识图谱系统

    本系统基于 **Neo4j 图数据库** 和 **大语言模型 (LLM)** 构建，提供：

    - 🔍 **知识查询**: 查询中药、方剂、疾病等实体信息
    - 💬 **智能问答**: 基于知识图谱的智能问答
    - 📊 **图谱统计**: 可视化展示知识图谱结构
    """)

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)

    try:
        # Get stats from Neo4j
        with neo4j_client.driver.session() as session:
            herb_count = session.run("MATCH (n:Herb) RETURN count(n) as count").single()["count"]
            formula_count = session.run("MATCH (n:Formula) RETURN count(n) as count").single()["count"]
            disease_count = session.run("MATCH (n:Disease) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

        with col1:
            st.metric("🌿 中药", herb_count)
        with col2:
            st.metric("📜 方剂", formula_count)
        with col3:
            st.metric("🏥 疾病", disease_count)
        with col4:
            st.metric("🔗 关系", rel_count)
    except Exception as e:
        st.warning(f"无法连接数据库: {e}")
        with col1:
            st.metric("🌿 中药", "-")
        with col2:
            st.metric("📜 方剂", "-")
        with col3:
            st.metric("🏥 疾病", "-")
        with col4:
            st.metric("🔗 关系", "-")

elif page == "🔍 知识查询":
    st.header("🔍 知识查询")

    query_type = st.selectbox(
        "选择查询类型",
        ["中药查询", "方剂查询", "疾病查询", "自定义 Cypher"]
    )

    if query_type == "中药查询":
        herb_name = st.text_input("输入中药名称", placeholder="例如：人参、黄芪")
        if st.button("查询", key="herb_search"):
            if herb_name:
                try:
                    with neo4j_client.driver.session() as session:
                        result = session.run("""
                            MATCH (h:Herb {name: $name})
                            OPTIONAL MATCH (h)-[r]->(target)
                            RETURN h, collect({rel: type(r), target: target.name}) as relations
                        """, name=herb_name)
                        record = result.single()
                        if record:
                            herb = record["h"]
                            relations = record["relations"]

                            st.success(f"找到中药：{herb_name}")

                            # Display properties
                            st.subheader("属性信息")
                            props = dict(herb)
                            for key, value in props.items():
                                if value and key != "name":
                                    st.write(f"**{key}**: {value}")

                            # Display relations
                            if relations and relations[0]["rel"]:
                                st.subheader("关联关系")
                                for rel in relations:
                                    if rel["rel"]:
                                        st.write(f"- {rel['rel']} → {rel['target']}")
                        else:
                            st.warning(f"未找到中药：{herb_name}")
                except Exception as e:
                    st.error(f"查询失败: {e}")

    elif query_type == "方剂查询":
        formula_name = st.text_input("输入方剂名称", placeholder="例如：四君子汤、桂枝汤")
        if st.button("查询", key="formula_search"):
            if formula_name:
                try:
                    with neo4j_client.driver.session() as session:
                        result = session.run("""
                            MATCH (f:Formula {name: $name})
                            OPTIONAL MATCH (f)-[r]->(target)
                            RETURN f, collect({rel: type(r), target: target.name, type: labels(target)[0]}) as relations
                        """, name=formula_name)
                        record = result.single()
                        if record:
                            formula = record["f"]
                            relations = record["relations"]

                            st.success(f"找到方剂：{formula_name}")

                            # Display properties
                            st.subheader("方剂信息")
                            props = dict(formula)
                            for key, value in props.items():
                                if value and key != "name":
                                    st.write(f"**{key}**: {value}")

                            # Display ingredients
                            ingredients = [r for r in relations if r["rel"] == "HAS_INGREDIENT"]
                            if ingredients:
                                st.subheader("药物组成")
                                herb_names = [r["target"] for r in ingredients if r["target"]]
                                st.write("、".join(herb_names))

                            # Display other relations
                            other_rels = [r for r in relations if r["rel"] != "HAS_INGREDIENT" and r["rel"]]
                            if other_rels:
                                st.subheader("其他关系")
                                for rel in other_rels:
                                    st.write(f"- {rel['rel']} → {rel['target']}")
                        else:
                            st.warning(f"未找到方剂：{formula_name}")
                except Exception as e:
                    st.error(f"查询失败: {e}")

    elif query_type == "疾病查询":
        disease_name = st.text_input("输入疾病名称", placeholder="例如：感冒、咳嗽")
        if st.button("查询", key="disease_search"):
            if disease_name:
                try:
                    with neo4j_client.driver.session() as session:
                        result = session.run("""
                            MATCH (d:Disease {name: $name})
                            OPTIONAL MATCH (other)-[r]->(d)
                            RETURN d, collect({rel: type(r), source: other.name, type: labels(other)[0]}) as treatments
                        """, name=disease_name)
                        record = result.single()
                        if record:
                            disease = record["d"]
                            treatments = record["treatments"]

                            st.success(f"找到疾病：{disease_name}")

                            if treatments and treatments[0]["rel"]:
                                st.subheader("相关治疗")
                                for t in treatments:
                                    if t["rel"]:
                                        st.write(f"- {t['source']} ({t['type']}) - {t['rel']}")
                        else:
                            st.warning(f"未找到疾病：{disease_name}")
                except Exception as e:
                    st.error(f"查询失败: {e}")

    elif query_type == "自定义 Cypher":
        cypher = st.text_area(
            "输入 Cypher 查询语句",
            placeholder="MATCH (n) RETURN n LIMIT 10",
            height=100
        )
        if st.button("执行查询", key="cypher_search"):
            if cypher:
                try:
                    with neo4j_client.driver.session() as session:
                        result = session.run(cypher)
                        records = list(result)
                        if records:
                            st.success(f"查询成功，返回 {len(records)} 条记录")
                            for record in records[:20]:  # Limit display
                                st.json(dict(record))
                        else:
                            st.info("查询无结果")
                except Exception as e:
                    st.error(f"查询失败: {e}")

elif page == "💬 智能问答":
    st.header("💬 智能问答")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("请输入您的问题，例如：黄芪有什么功效？"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    # Query related knowledge from Neo4j
                    context = ""
                    with neo4j_client.driver.session() as session:
                        # Search for relevant entities
                        result = session.run("""
                            MATCH (n)
                            WHERE n.name CONTAINS $keyword
                            OPTIONAL MATCH (n)-[r]->(m)
                            RETURN labels(n)[0] as type, n.name as name,
                                   collect({rel: type(r), target: m.name})[..5] as relations
                            LIMIT 5
                        """, keyword=prompt[:10])

                        records = list(result)
                        if records:
                            context = "相关知识：\n"
                            for record in records:
                                context += f"- {record['type']}: {record['name']}\n"
                                for rel in record["relations"]:
                                    if rel["rel"]:
                                        context += f"  - {rel['rel']}: {rel['target']}\n"

                    # Call LLM
                    full_prompt = f"""你是一个中医知识专家。请根据以下知识库信息回答用户问题。

{context}

用户问题：{prompt}

请用简洁专业的语言回答："""

                    response = my_llm.invoke(full_prompt)
                    answer = response.content if hasattr(response, 'content') else str(response)

                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    error_msg = f"抱歉，处理您的问题时出错：{e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

    # Clear chat button
    if st.button("清空对话"):
        st.session_state.messages = []
        st.rerun()

elif page == "📊 图谱统计":
    st.header("📊 图谱统计")

    try:
        with neo4j_client.driver.session() as session:
            # Entity type statistics
            st.subheader("实体类型分布")
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as type, count(n) as count
                ORDER BY count DESC
            """)

            entity_stats = {record["type"]: record["count"] for record in result}

            if entity_stats:
                import pandas as pd
                df = pd.DataFrame(list(entity_stats.items()), columns=["类型", "数量"])
                st.bar_chart(df.set_index("类型"))
                st.dataframe(df)

            # Relationship statistics
            st.subheader("关系类型分布")
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)

            rel_stats = {record["type"]: record["count"] for record in result}

            if rel_stats:
                df_rel = pd.DataFrame(list(rel_stats.items()), columns=["关系", "数量"])
                st.bar_chart(df_rel.set_index("关系"))
                st.dataframe(df_rel)

    except Exception as e:
        st.error(f"无法获取统计信息: {e}")

elif page == "⚙️ 系统设置":
    st.header("⚙️ 系统设置")

    st.subheader("数据库连接")

    # Check Neo4j connection
    try:
        with neo4j_client.driver.session() as session:
            session.run("RETURN 1")
        st.success("✅ Neo4j 数据库连接正常")
    except Exception as e:
        st.error(f"❌ Neo4j 连接失败: {e}")

    st.subheader("系统信息")
    st.write(f"- Python 版本: {sys.version}")
    st.write(f"- 项目路径: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")

    st.subheader("使用说明")
    st.markdown("""
    1. **知识查询**: 支持按中药、方剂、疾病名称查询，也支持自定义 Cypher 查询
    2. **智能问答**: 输入自然语言问题，系统会结合知识图谱给出回答
    3. **图谱统计**: 查看知识图谱的实体和关系分布情况
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>TCM Knowledge Graph © 2025 | Powered by Neo4j & LLM</div>",
    unsafe_allow_html=True
)
