from sentence_transformers import SentenceTransformer
from common.config import Config

conf = Config()

embedding_model = SentenceTransformer(conf.EMBEDDING_MODEL_PATH)
