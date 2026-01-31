from neo4j import GraphDatabase
from common.config import Config
from tqdm import tqdm
import json

conf = Config()


class Neo4jClient:
    def __init__(self, uri, user, password):
        """初始化连接"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def __del__(self):
        """关闭连接"""
        if self.driver is not None:
            self.driver.close()

    def run_cypher(self, query, parameters=None):
        """
        执行一条 Cypher 语句并返回结果
        :param query: Cypher 查询语句
        :param parameters: 可选参数字典
        :return: 查询结果列表（每一行是一个 dict）
        """
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def run_multiple_cypher(self, queries_with_params):
        """
        执行多条 Cypher 语句，使用事务，并显示 tqdm 进度条。

        参数:
            queries_with_params: List[Tuple[str, Dict]]
                形式如: [("CREATE (n:Test {name: $name})", {"name": "Alice"}), ...]
        """
        with self.driver.session() as session:
            def transaction_logic(tx):
                for query, params in tqdm(queries_with_params, desc="执行 Cypher 语句"):
                    tx.run(query, params or {})

            session.execute_write(transaction_logic)

    def run_multiple_cypher_read(self, queries_with_params):
        """
        执行多条 Cypher 语句查询，并显示 tqdm 进度条。

        """
        all_results = []

        def transaction_logic(tx, q, p):
            res = tx.run(q, p)
            return [record.data() for record in res]

        for query, params in tqdm(queries_with_params, desc="执行 Cypher 语句"):
            with self.driver.session() as session:
                records = session.execute_read(transaction_logic, query, params or {})
                all_results.append(records)

        return all_results

    def export_tcm_metadata_to_json(self, output_path="tcm_metadata.json"):
        with self.driver.session() as session:

            # 1. 所有节点标签
            label_query = """
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN DISTINCT label
            """
            labels = [record["label"] for record in session.run(label_query)]

            # 2. 所有关系类型
            rel_query = """
            MATCH (n)-[r]-()
            RETURN DISTINCT type(r) AS rel_type
            """
            rel_types = [record["rel_type"] for record in session.run(rel_query)]

            # 3. 所有三元组结构
            triple_query = """
            MATCH (n)-[r]->(m)
            WITH head(labels(n)) AS from_label, type(r) AS rel_type, head(labels(m)) AS to_label
            RETURN DISTINCT from_label, rel_type, to_label
            """
            triples = [{
                "from": record["from_label"],
                "rel_type": record["rel_type"],
                "to": record["to_label"],
                "description": ""
            } for record in session.run(triple_query)]

            # 4. 节点属性（每个标签下的属性键）
            node_props_query = """
            MATCH (n)
            UNWIND labels(n) AS label
            UNWIND keys(n) AS prop
            RETURN DISTINCT label, prop
            ORDER BY label, prop
            """
            label_props = {}
            for record in session.run(node_props_query):
                label = record["label"]
                prop = record["prop"]
                if prop == "project":  # 忽略 project 字段
                    continue
                label_props.setdefault(label, []).append({
                    "name": prop,
                    "description": ""
                })

            # 5. 关系属性（每种关系下的属性键）
            rel_props_query = """
            MATCH (n)-[r]->(m)
            UNWIND keys(r) AS prop
            RETURN DISTINCT type(r) AS rel_type, prop
            ORDER BY rel_type, prop
            """
            rel_type_props = {}
            for record in session.run(rel_props_query):
                rel_type = record["rel_type"]
                prop = record["prop"]
                rel_type_props.setdefault(rel_type, []).append({
                    "name": prop,
                    "description": ""
                })

            # 构建 JSON
            json_obj = {
                "labels": [
                    {
                        "name": label,
                        "description": "",
                        "properties": label_props.get(label, [])
                    } for label in labels
                ],
                "relationships": [
                    {
                        "type": rel,
                        "description": "",
                        "properties": rel_type_props.get(rel, [])
                    } for rel in rel_types
                ],
                "triples": triples
            }

            # 保存到文件
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(json_obj, f, ensure_ascii=False, indent=2)

            return output_path

    def get_all_node_names(self, label: str = None):
        """
        获取指定标签下所有节点的 name 属性
        :param label: 节点标签（如 'Effect', 'Symptom', 'Disease'）
        :return: List[str]
        """
        if label is None:
            query = """
            MATCH (n)
            RETURN DISTINCT n.name AS name
            ORDER BY name
            """
        else:
            query = f"""
            MATCH (n:{label})
            RETURN DISTINCT n.name AS name
            ORDER BY name
            """
        with self.driver.session() as session:
            result = session.run(query)
            return [record["name"] for record in result if record["name"]]

    def validate_cypher(self, query: str) -> bool:
        """
        检测 Cypher 查询语句是否合法（语法层面）
        :param query: 待检测的 Cypher 语句
        :return: True 表示合法，False 表示不合法
        """
        try:
            with self.driver.session() as session:
                # 使用 EXPLAIN 只做解析，不执行
                session.run(f"EXPLAIN {query}")
            return True
        except Exception as e:
            print(f"Cypher 语法错误: {e}")
            return False

    def clear_database(self):
        """
        ⚠️ 删除数据库中所有节点、关系、索引与约束（慎用）
        """
        with self.driver.session() as session:
            # 删除所有节点与关系
            session.run("MATCH (n) DETACH DELETE n")

            # 删除所有索引
            indexes = session.run("SHOW INDEXES")
            for record in indexes:
                name = record.get("name")
                if name:
                    session.run(f"DROP INDEX {name}")

            # 删除所有约束
            constraints = session.run("SHOW CONSTRAINTS")
            for record in constraints:
                name = record.get("name")
                if name:
                    session.run(f"DROP CONSTRAINT {name}")

        print("✅ 已清空数据库：所有节点、关系、索引与约束均已删除！")

neo4j_client = Neo4jClient(conf.NEO4J_URI, conf.NEO4J_USER, conf.NEO4J_PASSWORD)


# ---------------- 使用示例 ----------------
if __name__ == "__main__":
    neo4j_client = Neo4jClient(conf.NEO4J_URI, conf.NEO4J_USER, conf.NEO4J_PASSWORD)

    # # 插入两个节点和关系
    # neo4j_client.run_cypher("CREATE (a:Person {name:$name, age:$age})", {"name": "CaoCao", "age": 30})
    # neo4j_client.run_cypher("CREATE (b:Person {name:$name, age:$age})", {"name": "LiuBei", "age": 25})
    # neo4j_client.run_cypher("""
    #     MATCH (a:Person {name:$name1}), (b:Person {name:$name2})
    #     CREATE (a)-[:ENEMY_OF]->(b)
    # """, {"name1": "CaoCao", "name2": "LiuBei"})


    # 检索所有的人
    # result = neo4j_client.run_cypher("MATCH (n:Person) RETURN n")
    # print(result)

    # # 检索所有的敌对关系
    # result = neo4j_client.run_cypher("MATCH (n:Person)-[:ENEMY_OF]->(m:Person) RETURN n, m")
    # print(result)

    # neo4j_client = Neo4jClient(conf.NEO4J_URI, conf.NEO4J_USER, conf.NEO4J_PASSWORD)
    # queries_with_params = [("MATCH (n:Employee2) RETURN n LIMIT 5",{}),("MATCH (n:Employee) RETURN n LIMIT 5",{})]
    # result = neo4j_client.run_multiple_cypher_read(queries_with_params)
    # print(result)

    print(neo4j_client.get_all_node_names())