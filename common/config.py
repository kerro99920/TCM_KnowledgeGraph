import os
from dotenv import load_dotenv

from common.path_utils import get_file_path

load_dotenv()
# load_dotenv(r"D:\workspace\workspace-python\k_graph_1\.env")


class Config:
    def __init__(self):
        # 大模型相关
        self.MODEL_API_KEY = os.getenv("MODEL_API_KEY")
        self.MODEL_BASE_URL = os.getenv("MODEL_BASE_URL")
        self.MODEL_NAME = os.getenv("MODEL_NAME")

        # neo4j相关
        self.NEO4J_URI = os.getenv("NEO4J_URI")
        self.NEO4J_USER = os.getenv("NEO4J_USER")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

        # 读取极梦的密钥
        # self.JIMENG_AK = os.getenv("JIMENG_AK")
        # self.JIMENG_SK = os.getenv("JIMENG_SK")

        # 读取图谱模式层的数据
        # self.TCM_METADATA = open(get_file_path("__003__create_neo4j_database/tcm_metadata.json"), "r",encoding='utf-8').read()

        # embedding模型
        self.EMBEDDING_MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH")
        #
        # # index的路径
        # self.ENTITY_INDEX_PATH = get_file_path("__003__create_neo4j_database/nero4j_embedding_faiss.index")
        # self.ENTITY_ID2TEXT_PATH = get_file_path("__003__create_neo4j_database/nero4j_embedding_faiss_id2text.pkl")
        # 记忆轮次
        self.history_num = 5


if __name__ == "__main__":
    conf = Config()
    print(conf.EMBEDDING_MODEL_PATH)
