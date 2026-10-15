# 桂林古本智能辅助诊疗系统 (Guilinguben AI Assistant)

[![Java](https://img.shields.io/badge/Java-17-orange.svg)](https://openjdk.org/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.3-brightgreen.svg)](https://spring.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-purple.svg)](https://langchain-ai.github.io/langgraph/)

## 项目简介

基于 **Agentic RAG（检索增强生成 + 智能体）** 技术的中医古籍智能辅助诊疗系统。以《桂林古本伤寒杂病论》为核心知识库，结合本地私有化部署的大语言模型，为中医学习者、研究者及临床医生提供精准的古籍问答、原文溯源与选词解释服务。

## 核心特性

- **Agentic RAG**：LangGraph 状态机（guardrail → agent ⇄ tools → final_answer），LLM 通过 Function Calling 自主决策是否检索、检索什么，终结"误召回"造成的幻觉污染
- **精准溯源**：回答强制携带条文级 citations，支持点击跳转至 PDF 对应页码
- **SSE 流式输出**：三端 SSE 打通（Python 逐 token → Java WebFlux 转发 → 前端打字机），断连恢复三件套（event_id 去重 / Last-Event-ID 断点续发 / 缓冲过期历史兜底）
- **双层安全围栏**：关键词快路径毫秒级拦截 + LLM few-shot 判定，越界问题拒绝回答
- **多轮对话记忆**：滑动窗口摘要（最近 1 轮原文 + 更早轮次 LLM 要点摘要 + 增量缓存）
- **本地私有化**：数据索引与 LLM 推理全离线运行（Ollama + Qwen2.5:7B），医疗数据不出内网
- **工程化**：JWT + RBAC 鉴权、Redis 会话缓存与接口限流（fail-open 降级）、审计日志、Docker Compose 编排

## 架构

```
┌─────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│   Next.js 15 │────▶│  Spring Boot 3.3     │────▶│  FastAPI + LangGraph│
│  (前端 UI)   │ SSE │  (Java 后端/唯一入口) │ SSE │  (Python AI 服务)   │
│             │◀────│  JWT/审计/限流/转发   │◀────│  RAG + Agent + LLM  │
└─────────────┘     └──────────┬───────────┘     └─────────┬──────────┘
                               │                           │
                         PostgreSQL 16                FAISS / Chroma / Milvus
                            (业务/审计)                (向量库适配器三选一)
```

## 技术栈

| 层级 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **前端** | TypeScript, Next.js 15, react-pdf | 古籍阅读器、选词解释、SSE 打字机 |
| **后端** | Java 17, Spring Boot 3.3, Spring Security | JWT+RBAC、审计、限流、WebFlux 流式转发 |
| **AI 引擎** | Python, FastAPI, LangGraph, Ollama | Agent 状态机、Function Calling、本地推理 |
| **数据存储** | PostgreSQL 16, Redis, SQLite | 业务审计 / 会话缓存与限流 / 图状态检查点 |
| **向量检索** | FAISS / Chroma / Milvus（适配器可切换，当前 Chroma） | 协议适配器模式，切换零业务改动 |
| **嵌入模型** | BGE-large-zh-v1.5（1024 维） | 本地加载，全离线 |

## 快速开始

### 1. 环境准备

- **Docker & Docker Compose**：启动 PostgreSQL 等中间件
- **JDK 17+**：运行 Java 后端
- **Python 3.10+**：运行 AI 服务
- **Node.js 18+**：运行前端
- **Ollama**：本地运行 LLM（推荐 `qwen2.5:7b`）

### 2. 下载嵌入模型（约 1.3GB，不上传至本仓库）

```bash
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5 models/bge-large-zh-v1.5
# 国内镜像：git clone https://www.modelscope.cn/AI-ModelScope/bge-large-zh-v1.5.git models/bge-large-zh-v1.5
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 按需修改数据库密码、JWT 密钥等
```

### 4. 启动中间件

```bash
docker compose up -d postgres
```

### 5. 构建向量索引（仓库已含预构建索引，首次部署可跳过）

```bash
cd services/ai-service
pip install -r requirements.txt
python scripts/build_index.py
```

### 6. 启动三端服务（三个终端）

```bash
# A. Python AI 服务 (端口 8001)
cd services/ai-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# B. Java 后端 (端口 8080)
cd services/java-backend
mvn spring-boot:run

# C. 前端 (端口 3000)
cd services/frontend
npm install && npm run dev
```

访问 http://localhost:3000

## 项目结构

```text
guilinguben/
├── docs/                  # 需求文档、部署文档
├── data/                  # 方剂 JSON、FAISS/Chroma 索引、检查点
├── models/                # 嵌入模型（需自行下载，见快速开始）
├── scripts/               # 索引构建、E2E 测试脚本
├── services/
│   ├── ai-service/        # Python AI 服务 (FastAPI + LangGraph Agent)
│   ├── java-backend/      # Java 业务后端 (Spring Boot 3.3)
│   └── frontend/          # 前端 (Next.js 15)
├── src/                   # Python 核心（Agent 图 / RAG / UI）
├── tests/                 # Python 测试
├── docker-compose.yml     # 中间件编排
└── .env.example           # 环境变量模板
```

## 后续规划

- [ ] 病案录入与 RLHF 反馈闭环
- [ ] 会员分级体系
- [ ] RabbitMQ 长任务队列
- [ ] Milvus 集群化部署

## 许可证

本项目代码遵循 MIT 许可证。古籍原文版权归原作者及出版社所有，请勿用于商业用途。
