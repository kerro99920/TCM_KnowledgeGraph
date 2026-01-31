"""
Neo4j 客户端封装（Demo）
放在 __000__demo 目录下，可从项目根目录运行：python -m __000__demo.neo4j_client
"""
import os
import sys
import json

# 保证能导入 common 和加载项目根目录的 .env
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"))

from neo4j import GraphDatabase
from tqdm import tqdm


def _get_config():
    """从环境变量读取 Neo4j 配置"""
    return {
        "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", ""),
    }


class Neo4jClient:
    """Neo4j 图数据库客户端"""

    def __init__(self, uri=None, user=None, password=None):
        """
        初始化连接。
        若不传参数，则从环境变量 NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 读取。
        """
        cfg = _get_config()
        self.uri = uri or cfg["uri"]
        self.user = user or cfg["user"]
        self.password = password if password is not None else cfg["password"]
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def __del__(self):
        """关闭连接"""
        if getattr(self, "driver", None) is not None:
            try:
                self.driver.close()
            except Exception:
                pass

    def close(self):
        """显式关闭驱动"""
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def run_cypher(self, query, parameters=None):
        """
        执行一条 Cypher 语句并返回结果。
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
        :param queries_with_params: List[Tuple[str, Dict]]，如 [("CREATE (n:Test {name: $name})", {"name": "Alice"}), ...]
        """
        with self.driver.session() as session:
            def transaction_logic(tx):
                for query, params in tqdm(queries_with_params, desc="执行 Cypher 语句"):
                    tx.run(query, params or {})

            session.execute_write(transaction_logic)

    def run_multiple_cypher_read(self, queries_with_params):
        """
        执行多条 Cypher 查询，并显示 tqdm 进度条。
        :param queries_with_params: List[Tuple[str, Dict]]
        :return: List[List[dict]] 每条查询的结果列表
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

    def get_all_node_names(self, label=None):
        """
        获取指定标签下所有节点的 name 属性。
        :param label: 节点标签（如 'Effect', 'Symptom', 'Disease'），None 表示所有节点
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
        检测 Cypher 查询语句是否合法（语法层面）。
        :param query: 待检测的 Cypher 语句
        :return: True 表示合法，False 表示不合法
        """
        try:
            with self.driver.session() as session:
                session.run(f"EXPLAIN {query}")
            return True
        except Exception as e:
            print(f"Cypher 语法错误: {e}")
            return False

    def clear_database(self):
        """删除数据库中所有节点、关系、索引与约束（慎用）"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            indexes = session.run("SHOW INDEXES")
            for record in indexes:
                name = record.get("name")
                if name:
                    session.run(f"DROP INDEX {name}")
            constraints = session.run("SHOW CONSTRAINTS")
            for record in constraints:
                name = record.get("name")
                if name:
                    session.run(f"DROP CONSTRAINT {name}")
        print("✅ 已清空数据库：所有节点、关系、索引与约束均已删除！")


# --------------- 使用示例 ---------------
if __name__ == "__main__":
    client = Neo4jClient()

    # 示例：执行一条查询
    # result = client.run_cypher("MATCH (n) RETURN n LIMIT 5")
    # print(json.dumps(result, ensure_ascii=False, indent=2))

    # 示例：获取所有节点名称
    names = client.get_all_node_names()
    print("节点 name 数量:", len(names))
    if names:
        print("示例:", names[:5])

    client.close()
