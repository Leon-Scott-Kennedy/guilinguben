# ============================================================
# ai-service 容器化（E 轮 16.42 方案丙可选资产，默认不启用）
# 构建上下文必须是项目根目录（compose：context: . / dockerfile: services/ai-service/Dockerfile）：
#   docker build -f services/ai-service/Dockerfile -t guilinguben-ai .
# 路径语义：config.py BASE_DIR = parents[3] → 容器内 /app/app/config.py 解析为 /，
#   因此运行须挂载 ./models:/models ./data:/data ./guilinguben.pdf:/guilinguben.pdf（compose 已配置）。
# 环境覆盖：容器内无 .env（env_file 按工作目录解析且已 dockerignore），
#   本机 .env 中的 Windows 绝对路径由以下 ENV 覆盖（pydantic-settings 环境变量优先级高于 .env）：
#   LLM_BASE_URL → 宿主机 Ollama；VECTOR_BACKEND=chroma（当前项目默认后端，可改 faiss）；
#   CHROMA_PERSIST_DIR=/data/chroma_index（挂载卷）；模型/PDF 路径指向根挂载点。
# 构建注意：sentence-transformers 会拉取 torch（Linux 默认 CUDA 版镜像体积大，仅演示资产用）。
# ============================================================

FROM python:3.12-slim
WORKDIR /app

COPY services/ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ai-service/app ./app

ENV LLM_BASE_URL=http://host.docker.internal:11434 \
    VECTOR_BACKEND=chroma \
    CHROMA_PERSIST_DIR=/data/chroma_index \
    EMBEDDING_MODEL_PATH=/models/bge-large-zh-v1.5 \
    SOURCE_PDF_PATH=/guilinguben.pdf

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
