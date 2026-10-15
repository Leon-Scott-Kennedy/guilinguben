"""集中管理所有配置项"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator

# 项目根目录（src/config/ 的上一级）
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    # 模型配置
    embedding_model_path: str = "models/bge-large-zh-v1.5"
    llm_model_name: str = "qwen2.5:7b"
    llm_temperature: float = 0.2
    llm_base_url: str = "http://localhost:11434"

    # 检索配置
    top_k: int = 5
    display_k: int = 3

    # 数据路径
    data_path: str = "data/桂林古本方剂提取结果.json"

    # 应用配置
    app_mode: str = "web"
    debug: bool = True

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"

    # ========== 关键：将 .env 中的相对路径转为绝对路径 ==========
    @field_validator("embedding_model_path", "data_path")
    @classmethod
    def resolve_path(cls, v: str) -> str:
        """如果是相对路径，则基于 PROJECT_ROOT 转为绝对路径"""
        path = Path(v)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)


# 单例实例
settings = Settings()