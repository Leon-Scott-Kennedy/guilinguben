from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "guilinguben-ai"
    environment: str = "local"
    server_host: str = "0.0.0.0"
    server_port: int = 8001
    
    # Use absolute paths by resolving relative to BASE_DIR
    embedding_model_path: str = str(BASE_DIR / "models" / "bge-large-zh-v1.5")
    source_pdf_path: str = str(BASE_DIR / "guilinguben.pdf")
    
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"
    # 向量库后端开关：faiss（本地 MVP，默认）/ milvus（16.33，已停用）/ chroma（16.37）
    vector_backend: str = "faiss"
    milvus_uri: str = "http://localhost:19530"
    milvus_collection_name: str = "guilinguben_chunks"
    # Chroma 嵌入式持久化（本地目录，零容器零额外进程）
    chroma_persist_dir: str = str(BASE_DIR / "data" / "chroma_index")
    chroma_collection_name: str = "guilinguben_chunks"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    # 内部 API Key（预留，D 轮 16.40 取舍三）：非空时所有接口校验 X-Api-Key 请求头；
    # 当前为空 = 不启用（Java 直连本机开发），生产由部署方配置并与 Java ai-service.api-key 配对启用
    ai_service_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
