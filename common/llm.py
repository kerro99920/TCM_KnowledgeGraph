from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from common.config import Config

conf = Config()

# ============ 配置llm区域 ============
my_llm = ChatOpenAI(
    api_key=conf.MODEL_API_KEY,
    base_url=conf.MODEL_BASE_URL,
    model=conf.MODEL_NAME
)

if __name__ == '__main__':
    # 构造对话消息
    messages = [
        HumanMessage(content="用一句话介绍一下你自己")
    ]
    # 调用模型
    response = my_llm.invoke(messages)
    print(response.content)
