# 桂林古本智能辅助系统 (Guilinguben AI Assistant)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Java](https://img.shields.io/badge/Java-17-orange.svg)](https://openjdk.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)

## 📖 项目简介

本项目是一个基于 **RAG（检索增强生成）** 技术的中医古籍智能辅助系统。以《桂林古本伤寒杂病论》为核心知识库，结合本地部署的大语言模型（LLM），为中医学习者、研究者及临床医生提供精准的古籍问答、原文溯源及选词解释服务。

### ✨ 核心特性
*   **精准溯源**：回答均附带原文出处，支持点击跳转至 PDF 对应页码。
*   **选词解释**：鼠标选中任意古籍片段，即可获取 AI 生成的白话文翻译与辨证分析。
*   **本地私有化**：所有数据索引与 LLM 推理均在本地运行，确保数据安全与隐私。
*   **微服务架构**：采用 Java + Python + Next.js 的前后端分离架构，易于扩展与维护。

---

## 🛠️ 技术栈

| 层级 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **前端** | Next.js 16, React, Tailwind CSS | 现代化 UI，支持 PDF 交互渲染 |
| **后端** | Spring Boot 3.3, Java 17 | 统一 API 网关，业务逻辑处理 |
| **AI 引擎** | FastAPI, LangChain, Ollama | 向量检索与本地 LLM 推理 |
| **数据存储** | PostgreSQL 16, FAISS | 关系型数据与高性能向量搜索 |
| **嵌入模型** | BGE-M3 | 高质量中英双语文本嵌入 |

---

## 🚀 快速开始

### 1. 环境准备
*   **Docker & Docker Compose**: 用于启动 PostgreSQL 等中间件。
*   **JDK 17+**: 运行 Java 后端。
*   **Python 3.10+**: 运行 AI 服务。
*   **Node.js 18+**: 运行前端开发服务器。
*   **Ollama**: 需在本地安装并运行 LLM（如 `qwen2.5:7b`）。

### 2. 启动中间件
在项目根目录执行：
```bash
docker compose up -d postgres
```

### 3. 构建向量索引
首次运行需构建 FAISS 索引：
```bash
cd services/ai-service
pip install -r requirements.txt
python scripts/build_index.py
```

### 4. 启动服务
请分别在三个终端窗口中执行以下命令：

**A. 启动 Python AI 服务 (端口 8001)**
```bash
cd services/ai-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**B. 启动 Java 后端 (端口 8080)**
```bash
cd services/java-backend
mvn spring-boot:run
```

**C. 启动前端界面 (端口 3000)**
```bash
cd services/frontend
npm install
npm run dev
```

---

## 📂 项目结构

```text
guilinguben/
├── docs/                  # 项目文档
├── scripts/               # 全局脚本
├── services/
│   ├── ai-service/        # Python AI 微服务 (FastAPI + RAG)
│   ├── java-backend/      # Java 业务后端 (Spring Boot)
│   └── frontend/          # 前端应用 (Next.js)
├── docker-compose.yml     # 中间件编排文件
└── .env                   # 环境变量配置
```

---

## 📝 待办事项 (Roadmap)

- [ ] **多轮对话记忆**：实现基于 Session 的上下文连续问答。
- [ ] **用户认证系统**：集成 JWT 登录与权限管理。
- [ ] **性能优化**：优化大体积 PDF 的文本层渲染速度。
- [ ] **容器化部署**：完善 Dockerfile，实现全栈一键部署。

---

## 📄 许可证

本项目遵循 MIT 许可证。详见 [LICENSE](LICENSE) 文件。
