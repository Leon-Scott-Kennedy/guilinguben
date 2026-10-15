# 桂林古本智能辅助诊疗平台项目需求书

- 文档版本：0.4.10
- 更新时间：2026-09-18
- 项目状态：核心链路（Java -> Python -> RAG -> PostgreSQL）已打通；多轮对话记忆与上下文管理已实现并通过真实环境端到端验证；前端已升级为聊天式消息列表 UI；B 轮 Agent 化改造进行中（B1-B5 已完成，含 SSE 三端流式）；已完成岗位市场对照与路线纠偏（15.11）。
- 本文档用途：作为产品目标、技术架构、模块边界、迭代顺序、卡点记录和面试复述材料的长期依据

## 1. 项目概述

本项目面向中医经典文献知识检索和辅助分析场景，直接以《桂林古本伤寒杂病论.pdf》作为首个原始数据源，构建一个具备知识检索、对话分析、来源追溯、权限控制和审计能力的智能应用平台。

系统定位是“辅助研究与辅助决策工具”，不是自动诊断、处方或替代专业医师的系统。所有面向用户的结果必须保留知识来源、免责声明和人工复核边界。

核心链路：

```text
用户/Web客户端 -> Java 业务后端 (入口) -> Python AI 服务 (Agent) -> RAG/LLM/工具 -> PostgreSQL 持久化
```

## 2. 产品目标

### 2.1 MVP 目标

1. 用户可以登录并获得基础权限。
2. 用户可以提交症状或文献问题。
3. Java 后端可以调用 Python AI 服务。
4. Python 服务可以完成意图识别、知识检索、回答生成和安全围栏。
5. 返回结果包含回答、引用文档、置信提示、风险提示和请求追踪 ID。
6. Java 侧可以保存会话、病例元数据和审计记录。
7. 服务具备健康检查、错误响应和基本日志。

### 2.2 后续目标

1. 支持多用户、多租户和细粒度 RBAC。
2. 支持文献上传、解析、切分、审核和向量化流水线。
3. 支持异步任务、长流程 Agent 和人工复核。
4. 支持评测集、离线评测、回归测试和质量看板。
5. 支持 MCP 工具、外部知识源和可配置工作流。
6. 支持 Docker Compose 本地部署，后续再演进到 Kubernetes。

## 3. 用户与角色

### 3.1 普通用户/会员

- 注册登录系统
- 使用智能问答（严格模式/自由模式切换）
- 实时翻看内嵌文献并获取解释
- 录入个人病案
- 查看历史会话与分析结果

### 3.2 研究人员/专家

- 审核用户提交的疑难病案
- 标注 AI 回答质量（RLHF 反馈）
- 管理知识库版本和文献授权

### 3.3 管理员

- 管理用户、角色和会员权益
- 查看审计日志、调用日志和失败任务
- 配置模型参数、安全策略和 Tool 集合

## 4. 总体架构

### 4.1 Java 业务平台

Java 使用 Spring Boot 3.x、Java 17、Maven 构建，负责稳定的业务边界和数据一致性。**目前作为系统的唯一对外入口**。

职责：

- 用户、角色、权限和认证
- 会话、病例和业务元数据
- 文献资产、知识库版本和审核状态
- AI 服务调用编排、超时、重试和降级
- 审计日志、操作记录和请求追踪
- 对外 REST API
- 统一异常、参数校验和安全策略

### 4.2 Python AI 服务 (Agent Core)

Python 使用 FastAPI、LangChain、LangGraph，负责模型调用、知识检索和 Agent 工作流。

职责：

- **意图识别引擎**：判断用户问题是“症状查询”、“追问”还是“越界”。
- **RAG 检索与重排序**：基于 FAISS/Milvus 进行向量检索。
- **LangGraph Agent 状态流转**：实现 ReAct 工作流，支持 Tool Calling。
- **知识围栏与安全审查**：处理严格模式开关，执行越界降级。
- **结构化输出**：返回带引用、置信度和风险提示的回答。

## 5. 核心业务功能

### 5.1 智能问答与意图识别 (Agent Loop)

系统需根据用户输入动态调整处理逻辑：
1.  **意图识别**：
    *   **症状查询**：文本包含明确症状且与古文语境相近 -> 触发 RAG 检索。
    *   **追问**：基于上一轮对话上下文 -> 携带历史记录再次检索或直接生成。
    *   **越界处理**：非伤寒论范畴或要求确诊处方 -> 触发安全围栏，予以降级提示。
2.  **严格模式开关**：
    *   **开启**：强制基于检索证据回答，无证据则说明不确定性。
    *   **关闭**：进入通用 LLM 聊天环节，允许更自由的发散性讨论，但仍需附带免责声明。

### 5.2 内嵌文献交互式阅读

1.  **PDF 实时渲染**：Web 端内嵌 `guilinguben.pdf`，支持页码跳转和全文搜索。
2.  **选词解释**：用户光标选中古籍片段 -> 点击“解释” -> 后端调用 LLM 生成白话文解释或辨证分析。
3.  **双向联动**：点击 AI 回答中的引用链接，PDF 自动跳转至对应页码并高亮显示。

### 5.3 病案录入与 RLHF 闭环

1.  **病案录入**：支持用户录入主诉、现病史、舌脉等信息。
2.  **专家监督**：专家对 AI 生成的病案分析报告进行确认或修正。
3.  **语料进化**：经专家确认的病案自动向量化，存入向量库。
4.  **来源区分**：检索时明确标识内容是来自“原文案例”还是“客户病案”，提高可信度。

### 5.4 会员角色与权限管理

1.  **功能分级**：普通用户仅限基础问答，会员可使用深度病案分析、无限次文献解释等功能。
2.  **用量控制**：基于 Redis 实现会员每日调用次数限制。

### 5.5 工具调用 (Tool Calling) 与异常兜底

1.  **Tool 支持**：Agent 可根据需要调用外部工具（如：药材属性查询、方剂配伍禁忌检查）。
2.  **异常兜底**：
    *   **模型超时**：自动切换为精简版 Prompt 或返回预设的友好提示。
    *   **检索失败**：降级为纯 LLM 回答并显著标注“未检索到相关文献”。
    *   **服务不可用**：Java 侧返回统一的 503 错误码，前端展示维护页面。

### 5.6 会话与病例持久化

- 创建分析会话，保存用户问题、AI 回答、引用来源和反馈。
- 病例信息与分析会话分离，支持敏感字段最小化收集。
- 支持会话状态：ACTIVE、COMPLETED、ARCHIVED。

## 6. 中间件选型

| 组件 | 选型 | 主要用途 | 使用阶段 |
|---|---|---|---|
| 关系数据库 | PostgreSQL 16 | 用户、病例、会话、审计、元数据 | MVP 必选 |
| 缓存 | Redis 7 | 会话缓存、限流、短期状态 | MVP 必选 |
| 消息队列 | RabbitMQ 3.13 | 文献处理、异步 AI 任务、重试 | MVP 后半段 |
| 向量数据库 | Milvus 2.4 | Embedding 检索和知识库索引 | RAG 阶段 |
| 对象存储 | MinIO | PDF、原始文献和处理产物 | 文献上传阶段 |
| 协调组件 | etcd | Milvus 依赖和服务协调 | Milvus 阶段 |
| 本地模型 | Ollama + Qwen | 本地 LLM 推理 | 本地开发 |

MVP 使用 FAISS 作为本地向量库适配器，只用于快速验证核心 RAG 链路；业务代码必须依赖统一的向量库端口，不得直接依赖 FAISS API。后续切换 Milvus 时，只替换适配器和配置，不修改 Agent、API 和业务用例。

向量库抽象至少包含：`build_index`、`similarity_search`、`similarity_search_with_score`、`as_retriever` 和索引持久化能力。

所有中间件通过 `docker-compose.yml` 管理。开发环境优先保证可重复启动，生产环境再按资源和运维要求拆分部署。

## 7. 接口与服务边界

### 7.1 Java 对外接口

- `GET /api/health`
- `POST /api/auth/login`
- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/analysis`
- `POST /api/feedback`
- `GET /api/audit/logs`（管理员）

### 7.2 Python 内部接口

- `GET /health`
- `POST /api/agent/health-check`
- `POST /api/agent/analyze`
- `POST /api/retrieval/search`
- `POST /api/evaluation/run`（内部或管理员）

### 7.3 调用约束

- Java 是对外业务入口，Python 不直接承担用户认证
- Python 不直接修改 Java 业务数据库
- Java 调用 Python 必须设置连接超时和读取超时
- 可重试请求必须有幂等请求 ID
- Python 返回错误时，Java 转换为稳定的业务错误码
- 日志中不得记录密码、完整敏感病例或密钥

## 8. 非功能需求

### 8.1 可用性

- 服务启动失败必须有明确日志
- 每个服务提供健康检查
- 外部依赖不可用时返回可解释错误
- Java 和 Python 进程可以独立重启

### 8.2 性能

MVP 目标：

- Java 健康接口响应时间小于 200 ms
- 不含模型推理的业务接口响应时间小于 500 ms
- AI 请求设置最大超时，禁止无限等待
- 检索参数可配置，默认 `topK=5`

模型推理性能依赖本地硬件，不在 MVP 阶段承诺固定响应时间。

### 8.3 安全

- 密码不得明文存储
- 密钥只通过环境变量或密钥管理系统注入
- 生产环境关闭详细调试日志
- 所有管理接口必须鉴权
- 重要操作写入审计日志
- 文献授权状态必须可追踪

### 8.4 可观测性

- 统一 `requestId`
- 记录服务名、接口、耗时、状态和错误类型
- 通过 Actuator 暴露健康和基础信息
- 后续接入 Prometheus、Grafana 或集中日志系统

## 9. 开发与运行约定

### 9.1 Java

```text
Java: 17
Build: Maven 3.9.9
Framework: Spring Boot 3.3.x
Directory: services/java-backend
Build: mvn clean package
Run: java -jar target/java-backend-0.1.0.jar
```

### 9.2 Python

```text
Python: 3.13
Framework: FastAPI + LangGraph
Directory: services/ai-service
Run: python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 9.3 中间件

```text
docker compose up -d

docker compose ps

docker compose logs -f <service>
```

## 10. 迭代顺序

### 阶段一：基础骨架（已完成）
- Java 17 + Spring Boot 3.x 环境搭建
- Python FastAPI + LangGraph 环境搭建
- Docker Compose 中间件定义
- 核心健康检查接口验证

### 阶段二：最小联调闭环（已完成）
- Java-Python 分析接口契约定义
- 真实 HTTP 请求联调（Java -> Python -> Java）
- 结构化错误边界与 Request ID 实现

### 阶段三：业务数据与安全（已完成，2026-09-19）
- [x] PostgreSQL 用户、会话、审计表持久化（“病例表”未做——病案录入属远期功能未排期，见 5.3）
- [x] JWT 认证（D 轮 16.40）
- [x] RBAC 权限控制与全局异常处理（D 轮 16.40）
- [x] Redis 会话缓存与限流（⑤16.35）

### 阶段四：真实 RAG 与前端交互（已完成）
- PDF 解析、清洗、切分与 Embedding 生成
- FAISS/Milvus 向量库适配器实现
- Next.js 前端智能问答界面
- 内嵌 PDF 阅读器与选词解释功能（已实现鼠标选中调用 LLM）
- 前端多轮对话记忆与上下文管理（会话内固定 sessionId + 最近 5 条历史注入 Python Prompt）

### 阶段四·五：Agent 化改造与前端体验（B 轮，已完成）
- A 轮：前端聊天式消息列表 UI（已完成）
- B 轮 Agent 化五步：B1 接线 → B2 工具化 → B3 Agent 循环 → B4 检查点 → B5 流式输出（全部完成）
- 查缺补漏与后续项全部完成：①②③（方剂结构化引用、多轮记忆治理、Milvus 接线）+ A 轮搁置项 + ⑤Redis 接线 + C 轮数据治理 + 切换 Chroma + ④评测集指标化 + D 轮 JWT 鉴权 + ⑥审计日志与调用指标（详见 ##11 与各卡点）

### 阶段五：异步化与生产化（规划中）
- RabbitMQ 文献处理与长任务队列
- MinIO 文献资产管理
- 自动化评测、监控告警与 CI/CD
- 注（岗位纠偏 2026-09-17）：其中 Milvus 接线、Redis 会话缓存与限流、自动化评测三项市场高频，已提前至 B 轮查缺补漏阶段执行（15.11），阶段五保留 RabbitMQ 长任务、MinIO 资产管理、监控告警与 CI/CD

## 11. 当前待办清单

- [x] 定义 Java/Python 分析接口契约并实现联调
- [x] Java 增加分析接口、日志记录与 PostgreSQL 持久化逻辑
- [x] 搭建 Next.js 前端项目并实现基础问答界面
- [x] 解决前端 SSR 兼容性问题并集成 `react-pdf`
- [x] 实现点击引用卡片跳转至 PDF 对应页码的联动逻辑
- [x] 实现 PDF 选词解释功能（选中文字调用 LLM 生成释义）
- [x] 实现前端多轮对话记忆与上下文管理
- [x] 优化 Python 意图识别模型，支持动态 RAG 开关（B2 以 LLM 自主决策实现，替代预置关键词分类器）
- [x] 完善 Docker Compose 编排，实现全栈一键启动（E 轮 16.42 已实施 2026-09-20，待用户验收）：compose 加 healthcheck + profiles（rabbitmq/milvus 栈默认不拉起）+ scripts/start-all.sh / stop-all.sh 一键三端 + 三端 Dockerfile 可选资产（方案丙）+ docs/DEPLOY.md；静态验证全过
- [x] 前端“新建会话”按钮 + 侧栏会话列表（A 轮搁置，16.34 已实现）：DeepSeek 风格左侧会话列表（聚合 SQL 出首问标题/轮数/更新时间）+ 左上角新建会话按钮（localStorage 重新生成 sessionId）；历史加载静默降级策略确认：列表/历史加载失败均静默降级不阻塞提问
- [x] PDF 数据治理（C 轮已完成，16.36）：按“一个条文一条数据”重新切分 PDF、清洗后重建向量库（964 条）+ 方剂库 4 字段重构（446 条）
- [x] B 轮 Agent 化：B1 接线（ai-service 内实现 LangGraph 图，替换两步函数调用）
- [x] B 轮 Agent 化：B2 工具化（Tool Calling + 动态 RAG 开关，LLM 自主决策检索）
- [x] B 轮 Agent 化：B3 Agent 循环（围栏升级：关键词快路径 + LLM few-shot 越界判定双层围栏；截断收敛：final_answer 节点基于已有证据强制生成回答；工具异常不中断循环；验收 13 围栏用例 + 5 场景回归全过）
- [x] B 轮 Agent 化：B4 会话检查点（SqliteSaver 本地文件 data/checkpoints.sqlite，thread_id=session_id；存储介质三方案权衡见 16.24；方案甲：history_context 仍由 Java 注入，对外行为零变化；验收：同线程累加/多线程隔离/重启持久化 4 断言全过 + 7 场景回归全过）
- [x] B 轮 Agent 化：B5 流式输出（SSE 三端打通：Python /api/agent/analyze/stream（stream:true 逐 token，ContextVar 事件发射 + 有界队列）→ Java /api/analysis/stream（WebFlux WebClient + SseEmitter 转发 + 每会话缓冲）→ 前端 fetch 解析 SSE 打字机渲染；断连三件套落地：自增 event_id 去重、Java 缓冲 Last-Event-ID 续发短断连（TTL 5 分钟）、缓冲不可用引导历史恢复；验收：三端联调 12/12 全过 + 浏览器实测打字机正常；踩坑见 16.30）
- [x] 查缺补漏②：多轮记忆治理（16.32 已实现）：历史上下文摘要化（滑动窗口：最近 1 轮保留原文供指代解析，更早轮次 LLM 要点摘要 + 增量缓存，≤1 轮零 LLM 开销，失败 fail-open 降级截断）+ 自由模式弱兜底（无证据且回答含条文编号时追加警示）+ 历史接口分页（limit/offset + total/hasMore，前端“加载更早消息”）；验收：单元 7 组 + 端到端 4 轮（指代解析成功、摘要 49 字/增量 34 字）+ 弱兜底 3 断言 + 分页 5 断言全过
- [x] 查缺补漏③：Milvus 接线（16.33 已实现，用户 2026-09-18 确认验收）：MilvusVectorStore 适配器复用 ports.py 协议（schema：content/source/page/chunk + 1024 维向量，IVF_FLAT+COSINE，返回 1-cosine 伪距离与 FAISS 分数语义对齐，tools 层零改动）；vector_backend 开关（faiss/milvus，.env 配置）；灌数脚本复用 PDF 切块清洗；compose 修正（milvus run 需 standalone 位置参数、minio 镜像换 quay.io、mc 建 a-bucket、etcd advertise 改服务名）；验收：8 查询 top-5 与 FAISS 完全重合 + 三端回归全过；验收后因本机内存紧张切回 FAISS（milvus 容器栈停止，切换机制双向实测可用）
- [x] 查缺补漏（岗位纠偏·优先②）：工具调用评测集回归机制指标化（16.39 已实现，2026-09-19 验收）：自建 20 条评测集（症状/方剂/常识/越界/重复提问各 4 条）+ scripts/eval_rag.py（规则+本地 Ollama judge）；基线：工具调用精度 20/20、幻觉率 0/12、任务成功率 20/20；评测驱动修复 guardrail 两处误拦
- [x] 查缺补漏①（B4 实测发现）：方剂工具结构化引用（16.31 已实现）：lookup_formula 返回与检索证据同构的结构化证据（document_id 前缀 formula_db: + title/content/score），统一计入 citations；纯方剂证据 → intent=formula_query；验收：单元 8 断言 + 非流式/流式端到端全过（麻黄汤/桂枝汤 → formula_query + 5 citations）
- [x] 查缺补漏（岗位纠偏）：Redis 接线（16.35 已实现）：Java 端会话历史上下文缓存（写更新 append + 5 轮裁剪）+ 接口限流（固定窗口 INCR，30 次/分钟/IP，429）+ 四层 fail-open 降级；验收：缓存命中 3 连问 + 限流 31 请求第 31 个 429 + 三端回归全过
- [x] 查缺补漏（岗位纠偏）：审计日志与调用指标（16.41 已实现，2026-09-19）：audit_logs 表 + 5 类动作埋点（登录/问答/流式/解释）+ GET /api/audit（@PreAuthorize ADMIN）+ Python 进程内双层指标（/metrics，重启清零）；验收：6 条审计记录字段完整 + metrics 计数/明细正确
- [x] D 轮 JWT 鉴权 + RBAC + 登录功能（16.40 已实现，2026-09-19）：users/roles/user_roles 三表 + BCrypt + jjwt HS256 + JwtAuthenticationFilter + SecurityConfig 收口 authenticated（OPTIONS 精确放行、401/403 JSON）+ 前端登录页/登出/401 全局处理；三处取舍（RBAC 数据模型/数据隔离 owner 写路径/refresh token 预留）已搭架子并记录边界

### 下阶段开发顺序（用户 2026-09-19 调整；前 7 项已全部完成，E 轮收尾已实施待验收）
1. ~~A 轮待决策搁置项~~（已完成 16.34）：前端“新建会话”按钮 + DeepSeek 风格侧栏会话列表 + 历史加载静默降级策略确认
2. ~~⑤Redis 接线~~（已完成 16.35）：Java 端会话缓存 + 接口限流（spring-data-redis；写更新缓存一致性 + 固定窗口限流 + fail-open 降级）
3. ~~C 轮先行：数据治理~~（已完成 16.36）：retrieve_guilinguben 按条文编号切分（964 条，一个编号一条数据）+ lookup_formula 4 字段重构（446 条：页码/方剂名/药物组成/注意事项）+ 页码双轨四端贯通 + 前端跨页 PDF 渲染
4. ~~切换 Chroma 向量库~~（已完成 16.37）：ChromaVectorStore 协议适配器（chromadb 1.5.9 嵌入式持久化，cosine space，tools/Agent/API/Java/前端零改动）+ 灌数 964 条 + 8 查询 top-5 与 FAISS 40/40 重合 + 三端回归；当前 vector_backend=chroma，FAISS 保留可切回
5. ~~④评测集指标化~~（已完成 16.39，2026-09-19 验收）：自建 20 条评测集 + 三指标基线 100%/0%/100%
6. ~~D 轮 JWT 鉴权 + RBAC + 登录功能~~（已完成 16.40，2026-09-19，待用户验收）：登录/鉴权/前端登录页三端落地，三取舍已搭架子
7. ~~⑥审计日志与调用指标~~（已完成 16.41，2026-09-19，待用户验收）：audit_logs 落库 + 5 类动作埋点 + @PreAuthorize 审计查询 + Python /metrics 双层指标
8. E 轮 Docker Compose 全栈一键启动（16.42 已实施 2026-09-20，待用户验收）：编排方案丙（compose 管中间件 + 脚本管三端 + Dockerfile 可选资产）；postgres compose 管理化迁移待用户执行；验收 5 条见 16.42
调整理由（用户 2026-09-19）：D 轮生产化必经（16.3 预研：/api/analysis/** 全放行）；⑥审计依赖 D 轮的用户体系，故 D 轮优先。

## 15. 项目执行总览：按顺序记录的已做工作

### 15.1 阶段一：项目立项与技术选型

- [x] 确认项目定位：中医经典文献检索 + 智能辅助分析平台。
- [x] 确认技术分工：Java 业务层 + Python AI 层。
- [x] 确认基本技术栈：Java 17 + Spring Boot 3.3.x + Python 3.13 + FastAPI + LangGraph + FAISS + pypdf + Ollama。
- [x] 确认最核心原则：先跑通核心链路，再做中间件扩展，不允许过早微服务化和功能堆叠。
- [x] 选择 PDF 作为原始知识源，不再依赖手工整理 JSON 作为生产事实库。

### 15.2 阶段二：Java 与 Python 的最小联调

- [x] 构建 Java Spring Boot 应用骨架。
- [x] 验证 Java 17 + Maven 成功运行。
- [x] 验证 Java JAR 可启动并返回 `/api/health`。
- [x] 构建 FastAPI AI 服务骨架。
- [x] 验证 Python `/health` 与 `/api/agent/health-check` 正常返回。
- [x] 定义 Java/Python 协议：请求与响应字段、状态字段、引用字段与警告字段。
- [x] 实现 Java AI 客户端，调用 Python AI 服务。
- [x] 实现 Java 分析接口，并通过真实 HTTP 完成联调。
- [x] 修复 Java/Python 字段命名不一致问题（snake_case/camelCase 的兼容问题）。
- [x] 修复 Python 依赖与版本不兼容问题（LangChain、NumPy、Python 3.13 环境问题）。

### 15.3 阶段三：真实 PDF 数据链路

- [x] 使用真实的《桂林古本伤寒杂病论.pdf》（现重命名为 `guilinguben.pdf`）作为生产数据源。
- [x] 解析 PDF 内容并保留页码和来源信息。
- [x] 实现 `PdfDocumentLoader`。
- [x] 完成文本清洗：空白规范化、换行修正、页眉页脚过滤等。
- [x] 按段落切分，产出 `SourceDocument` 结构。
- [x] 验证真实 PDF 解析结果：已生成 174 个带 `source/page/chunk` 元数据的文本片段。
- [x] 确认解析后的数据是可追溯的，不再是纯文本堆放。

### 15.4 阶段四：向量存储与抽象设计

- [x] 定义 `DocumentLoader`、`SourceDocument`、`SearchResult` 和 `VectorStore` 抽象协议。
- [x] 创建 `FaissVectorStore` 适配器，确保上层调用不直接绑定 FAISS 实现细节。
- [x] 保证今后切换 Milvus 时只更换适配器，不改动 Agent 或 API 逻辑。
- [x] 固定 `build_index`、`similarity_search`、`similarity_search_with_score`、`as_retriever` 等接口契约。
- [x] 在真实环境下完成 Embedding 模型加载与生成向量验证。
- [x] 完成 FAISS 建索引与检索的真实端到端验证。

### 15.5 阶段五：AI 生成与安全围栏

- [x] 先实现结构化返回契约：answer / intent / citations / warnings / status / requestId。
- [x] 将占位答案替换为真实检索增强的回答生成逻辑。
- [x] 接入本地 Ollama + Qwen（`_local_llm_response` 函数已实现并验证）。
- [x] 接入知识来源引用和置信度字段。
- [x] 增加不确定性与越界提示。
- [x] 强制要求"基于文献证据回答，避免伪造来源"。

### 15.6 阶段六：性能优化与服务化（新增）

- [x] **FAISS 索引持久化** - 添加 `save_index()` 和 `load_index()` 方法，支持索引保存到磁盘。
- [x] **独立索引构建脚本** - 创建 `scripts/build_index.py`，可独立运行构建索引。
- [x] **单例检索服务** - 实现 `RetrievalService` 单例类，Embedding 模型只加载一次。
- [x] **服务启动预加载** - 使用 `@app.on_event("startup")` 在服务启动时预加载索引。
- [x] **端到端测试脚本** - 创建 `scripts/test_e2e.py` 验证完整链路。
- [x] **预索引构建完成** - 已成功执行 `python scripts/build_index.py`，索引保存至 `data/faiss_index`。
- [x] **性能验证** - 索引构建耗时大幅缩短，后续加载可实现秒级启动。

### 15.7 阶段七：前端交互增强与架构统一（新增）

- [x] **前端 API 模块化** - 将 `fetch` 请求和接口定义迁移至 `services/frontend/src/lib/api.ts`。
- [x] **统一网关转发** - 确立以 Java 后端为统一入口，解决前端跨域问题。
- [x] **Java 安全配置优化** - 在 `SecurityConfig` 中放行 `/api/analysis/**` 路径，允许预检请求通过。
- [x] **字段对齐修复** - 修正前后端 `ExplainTextRequest` 字段名不一致导致的 `null` 传递问题。
- [x] **PDF 文本层渲染** - 开启 `renderTextLayer` 并引入样式，支持用户选中古籍原文。
- [x] **文档同步更新** - 完成 `README.md` 编写及 `PROJECT_REQUIREMENTS.md` 进度同步。

### 15.8 阶段八：生产化准备

- [x] 增加 PostgreSQL 基础实体。
- [x] 增加鉴权与 RBAC（D 轮 16.40 已完成）。
- [x] 增加 Redis 会话、限流与缓存。
- [ ] 增加 RabbitMQ 异步任务（阶段五规划中，未排期）。
- [x] 增加 Milvus 适配器和配置切换。
- [x] 增加自动化评测与回归测试（④16.39 已完成：自建 20 条评测集 + 三指标基线）。
- [ ] 完成 Docker Compose 本地部署文档（E 轮收尾项）。

### 15.9 阶段九：多轮对话记忆与上下文管理（新增）

- [x] 修复前端 sessionId 每次请求用 `Date.now()` 重新生成的问题，改用 `useRef` 在浏览器会话内固定，保证同一标签页多轮对话共享同一会话。
- [x] 修复 Java 会话查询语义错误：`sessionRepository.findById`（按主键）改为 `findBySessionId`（按业务字段），避免每次请求重复创建会话行。
- [x] 历史上下文限定最近 5 条：`AnalysisRecordRepository` 改用显式 `@Query("SELECT r FROM AnalysisRecord r WHERE r.sessionId = :sessionId ORDER BY r.createdAt DESC LIMIT 5")`，不再依赖方法名解析，实际 SQL 为 `fetch first 5 rows only`。
- [x] AI 调用失败时在 catch 分支保存失败记录（question + 错误信息），避免多轮对话历史中断。
- [x] 真实环境端到端验证：向同一会话插入 7 条记录，实测接口日志"已加载 5 条历史记录"，滚动窗口正确前移，Python 端正常收到 `history_context`。
- [x] 修复数据库时区：PostgreSQL 默认时区设置为 Asia/Shanghai（`ALTER DATABASE` 立即生效 + docker-compose `TZ`/`-c timezone` 保证重建生效），入库时间按北京时间显示。

### 15.10 阶段十：聊天式消息列表 UI 与 Agent 化起步

- [x] Java 新增 `GET /api/analysis/history` 会话历史查询接口：全量升序返回（与 Top5 上下文注入的降序查询语义分离），citations 从 jsonb 字符串反序列化为结构化列表并做解析失败兜底。
- [x] 前端聊天式界面重构：用户/AI 消息气泡、引用证据卡内嵌 AI 消息、自动滚动与加载中气泡；sessionId 改用 localStorage 持久化（跨刷新保留会话）。
- [x] B1 接线（已完成）：在 ai-service 内新建 `app/agent/` 包实现 LangGraph 图（不 import 根目录 src），替换 main.py 的两步函数调用，对外契约不变（B 轮规划详见 16.17）。
- [x] B2 工具化：新建 `agent/tools.py`（retrieve_guilinguben 向量检索 + lookup_formula 方剂库查询，数据源 data/桂林古本方剂提取结果.json）；图升级为 guardrail → agent ⇄ tools 循环（MAX_ITERATIONS=3 防死循环），LLM 自主决策调用工具（动态 RAG 开关）；实测三场景：症状问题自动双工具调用并基于证据回答、常识问题零工具直接回答、越界问题硬边界拦截。
- [x] B2 验收修复（16.19）：历史上下文旧答案导致模型跳过工具调用并复述幻觉条文 → system prompt 双重强化 + 严格模式 user 消息级强制指令，复现场景验证修复且无回归。
- [x] B2 验收修复（16.20）：冷启动场景模型仍可不调工具直接回答并编造条文（“发热、恶寒、身疼痛”经典问题）→ 严格模式首轮代码层确定性兜底：未调工具则丢弃直接回答并强制注入检索，实测三层防线生效。
- [x] B3 Agent 循环（16.22）：围栏升级为双层（关键词快路径 + LLM few-shot 越界判定，fail-open）；新增 final_answer 节点实现循环截断收敛（不再返回空回答）；工具异常处理不中断循环；验收围栏 13 用例 + 截断收敛 + 5 场景端到端回归全过。
- [x] B3 全链路实测（三端联调 + 三端日志埋点）：真实向量库/方剂库/数据库三端联调 6 场景全过；发现并修复方剂名繁简不匹配（16.23）；多轮指代追问（“它的药物组成是什么？”）验证通过。
- [x] B4 会话检查点（16.24）：graph.py 挂 SqliteSaver（data/checkpoints.sqlite，check_same_thread=False 内部有锁），main.py invoke 带 thread_id=session_id；requirements.txt 按 torch_env 实装版本全量同步（新增 langgraph-checkpoint-sqlite==3.1.1/sentence-transformers/langchain-core，移除未使用的 langchain，fastapi/uvicorn/pydantic/requests 等 8 项版本对齐）；验收：检查点机制 4 断言全过（同线程累加/多线程隔离/模拟重启持久化/重启后延续）+ 真实服务 7 场景回归全过；实测发现 lookup_formula 不产出结构化 citations（已列查缺补漏）。
- [x] B5 流式输出（16.30 已实现）：Python 新增流式端点（Ollama stream:true 逐 token + ContextVar 事件发射不入图状态 + 有界队列丢弃防内存膨胀）；Java 新增流式端点（WebFlux WebClient 消费上游、SseEmitter 转发、AnalysisStreamService 每会话事件缓冲 + 断连不取消订阅照常落库）；前端 fetch 手动解析 SSE 打字机渲染（去重/断点重连/历史恢复兜底）；SecurityConfig 放行 /api/analysis/stream。验收：三端联调 12/12 断言全过（事件序列与 id 自增、done 落库、断连后 Last-Event-ID 重放 id 连续、旧接口回归）+ 浏览器实测（打字机/状态文本/引用证据卡/越界快路径）；实测踩坑：SSE 响应未声明 charset=UTF-8 中文被误读、SseEmitter.send 带 MediaType 参数绕过 SseEventBuilder 拆包事件静默丢失（详见 16.30）。
- [x] 查缺补漏①方剂工具结构化引用（16.31 已实现）：lookup_formula 返回 (文本, 证据列表) 与检索证据同构计入 citations（document_id 前缀 formula_db: 标识来源，score=1.0 精确匹配）；纯方剂证据 intent=formula_query（新增契约值）；字段命名兼容 C 轮 4 字段重构（页码/方剂名/药物组成/注意事项）。验收：单元 8 断言全过 + 非流式端到端 4 用例（麻黄汤/桂枝汤 → formula_query+5 citations、症状回归 symptom_query、越界快路径 43ms）+ 流式 done 事件 formula_query+5 citations。
- [x] 查缺补漏②多轮记忆治理（16.32 已实现）：Python 摘要模块（滑动窗口：最近 1 轮原文 + 更早轮次 LLM 要点摘要；增量缓存同会话每请求至多 1 次摘要调用、命中零开销；失败 fail-open 降级截断）；自由模式弱兜底（无证据 + 条文编号 → 追加警示）；Java 历史接口分页（limit/offset + total/hasMore，limit clamp 1~200，倒序取页反转升序）；前端分页加载 + “加载更早消息”按钮。验收：单元 7 组 + 端到端 4 轮（指代解析成功、摘要 49 字/增量 34 字）+ 弱兜底 3 断言 + 分页 5 断言全过；踩坑：测试脚本 snake_case 字段与 camelCase record 不匹配致 session_id 非空约束 500（详见 16.32）。

### 15.11 阶段十一：岗位市场对照与路线纠偏（2026-09-17）

- [x] 归纳 14 份深圳大模型应用/Agent 方向招聘信息（2026-09-12 发布）技能频次（14 帖中提及帖数）：Python 13、Agent 应用开发 13、RAG 12、大模型 API 集成 12、LangChain 系框架 10、Tool Calling/MCP 7、Prompt Engineering 7、Redis 7、Java 7、FastAPI/Flask 7、MySQL/PostgreSQL 6、向量数据库 6、Docker/Linux/CI-CD 5、Embedding 5、Dify 平台 5、微调 4、多轮会话管理 4、安全（权限/审计）4、评测体系 3 等。
- [x] 纠偏结论：项目大方向与市场主需求一致（Python FastAPI + LangGraph Agent + Java 三端；B 轮 Agent 化路线正踩 Agent 架构/Tool Calling/RAG 高频考区），无需改向；按市场性价比调整后续优先级 5 项——Milvus 接线提前、评测集指标化、Redis 接线、审计日志与监控、B5 增加流式工程细节；新增卡点 16.26-16.29，##10/##11 已同步。
- [x] 明确最匹配目标岗位：能信安“Agent开发工程师”（18-25K，5-10 年，纯 Java 岗：要求 SSE 流式断连/去重/恢复、第三方接口重试幂等、JUnit5/Mockito、Agent 框架）。

## 16. 当前卡点记录（面试中最容易被问到的关键点）

### 16.1 多轮对话记忆的上下文管理（已解决）
- **问题**：Python 端日志始终未输出历史上下文对话，跨层排查发现多轮对话记忆链路存在三处断点：
  1. 前端每次提问用 `Date.now()` 生成新 sessionId，Java 按新会话查历史永远为空；
  2. Java 端 `findById` 误按主键查询，业务字段 sessionId 永远匹配不到已有会话；
  3. 历史查询与"最近 5 条"注释不一致，且 AI 调用失败时不落库，导致历史中断。
- **处理方式**：
  - 前端改用 `useRef` 固定浏览器会话内 sessionId；
  - Java 改用 `findBySessionId` 按业务字段查询，并加显式 `@Query` 的 `LIMIT 5` 保证只取最近 5 条；
  - AI 调用失败时在 catch 分支保存失败记录，维持上下文连续性；
  - 真实环境实测：7 条记录仅加载 5 条（SQL 为 `fetch first 5 rows only`），滚动窗口与 Python 端 `history_context` 接收均正常。
- **结果**：连续追问时 AI 可携带最近 5 轮对话上下文生成回答，上下文窗口上限 5 条避免 Token 膨胀。
- **面试回答关键词**：多轮对话上下文窗口、跨层根因定位、显式 SQL 限制、真实环境端到端验证。

### 16.2 PDF 文本层渲染的性能瓶颈
- **现状**：在开启 `renderTextLayer={true}` 后，大页码（如超过 50 页的古籍）在首次加载时会出现明显的 UI 阻塞。
- **难点**：`react-pdf` 的文本层计算量较大，且 Next.js 的客户端渲染机制在处理大量 DOM 节点时存在性能开销。
- **解决方案预研**：考虑实现虚拟滚动或懒加载策略，仅渲染可视区域内的文本层；或者将文本层提取为独立的 JSON 数据按需加载。

### 16.3 跨域与安全认证的平衡
- **现状**：为了开发便利，目前在 `SecurityConfig` 中对 `/api/analysis/**` 进行了放行。
- **难点**：生产环境下需要严格的 JWT 鉴权，但这会增加前端请求的复杂度，并可能再次触发 CORS 预检失败。
- **解决方案预研**：设计统一的 `JwtAuthenticationFilter`，并在 Spring Security 配置中精确匹配 OPTIONS 请求的处理逻辑。

### 16.12 新解决卡点：Java 后端日志缺失与持久化字段映射

- **问题**：Java 后端在处理请求时缺乏直观的流程日志，且在持久化 `citations` 字段时遇到类型映射错误。
- **处理方式**：
  - **引入 SLF4J**：在 `AnalysisController` 中添加详细的 INFO/DEBUG 级别日志，覆盖请求接收、会话管理、AI 调用和持久化全过程。
  - **JSON 映射修复**：使用 Hibernate 的 `SqlTypes.JSON` 注解处理 `List<Citation>` 到 PostgreSQL `jsonb` 类型的转换。
- **结果**：开发者可以通过控制台实时追踪请求生命周期，且分析记录能完整存入数据库。
- **面试回答关键词**：可观测性增强、ORM 高级特性、故障排查。

### 16.1 卡点一：Java 与 Python 的协议不一致，最开始联调失败

- 问题：Java 侧发送的是 camelCase，Python 侧最初使用 snake_case，导致请求解析失败，接口联调被卡住。
- 处理方式：
  - 统一使用结构化 DTO 和 Pydantic 模型；
  - 通过字段映射和 `AliasChoices` 兼容输入；
  - 同步修正 Java 侧的 `@JsonProperty` 等字段映射；
  - 重新启动 Python 服务，避免 stale process 继续使用旧配置。
- 结果：Java -> Python 的真实 HTTP 联调最终正常工作。
- 面试回答关键词：协议统一、字段兼容、接口联调稳定性。

### 16.2 卡点二：依赖版本与 Python 3.13 环境不兼容

- 问题：项目最初的 LangChain 版本过旧，放在 Python 3.13 上会触发 NumPy 依赖编译和安装问题，导致环境不稳定。
- 处理方式：
  - 强制升级到兼容版本：LangChain 1.4.0、LangGraph 1.2.11、FastAPI 0.115.0、pypdf 6.18.1；
  - 保留 FAISS CPU 1.15.0；
  - 以真实项目环境为准，不继续在"完全依赖旧版本"的状态上硬凑兼容。
- 结果：基础 Python 环境稳定，核心框架能够正常工作。
- 面试回答关键词：环境兼容性、版本收敛、减少不必要技术债。

### 16.3 卡点三：真实 PDF 原始数据源和"手工 JSON"思路的冲突

- 问题：项目早期容易把手工整理 JSON 当作核心输入，导致数据链路不真实，后续无法体现真实知识库价值。
- 处理方式：
  - 明确规定：原始数据必须直接使用《桂林古本伤寒杂病论.pdf》；
  - 不再把手工 JSON 当作生产知识源；
  - 将 PDF 解析、清洗、切分与向量化视为真正的工作路径。
- 结果：数据 source 是真实文献，而不是人工归纳的静态副本。
- 面试回答关键词：真实数据优先、可追溯来源、产品可信度。

### 16.4 卡点四：架构设计中"快跑通"和"过早扩展"的平衡

- 问题：很容易在还没跑通 RAG 核心链路时，就开始扩展多 Agent、RabbitMQ、Milvus 等复杂流程，导致工程混乱。
- 处理方式：
  - 固定顺序：Java/Python 联调 -> PDF 解析 -> Embedding -> FAISS -> RAG -> Ollama -> 扩展中间件；
  - 统一向量库抽象层，保证未来切换 Milvus 时不影响 Agent 上层逻辑；
  - 先保证最核心链路稳定，后续中间件才接入。
- 结果：工程边界清晰，后续扩展成本低。
- 面试回答关键词：分阶段实施、最低可验证闭环、架构守门策略。

### 16.5 当前已解决的卡点：本地 BGE Embedding 环境问题

- 问题：当前 Python 3.13 + Windows 环境中，`sentence-transformers` + `torch` 导入阶段出现 DLL 载入失败，表现为 `WinError 193` 和 `c10.dll` 加载错误。
- 进一步判断：这不是业务代码问题，而是运行环境与 PyTorch 二进制包不匹配，属于底层依赖层面问题。
- 处理思路：
  - 先确认当前 venv 的 Python 位数、PyTorch 安装状态；
  - 直接切到已确认可用的 Anaconda `torch_env`；
  - 重新验证 embedding 生成能力；
  - 成功后继续接入 FAISS 和真实检索。
- 结果：在 Anaconda `torch_env` 中，`torch` 导入成功，BGE 模型加载成功，`embed_query`/`embed_documents` 可以执行。
- 面试回答关键词：定位问题、分层排查、解决根因而不是表面修补。

### 16.6 当前仍在解决的卡点：PDF 文本清洗与中文编码质量

- 问题：真实 PDF 解析后，返回的检索片段存在明显乱码和断句现象，虽然已经能检索出来源，但回答质量会被直接拉低。
- 判断：这不是索引错误，而是 PDF 文本抽取后的清洗和编码规范化还不够完整，特别是古籍扫描文本中的特殊符号、页眉页脚和混合编码问题。
- 处理思路：
  - 先做页面级和段落级清洗；
  - 规范化特殊空白与异常换行；
  - 识别并剔除非正文噪声；
  - 视情况增加 OCR 或回退策略，确保真实文本质量。 
- 目前状态：RAG 检索链路已跑通，但最终回答质量仍取决于文本清洗质量。
- 面试回答关键词：真实数据清洗、质量优先、可追溯证据链。

### 16.7 新解决卡点：测试性能瓶颈 - Embedding 模型和向量库重复加载

- **问题**：每次运行测试都要重新加载 BGE Embedding 模型（约 1-2 GB）和重建 FAISS 索引（404 个片段），导致单次测试耗时 5+ 分钟，严重影响开发效率。
- **根因分析**：
  1. Embedding 模型没有单例化管理，每次测试都从磁盘重新加载到内存
  2. FAISS 索引没有持久化，每次都要从 PDF 重新解析、清洗、向量化
  3. 测试使用 `TestClient` 运行在内存中，无法复用已加载的模型和索引
- **解决方案**：
  1. **单例检索服务** - 创建 `RetrievalService` 单例类，管理 Embedding 模型和向量库的生命周期
  2. **FAISS 索引持久化** - 添加 `save_index()` 和 `load_index()` 方法，支持索引保存到磁盘
  3. **独立构建脚本** - 创建 `scripts/build_index.py`，可预先构建索引，后续直接加载
  4. **服务启动预加载** - 使用 FastAPI 的 `@app.on_event("startup")` 在服务启动时一次性加载
- **技术实现**：
  ```python
  # faiss_store.py - 添加持久化方法
  def save_index(self, path: str | Path | None = None) -> None
  def load_index(self, path: str | Path | None = None) -> None
  def index_exists(self, path: str | Path | None = None) -> bool
  
  # main.py - 单例服务
  class RetrievalService:
      _instance = None
      def initialize(self):  # 只执行一次
          self._provider = LocalEmbeddingProvider(...)  # 加载 Embedding
          if self._store.index_exists():
              self._store.load_index()  # 秒级加载
          else:
              self._store.build_index(documents)  # 首次构建
              self._store.save_index()  # 保存到磁盘
  ```
- **效果预期**：
  - 首次构建：约 2-3 分钟（加载模型 + 解析 PDF + 构建索引）
  - 后续测试：秒级启动（直接加载预构建索引）
  - 测试时间从 5+ 分钟降到 10 秒内
- **关于 Milvus 的决策**：
  - **当前保持 FAISS**：404 个片段完全够用，无需引入复杂中间件
  - **未来迁移时机**：数据量 > 10 万条、需要高并发、需要分布式部署时再考虑
  - **迁移成本极低**：已有 `VectorStore` 抽象层，只需实现 `MilvusVectorStore` 适配器
- **面试回答关键词**：性能优化、单例模式、索引持久化、架构演进策略、技术选型权衡。

### 16.8 新解决卡点：脚本执行环境与相对路径解析冲突

- **问题**：在执行 `scripts/build_index.py` 时，由于 `config.py` 中的 `BASE_DIR` 计算依赖于 `__file__`，而脚本执行时的 CWD（当前工作目录）变化导致相对路径解析错误，无法找到 `models` 文件夹或 PDF 文件。
- **处理方式**：
  - 在 `scripts/build_index.py` 中显式增加路径解析逻辑，将配置中的相对路径转换为基于项目根目录的绝对路径。
  - 统一数据源文件名为 `guilinguben.pdf`，并在 `.env` 和 `config.py` 中同步更新。
- **结果**：索引构建脚本在不同目录下均可稳定执行，FAISS 索引成功持久化至 `data/faiss_index`。
- **面试回答关键词**：路径鲁棒性、环境隔离、脚本工程化。

### 16.9 新解决卡点：Ollama 服务调用降级与意图识别逻辑

- **问题**：在测试“伤寒论的主要症状是什么？”这类宏观问题时，系统依然尝试检索原文并交给 LLM 总结，且初期出现了“本地模型服务不可用”的降级提示。
- **处理方式**：
  - **调试 Ollama**：确认 Ollama 进程已启动且端口通畅，通过直接调用 `curl` 排除网络问题。
  - **优化 Prompt 逻辑**：在 `generate_answer` 中增加分支，当无检索证据时，自动切换为通用知识问答模式并附带免责声明。
  - **意图识别预留**：虽然现阶段为了跑通链路保留了“先检索后回答”的逻辑，但已明确未来需根据关键词（如恶风、汗出等）动态决定是否启用 RAG。
- **结果**：LLM 能够结合检索到的古文片段生成结构化的辅助分析回答，且在模型异常时能给出友好的降级反馈。
- **面试回答关键词**：服务容错、Prompt 工程、意图识别演进、链路完整性。

### 16.10 新解决卡点：Java 与 Python 端到端链路联调

- **问题**：Java 后端调用 Python 服务时，需要确保 DTO 字段对齐、超时设置合理以及错误码转换。
- **处理方式**：
  - 利用 Spring Boot 3 的 `RestClient` 简化 HTTP 调用。
  - 在 Java DTO 中使用 `@JsonProperty` 精确映射 Python 的 snake_case 字段。
  - 验证了从 Java 提交请求到最终拿到包含文献引用的 AI 回答的全过程。
- **结果**：成功通过 Java 接口 `/api/analysis` 获取到了由 Python 侧 FAISS 检索并由 Ollama 生成的综合回答。
- **面试回答关键词**：跨语言协作、DTO 映射、微服务联调、全链路验证。

### 16.11 新解决卡点：LLM 调用超时与 Prompt 调试可见性

- **问题**：在处理长上下文（多个古籍条文）时，Ollama 生成回答的时间偶尔超过 60 秒，导致 Python 侧抛出 `Read timed out` 异常并进入降级逻辑；同时，开发人员无法在控制台看到实际发送给 LLM 的 Prompt，难以调试回答质量。
- **处理方式**：
  - **增加超时阈值**：将 `_local_llm_response` 中的 `timeout` 参数从 60s 增加到 120s，适应本地模型在复杂推理下的响应速度。
  - **增加日志输出**：在调用 LLM 前通过 `print` 将完整的 Prompt（包含问题和检索到的证据）输出到控制台。
- **结果**：降级提示消失，LLM 能够稳定生成包含辨证思路和治法要点的详细回答；控制台现在可以实时查看 Prompt 构造情况。
- **面试回答关键词**：超时控制、日志调试、稳定性优化、可观测性。

### 16.13 新解决卡点：前端 SSR 兼容性与内嵌 PDF 阅读器实现

- **问题**：在 Next.js 中集成 `react-pdf` 时，由于该库依赖浏览器端的 `document` 对象，导致在服务端渲染（SSR）阶段抛出 `document is not defined` 运行时错误。此外，需要实现点击引用卡片自动跳转至 PDF 对应页码的联动逻辑。
- **处理方式**：
  - **动态导入禁用 SSR**：使用 Next.js 的 `next/dynamic` 组件加载 `PdfViewer`，并设置 `{ ssr: false }`，确保 PDF 渲染逻辑仅在客户端执行。
  - **PDF 资源部署**：将 `guilinguben.pdf` 放置于 Next.js 的 `public` 目录下，通过静态资源路径访问。
  - **元数据解析与联动**：从 AI 返回的 `citations` 中提取 `document_id`（如 `p73`），解析出页码并传递给 `PdfViewer` 组件。
  - **LLM 响应截断修复**：调整 Ollama 调用的 `num_predict` 参数至 1024，并通过 Prompt 指令控制回答长度，解决了之前因硬限制导致的回答不完整问题。
- **结果**：成功实现了“问答-引用-原文预览”的 Agent Loop 闭环，用户可以在 Web 界面完成从提问到查阅古籍原文的全流程。
- **面试回答关键词**：Next.js SSR 优化、客户端组件隔离、文图联动交互、Prompt 工程化控制。

### 16.14 新解决卡点：数据库时间与北京时间相差 8 小时

- **问题**：`created_at` 字段（Java `Instant` -> PostgreSQL `timestamptz`）存储的绝对时刻本身正确，但容器默认时区为 UTC，psql 查询显示的时间比北京时间晚 8 小时。
- **处理方式**：`ALTER DATABASE guilinguben SET timezone TO 'Asia/Shanghai'` 立即生效；同时在 docker-compose 中为 postgres 容器补充 `TZ: Asia/Shanghai` 与启动参数 `-c timezone=Asia/Shanghai`，保证重建容器后同样生效。Java 侧 `Instant` 语义不变（绝对时刻存储，与 JVM 时区无关）。
- **结果**：数据库查询显示时间与北京时间一致，已有数据的绝对时刻不受影响。
- **面试回答关键词**：时区标准化、timestamptz 绝对时间语义、容器时区配置。

### 16.15 会话历史接口的查询语义分离与兼容性设计（A 轮）

- **问题**：同一张 `analysis_records` 表存在两个查询用途：多轮对话上下文注入只需最近 5 条（降序）；前端聊天界面需要完整历史（升序）。若共用一个查询方法，要么上下文 token 膨胀，要么界面历史缺失。此外 citations 以 jsonb 字符串存储，读接口需反序列化且不能因单条脏数据导致整个历史接口失败。
- **处理方式**：
  - 保留 `findTop5BySessionIdOrderByCreatedAtDesc`（显式 `@Query` LIMIT 5，注入用）与新增 `findAllBySessionIdOrderByCreatedAtAsc`（展示用）两个独立方法，用途在注释中明确；
  - 新增 GET 接口不动既有 POST 契约（向后兼容），SecurityConfig 精确放行新路径 `/api/analysis/history` 而非整体开放 `/api/analysis/**`；
  - citations 用 Jackson `TypeReference<List<Citation>>` 反序列化，解析失败兜底为空列表并记录 warn 日志，不中断整体响应。
- **结果**：旧链路零影响，新接口独立演进；前端刷新后历史完整恢复。
- **面试回答关键词**：查询语义分离、契约向后兼容、JSON 反序列化容错。

### 16.16 Next.js 客户端组件中 localStorage 的 SSR 时序问题（A 轮）

- **问题**：`'use client'` 组件在 SSR 阶段也会在服务端执行一次渲染（生成首屏 HTML），此时 `window`/`localStorage` 不存在；若在 useState 初始化器或组件体内直接读取 localStorage，会抛 "window is not defined" 或造成 hydration 不一致。
- **处理方式**：sessionId 初始为空串，在 `useEffect`（仅客户端执行）中从 localStorage 读取或生成并 setState；依赖 sessionId 的历史加载 effect 在 ID 就绪后才触发；后端未启动时历史加载失败静默降级为空会话，不阻塞提问。
- **结果**：刷新页面后会话历史完整恢复，SSR/CSR 均无报错。
- **面试回答关键词**：SSR 副作用边界、useEffect 时序、优雅降级。

### 16.17 Agent 图与服务的割裂：LangGraph 未接线（B 轮起点）

- **问题**：项目根目录 `src/core/agent_graph.py` 已实现 LangGraph 状态机（classifier→retrieve/guardrail→gen 条件路由），但 `services/ai-service/app/main.py` 的 `/api/agent/analyze` 实际执行的是“向量检索 → 拼 Prompt 生成”两步写死函数调用，LangGraph 代码是未接线的死代码。系统行为比 workflow 更弱：路由决策写死在代码里，无法演进为 LLM 自主决策的 Agent。
- **处理方式（B1）**：不在 main.py 里 import 根目录 src（跨包依赖混乱），而是在 ai-service 内自建 `app/agent/` 包（state/nodes/graph/llm），把图实现与 FastAPI 服务放在同一项目内接线；B2 起引入 Tool Calling 与动态 RAG 开关，B3 建立 ReAct 循环，逐步具备 Agent 工作模式。
- **结果**：B1 完成后同一接口对外行为不变（契约兼容），但执行路径已由图引擎驱动，为工具化改造铺路。
- **面试回答关键词**：模块接线、死代码清理、架构演进路径。

### 16.18 Agent 工具调用的可靠性：动态 RAG 开关与 Prompt 约束（B2）

- **问题**：接入 Ollama + Qwen2.5:7b 的 function calling 后，第一版 system prompt 下，症状类问题（“发热、汗出、恶风是什么证？”）模型不调用检索工具，直接凭自身知识回答并编造条文编号，违反严格模式“必须基于证据”的约束；而在带“请检索”显式指令的单测中却能正确调用工具——说明工具调用行为高度依赖 prompt 引导强度，而不是模型不具备能力。
- **处理方式**：
  - 先实测模型工具能力三场景：工具选择与参数生成正常、工具结果回填后能基于证据生成最终回答、常识问题倾向性调用工具；
  - 收紧 system prompt：明确“涉及症状辨证/条文内容/方剂组成必须先调用工具，仅与条文无关的一般性问题可直接回答，严禁编造条文编号或原文”；
  - Agent 循环架构：guardrail（关键词硬边界，不交 LLM 决策）→ agent（LLM 决策）⇄ tools（执行回填），循环上限 3 轮防死循环；
  - 检索工具返回结构化证据（document_id/title/content/score），最终响应 citations 从图状态提取，引用可追溯。
- **结果**：症状问题自动触发 retrieve_guilinguben + lookup_formula 双工具组合调用并基于证据回答；常识问题零工具直接回答；越界问题被硬边界拦截。动态 RAG 开关由模型自主决策落地，系统首次具备 Agent 工作模式。
- **面试回答关键词**：Function Calling、动态 RAG 开关、Prompt 约束调优、Agent 循环防死锁。

### 16.19 多轮历史答案污染工具调用决策（B2 验收修复）

- **问题**：真实联调中发现：当新问题与历史上下文中的某个旧问题相同或相似时（如“发热、恶寒、身疼痛是什么证？”），模型 0 次工具调用、直接复述历史答案，甚至把历史中上一轮 AI 编造的条文（“第1条”）连同“[原文证据]”标记一起复述——历史幻觉通过多轮记忆被“洗白”为可信上下文。
- **根因**：history_context 由 Java 端把最近 5 轮完整 User/AI 回答拼进 system prompt，其中包含早期轮次未基于证据生成的幻觉条文；模型判断“答案与证据已在上下文中”，跳过工具调用。纯 system prompt 软约束（声明“历史不构成证据”）对 7B 模型遵从度不足，复述行为依然出现。
- **处理方式**：
  - system prompt 双重强化：历史上下文标注“仅供理解对话连续性，其中的回答与引用不构成证据”；工作方式增加“即使历史中已出现过相似问题，也必须调用工具获取当前证据，不得直接复述历史结论”；
  - 严格模式下 user 消息末尾追加即时强制指令“本次提问必须通过工具检索证据后回答”（近因效应强于 system prompt，实测生效）；
  - 自由模式不追加指令，保持 LLM 自主决策（动态 RAG 开关语义不变）。
- **结果**：复现场景修复后，模型正确调用检索工具并基于真实证据回答（旧幻觉说“太阳中风”，证据修正为“伤寒”）；回归验证：严格模式常识问题仍直接回答且声明证据边界、自由模式症状问题自主检索、自由模式常识问题直接回答，均无回归。
- **面试回答关键词**：多轮幻觉传播、工具调用决策干扰、Prompt 近因效应、分层约束设计。

### 16.20 小模型工具调用决策的不确定性：冷启动失败模式与代码兜底（B2 验收修复）

- **问题**：真实联调发现冷启动场景（无历史上下文）首次提问“发热、恶寒、身疼痛是什么证？”时，模型不调用工具直接回答，并编造“第1条”和“[原文证据：《桂林古本伤寒杂病论》第1条]”标记——幻觉式自我引用，模型在无工具结果时模仿系统“带证据回答”的输出格式。
- **根因**：Qwen2.5:7b 的 tool calling 决策本质是概率性采样，对训练数据中高频的经典条文问题（“发热恶寒身疼痛”=太阳伤寒教材内容），模型自认为知识充足，直接作答倾向压过工具调用倾向；同一类问题不同措辞决策不同（“发热、汗出、恶风”会调工具，“发热、恶寒、身疼痛”不调），暴露 B2 验证样本覆盖不足（只测了一个症状问题变体）。纯 prompt 软约束对 7B 模型遵从度有限。
- **备选方案实测**：Ollama `tool_choice="required"` 在 Ollama 0.17.4 + qwen2.5:7b 下不稳定——同一请求两次执行结果不同（一次返回 tool_calls、一次不返回），模型模板未完全实现强制语义，不能作为可靠性依赖。
- **处理方式（软约束 + 硬兜底分层设计）**：严格模式首轮增加代码层确定性兜底——若首轮模型未调用工具直接回答，丢弃其直接回答（正是幻觉条文来源），代码强制以原始问题为 query 注入一次 retrieve_guilinguben 调用，工具执行后第二轮让模型基于证据回答；自由模式不兜底，保持 LLM 完全自主（动态 RAG 开关语义不变）。
- **结果**：冷启动场景 3 次复测全部基于证据回答（正确结论“名为伤寒”）；mock 验证兜底分支确定性触发；历史复述场景回归中模型再次不调工具（prompt 约束复现失效的实例），兜底触发保证证据闭环；严格模式常识问题经兜底后回答“文献未提及作者，一般认为张仲景所著”，符合严格模式“无证据时明确说明”语义；自由模式症状问题自主检索、常识问题直接回答，均无回归。
- **面试回答关键词**：小模型 tool calling 不确定性、幻觉式自我引用、软约束+硬兜底分层设计、tool_choice 兼容性。

### 16.21 企业级工具调用保障方案与当前方案的差距（B2 验收引申）

- **背景**：16.19/16.20 两次验收失败均源于同一根因——Qwen2.5:7b 的工具调用决策不稳定，由此引出“企业级系统如何保证是否调用工具”的完整对比。
- **企业级五层保障**：
  - 模型选型层：企业级不用 7B 做工具决策，选用 GPT-4o/Claude/DeepSeek-V3/Qwen-72B 等工具调用稳定的大模型，选型参考 Berkeley Function Calling Leaderboard、τ-bench 等基准；
  - 引擎/API 层：OpenAI `tool_choice="required"` 是服务端硬保证必返回 tool_calls，而本地 Ollama 对 Qwen 模板是软实现（实测同一请求两次结果不同）；vLLM 等框架支持 grammar-based decoding 结构化输出约束；
  - 架构模式层：Always-Retrieve（所有问题强制检索，LLM 只判断证据是否可用——Perplexity/New Bing 及医疗金融等合规场景主流）、Router 两阶段决策（先输出结构化 JSON 决策再由代码路由）、轻量分类器路由（BERT 意图分类，确定性 100% 但灵活性差）、混合模式（规则快路径 + LLM 决策慢路径）；
  - 可靠性工程层：工具调用格式错误重试、参数 Pydantic 校验、自建工具调用评测集回归、调用率/幻觉率/证据引用率监控；
  - 降级兜底层：模型决策失败时代码兜底保证系统不裸奔。
- **当前方案定位**：严格模式 = Always-Retrieve 的代码级实现（符合医疗文献类合规场景的正确选择），自由模式 = LLM 自主 auto 语义；与企业的差距主要在模型规格（7B vs 大模型）与评测集回归机制缺失（已列入查缺补漏阶段）。
- **面试回答关键词**：tool calling 可靠性、Always-Retrieve 模式、Router 两阶段决策、评测集回归、分层保障设计。

### 16.22 Agent 围栏升级与循环截断收敛（B3）

- **问题**：B2 的关键词围栏只能拦截枚举内的越界问题（“写代码/股票/天气”等），无法覆盖“帮我写一首诗”“什么是微积分”等枚举外越界问题；且工具循环达到 MAX_ITERATIONS 截断时直接返回空回答，由 main.py 固定文案降级，体验差。
- **处理方式**：
  - 双层围栏：关键词快路径（确定性、零延迟）+ LLM 越界判定慢路径（few-shot prompt：单词 YES/NO 输出 + 4 组示例，temperature=0）；判定失败 fail-open 放行（围栏故障不阻断服务，宁可放行不误伤正常提问）；
  - 截断收敛：新增 final_answer 节点——达到循环上限时不直接 END，而是不带工具强制基于已有对话与工具结果生成最终回答（防止模型在截断时留下空回答）；
  - 工具异常处理：单个工具执行失败不中断循环，错误文本回填给模型 + 追加 warning，让模型下一轮自行调整。
- **关键调试**：围栏第一版 prompt 把“发热恶寒是什么证”误判为越界（误伤核心症状问题）→ 加 few-shot 示例后 13 用例（含 3 轮重复验证稳定性）全部通过；“高血压怎么治”等现代医学主题被正确拦截。
- **结果**：围栏 13 用例全过；截断收敛场景 3 轮工具后由 final_answer 生成完整基于证据的回答（如“发热恶寒身疼痛是太阳伤寒证”）；5 场景端到端回归全过（关键词拦截、LLM 判定拦截、严格模式症状、自由模式常识、历史复述）。
- **面试回答关键词**：围栏双轨设计、fail-open 容错、循环截断优雅收敛、few-shot 判定稳定化。

### 16.23 方剂名繁简不匹配导致工具查询空结果（B3 全链路实测修复）

- **问题**：全链路实测多轮指代场景——“它的药物组成是什么？”（历史上下文上一条为“麻黄汤的适用症状是什么？”），模型正确理解指代并自主调用 `lookup_formula(formula_name='麻黄汤')`，但工具返回 0 条记录，最终回答“未找到麻黄汤相关条文”。
- **根因**：方剂库 JSON（562 条）的 `formula` 字段为繁体（“麻黃湯”），模型生成的参数为简体（“麻黄汤”），`子串匹配`（“麻黄汤” in “麻黃湯”）失败——繁体数据源与简体模型输出的字符集不一致。
- **处理方式**：`lookup_formula` 增加繁→简归一化映射表（覆盖方剂/症状常见 60 余字），匹配前把查询词与库中字段统一归一化为简体再做子串匹配。
- **结果**：简体/繁体查询双向命中；重测指代场景正确返回麻黄汤组成（麻黄、桂枝、杏仁、炙甘草）并引用【3.18】【7.4-7.6】条文；“桂枝汤呢？”指代变体同样正确。
- **面试回答关键词**：数据源繁简一致性、字符集归一化、多轮指代消解、全链路测试覆盖度。

### 16.24 会话检查点存储介质选型：MemorySaver / SqliteSaver / PostgresSaver 三方案权衡（B4）

- **背景**：B4 为 LangGraph Agent 图挂 checkpointer，实现跨请求图内状态持久化与中断恢复。LangGraph 的 checkpointer 是接口抽象，官方提供三种典型实现，选型还受本项目的架构约束影响："所有数据库操作在 Java 端完成"（Python 端不直连业务数据库）。
- **方案一 MemorySaver（进程内存）**：检查点存进程内存，按 thread_id 维度隔离。优点：零存储依赖、零配置，单机验证机制最快。缺点：进程重启即丢，无法跨重启持久化；多实例部署时状态无法共享。
- **方案二 SqliteSaver（本地 SQLite 文件，langgraph-checkpoint-sqlite）**：检查点写入 ai-service 本地文件（如 data/checkpoints.sqlite）。优点：文件即数据、重启不丢、不依赖任何数据库服务、与 Java 端业务库完全解耦（符合架构约束）、单机场景足够。缺点：文件绑定单机，AI 服务水平扩展为多实例时无法共享状态。
- **方案三 PostgresSaver（langgraph-checkpoint-postgres）**：检查点落 PostgreSQL（checkpoints 三张表），LangGraph 官方生产环境推荐。优点：持久化、多实例共享、与业务库同源运维。缺点：Python 端直连数据库（psycopg），与"所有数据库操作在 Java 端完成"约束冲突；新增依赖与连接配置。
- **决策（B4）**：选 SqliteSaver + 方案甲（保留 Java history_context 注入不变，图内消息链暂不接管多轮上下文，对外行为零变化）；检查点只负责图内状态的持久化与可恢复性（执行轨迹可审计、重启不丢），为查缺补漏阶段"原生消息链多轮"铺好存储层。
- **演进路径**：checkpointer 接口一致，未来多实例部署时仅需把 compile(checkpointer=...) 参数换成 PostgresSaver，节点与图逻辑零改动。
- **面试回答关键词**：checkpointer 接口抽象、存储介质三选权衡（内存/文件/数据库）、架构约束驱动技术选型、演进路径设计。

### 16.25 方剂工具结果未结构化导致 citations 与回答正文不一致（B4 实测发现）

- **问题**：B4 回归实测中，方剂类问题（“麻黄汤的适用症状是什么？”）模型正确调用 `lookup_formula(formula_name='麻黄汤')` 且工具命中 212 条记录，但最终响应 intent=no_match、citations=0，而回答正文却引用“条文证据”表述方剂症状——citations 字段与回答正文不一致，warning 文案“本回答未基于文献检索证据”与实际相悖。
- **根因**：`execute_tool_call` 对 lookup_formula 按设计返回空证据列表（仅 retrieve_guilinguben 产出结构化证据，tools.py 注释“检索证据列表（仅检索工具有）”），方剂条文以纯文本形式回填给模型；模型只调用方剂工具而不调向量检索时（7B 工具选择概率性，16.20），图状态 retrieved 为空。
- **处理方式（列查缺补漏）**：将方剂记录的 ref/symptom/formula 转换为结构化 Citation（document_id 用条文编号），使 lookup_formula 也产出 citations；同时 intent 判定与 warning 文案按“是否基于工具证据（含方剂库）”统一口径。
- **面试回答关键词**：工具结果结构化统一、响应契约一致性（citations/intent/warnings 三字段对齐）、概率性工具选择下的健壮性设计。

### 16.26 向量库 FAISS → Milvus 的可替换架构设计（岗位纠偏·优先级提前）

- **背景**：14 份招聘 6 份点名 Milvus/Qdrant 等企业级向量库；项目当前用 FAISS 本地索引（16.7 原决策：404 片段够用、暂不引入复杂中间件），技术层面原决策成立，但从面试市场角度 Milvus 是高频考点，且基础设施早已备齐（docker-compose 已定义 milvus+etcd+minio，config.py 已有 milvus_uri 占位），接线成本低、收益高。
- **处理方式**：新增 `MilvusVectorStore` 适配器实现 ports.py 的 `VectorStore` 协议（build_index/similarity_search/similarity_search_with_score/as_retriever），启动配置切换 FAISS/Milvus；Agent、API、业务用例零改动——这正是当初“业务代码必须依赖统一向量库端口，不得直接依赖 FAISS API”约定的兑现。
- **结果（预期）**：同一套 Agent 代码可跑两种向量库，“本地 MVP 适配器 + 生产适配器”双实现；面试可讲“面向接口设计的提前收益：换基础设施不改业务”。
- **面试回答关键词**：面向接口设计、适配器模式、基础设施可替换、演进路径规划。

### 16.27 自研 LangGraph Agent 与 Dify/Coze 平台化的取舍（岗位纠偏·面试必问）

- **背景**：14 份招聘 5 份提到 Dify/Coze/RAGFlow 平台，“平台化 vs 定制化”是面试高频题。
- **项目立场**：本项目选自研 LangGraph，因为平台做不了工程细节——双层围栏 fail-open、严格模式首轮代码兜底（丢弃幻觉回答强制注入检索）、工具异常回填、checkpointer 存储介质自选，这些确定性兜底逻辑在低代码平台上无法实现；医疗文献场景要求引用可追溯、证据闭环，需要代码级控制。
- **结论**：平台适合快速 PoC 与非研发团队；自研适合合规约束强、需要确定性兜底与深度定制的场景。面试回答应讲“按场景选型 + 自研能做什么平台做不了的事”，而非贬低平台。
- **面试回答关键词**：平台化 vs 自研、定制化需求驱动选型、低代码平台边界。

### 16.28 不做微调的技术取舍（岗位纠偏·加分项的策略性放弃）

- **背景**：14 份招聘 4 份将 Fine-tuning 列为加分项，面试可能被问“为什么不做微调”。
- **项目立场**：本地 Qwen2.5:7b + 单本古籍场景不做微调，理由：(1) 数据量不足——一本 PDF 不足以支撑稳定微调，易过拟合/灾难性遗忘；(2) 领域知识走 RAG 注入——知识在文档不在参数，更新成本低、来源可追溯；(3) 当前问题是工具调用决策与引用真实性，微调不直接解决，工程兜底（16.19/16.20）才是对症；(4) 成本收益——算力与评测闭环成本高。
- **结论**：明确“RAG 优先、微调为备选”路线；若未来数据与算力到位，LoRA 是合理演进方向（认知已备）。
- **面试回答关键词**：RAG 优先原则、微调适用边界、成本收益权衡。

### 16.29 MCP 协议演进路径（岗位纠偏·趋势储备）

- **背景**：14 份招聘 4 份提及 MCP（Model Context Protocol），是工具生态标准化趋势。
- **项目现状**：工具层按 OpenAI function calling 格式定义（TOOL_DEFINITIONS）+ execute_tool_call 统一分发入口，检索/方剂两个工具；分发入口已是“工具注册表”雏形，function calling schema 与 MCP tool schema 同构。
- **演进路径**：将现有工具封装为 MCP Server（retrieve/lookup 作为 tools 暴露），LangGraph 经 MCP 适配器调用；Java 侧可作为 MCP client 供其他 Agent 平台复用——工具层格式标准化使演进成本低。
- **面试回答关键词**：MCP 协议、工具生态标准化、接口同构演进。

### 16.30 SSE 流式恢复策略分层设计：Last-Event-ID 续传的取舍（B5 已实现）

- **背景**：B5 实现 SSE 三端流式输出，岗位要求的断连/去重/恢复三件套需分层设计。一个协议细节：浏览器原生 EventSource 只支持 GET，而本项目流式接口是 POST（问题在请求体），前端用 fetch 手动解析 SSE、手动携带 Last-Event-ID header。
- **Layer 1（必做·已实现）**：SSE 事件带自增 event_id——事件去重本来就依赖它，零额外成本。
- **Layer 2（建议做·已实现）**：Java 侧每会话事件缓冲（内存 CopyOnWriteArrayList + TTL 5 分钟，AnalysisStreamService），断连重连（带 Last-Event-ID）先从缓冲续发剩余增量，覆盖 99% 短断连（网络抖动），用户无感；实测成本约 Java 211 行 + 前端约 120 行。
- **Layer 3（不做）**：Python 支持 last_event_id 参数重订——仅在“Java 也重启、Python 仍在跑”时有用；本地单机 Java 重启后本应走历史接口恢复，收益低，不引入。
- **Layer 4（不做）**：Redis/DB 持久化事件与 offset——多实例部署才需要，单机不引入。
- **兜底**：record-level 恢复（前端重连后调 GET /api/analysis/history 补齐已落库记录）作为最终兜底；断连后 Java 仍让 Python 跑完并照常落库（断连仅移除转发器、不取消上游订阅），不浪费已生成结果。
- **B5 验收结果（2026-09-18）**：三端联调 12/12 断言全过（事件序列与 id 自增、done 落库、断连后 Last-Event-ID 重放 id 连续、旧接口回归）；浏览器实测打字机/状态文本/引用证据卡/越界快路径正常。实测新增两个编码细节（面试高频追问）：
  1. **SSE 响应必须声明 charset=UTF-8**：Java SseEmitter 默认响应头 text/event-stream 无 charset，客户端按 ISO-8859-1 解码 UTF-8 字节 → 中文乱码且 0x85 等字节被 splitlines 误判换行导致 JSON 解析失败；修复：controller 提前 response.setContentType("text/event-stream;charset=UTF-8")（Spring 写首条消息时若 Content-Type 已存在则不覆盖）。
  2. **SseEmitter.send 不能传 MediaType 参数**：带 mediaType 的 send(Object, MediaType) 重载绕过 SseEventBuilder 拆包，且 StringHttpMessageConverter 不支持 text/event-stream;charset=UTF-8 → canWrite 全部失败抛 IllegalArgumentException 被 catch 吞掉，事件静默丢失（客户端零字节、5 分钟后 AsyncRequestTimeout）；修复：send 只传 SseEmitter.event() 构建器（spring-webmvc 6.1.12 字节码实证）。
- **面试回答关键词**：SSE 三件套（断连/去重/恢复）、Last-Event-ID 续传、分层恢复策略、EventSource 协议边界（POST 流式需 fetch 手动解析）、流式编码链路（charset 声明与消息转换器兼容性）。

### 16.31 方剂工具结构化引用：lookup_formula 证据并入 citations（查缺补漏①已实现）

- **背景**：B4/B5 实测发现 lookup_formula 按设计只回填文本不产出结构化证据（execute_tool_call 仅检索工具有证据列表），模型仅调方剂工具时 intent=no_match 且 citations=0，而回答正文却引用了方剂库条文——“回答有引用、响应无引用”的口径矛盾。方剂证据与 PDF 检索证据同构后统一计入 citations，前端引用证据卡即可展示方剂来源。
- **实现（2026-09-18）**：
  1. tools.py：lookup_formula 返回 (文本, 证据列表)，证据与检索证据同构（document_id/title/content/score）；document_id 以 "formula_db:" 前缀标识方剂库来源（供 intent 归类）；score=1.0（精确匹配非相似度检索，确定性命中记满分）；execute_tool_call 分支透传证据。
  2. main.py `_build_final_response`：证据全部为 formula_db: 来源 → intent=formula_query（新增契约值，三端仅透传与日志展示，无白名单校验）+ 方剂库专属 warning 文案；混合/纯检索保持 symptom_query；无证据保持 no_match；围栏保持 out_of_scope。
  3. C 轮兼容设计（方剂库将重构为 4 字段：方剂所在页码/方剂名/药物组成/注意事项）：document_id/title/content 字段命名已按此方向预留，届时仅调整取数来源（如 content 改为药物组成+注意事项、document_id 带页码），调用方零改动。
- **验收（2026-09-18）**：
  1. 单元断言 8 项全过：证据四键齐全/document_id 前缀/execute 透传/未命中空证据/_build_final_response 四分支（formula_query/symptom_query/no_match/out_of_scope）。
  2. 非流式端到端（Java 8080 三端链路）：“麻黄汤的组成” → intent=formula_query + citations=5（来源 formula_db:【3.18】）；“桂枝汤的组成” → formula_query + 5 citations；症状问题回归 → symptom_query + 5 citations（guilinguben.pdf:p65:c0）；越界快路径 → out_of_scope 43ms。
  3. 流式端到端：done 事件 intent=formula_query + citations=5（来源 formula_db:【5.21】等），Java 落库正常。
- **面试回答关键词**：多源证据统一建模（检索证据与结构化库证据同构）、来源前缀区分 intent 归类、契约值域扩展（formula_query）、字段命名前向兼容。

### 16.32 多轮记忆治理：历史上下文摘要化与历史接口分页（查缺补漏②已实现）

- **背景**：B5 后多轮对话把 Java 拼装的最近 5 轮 User/AI 原文整体注入 system prompt（B5 实测 5 轮可达 1000+ 字），token 随轮数线性膨胀，旧轮次重复内容挤占新问题的生成窗口，且历史接口一次返回全量记录、长会话无分页。
- **实现（2026-09-18）**：
  1. Python 摘要模块 `app/memory/history_summarizer.py`：滑动窗口策略——最近 1 轮保留原文（指代解析依赖，如“它的组成是什么？”），更早轮次压缩为 LLM 要点摘要（标注“仅供理解对话连续性，不构成证据”）；增量缓存：同会话连续对话时“旧摘要 + 新增轮次原文”合并重新提炼一次（每请求至多 1 次摘要 LLM 调用，缓存命中零开销）；单轮对话（≤1 轮）原样注入零 LLM 开销；摘要失败 fail-open 降级为原文截断（每轮 80 字）不阻断服务；缓存为进程内存（session_id 为键），重启后首次请求重算（可接受）。轮次解析按 Java 拼接格式（“User:/AI:” + 空行）切分。
  2. `llm.py` 新增 `summarize_history`（要点式摘要指令：只保留主题/症状/条文编号/方剂名/结论，100 字以内，temperature 0.2）；`state.py` 加 `session_id` 字段；`nodes.py` guardrail 节点先经 `compress_history_context` 压缩再进 `build_system_prompt`。
  3. 自由模式弱兜底（main.py）：无工具证据且回答含条文编号（正则 `【6.2】`/`[4.9]`）时追加“未经过文献检索验证”警示（严格模式不叠加）。
  4. Java 历史接口分页：`GET /api/analysis/history` 增加 limit/offset（limit clamp 1~200），按 createdAt 倒序取页后反转为升序返回，响应改为 `HistoryPage{messages,total,hasMore}`；repository 用 `findBySessionId(Pageable)` 分页 + `countBySessionId` 总数；Top5 上下文注入保留显式 LIMIT 5 JPQL。
  5. 前端：`fetchSessionHistory` 带 limit/offset 返回 HistoryPage；页首“加载更早消息”按钮（hasMore 时显示），更早页升序 prepend；断连恢复路径复用最新一页刷新逻辑。
- **验收（2026-09-18）**：
  1. 单元 7 组全过：轮次解析、单轮零 LLM 开销（monkeypatch 计数）、多轮摘要 + 最近一轮原文保留、缓存命中零新增调用、增量更新仅一次调用、摘要失败截断降级、条文编号正则命中/不误伤。
  2. 端到端 4 轮对话（Java 8080 三端链路）：第 1 轮麻黄汤 → formula_query+5 citations；第 2 轮“它的主治症状有哪些？” → 指代解析成功（检索“麻黄汤 主治”，symptom_query+3 citations）；第 3 轮桂枝汤 → 摘要触发（Python 日志 `[Memory]` 摘要 49 字）+ formula_query+5 citations；第 4 轮增量摘要 34 字。
  3. 弱兜底单元 3 断言：自由模式+条文编号+无证据 → 警示追加；严格模式不叠加；无编号不误伤。
  4. 分页 5 断言（4 条记录会话）：全量页/最新页（offset=0 升序 2 条 hasMore=true）/更早页（offset=2）/越界空页/limit=0 clamp 到 1。
  5. 前端 tsc 编译通过。
- **踩坑记录**：接口测试脚本请求体字段用 snake_case（session_id/strict_mode/top_k）而 AnalyzeRequest 为 camelCase record（无 @JsonProperty），Jackson 反序列化出 null/false/0 → 建会话时 session_id 非空约束违反 500（DataIntegrityViolationException），定位靠 Java 日志 Hibernate flush 帧 + 数据库会话未落库两个证据交叉验证。前端一直用 camelCase 故未暴露。教训：接口契约字段命名以 Java DTO 为准，测试脚本与真实客户端保持一致。
- **浏览器实测补充（2026-09-18，用户验收反馈）**：
  1. 点击“加载更早消息”后页面跳到最底：prepend 更早页改变了 messages，误触发了“新消息自动滚动到底部” effect → 修复为滚动锚定（prepend 前记录滚动容器 scrollHeight/scrollTop，effect 里补偿 scrollTop 保持视口不动，新内容从上方插入，与微信/Telegram 加载历史行为一致；正常提问仍自动滚底）。
  2. 方剂库证据卡片两处误导：score=1.0 展示成“匹配度 100.0%”（查表命中非相似度检索）；点击“查看原文”静默无效（document_id 无页码，前端正则 /p(\d+)/ 解析失败且无提示）→ 修复：formula_db 来源改显琥珀色“方剂库精确匹配”标签 + 灰字“方剂库条目，暂不支持跳转 PDF（C 轮含页码后支持）”，点击直接返回。根因：方剂库 JSON 为 3 字段（ref/symptom/formula）无页码，跳 PDF 需 C 轮 4 字段重构（页码/方剂名/药物组成/注意事项）后支持。
- **面试回答关键词**：上下文管理价值（滑动窗口 + LLM 摘要、增量缓存降低重复摘要开销、fail-open 降级不阻断主链路）、token 预算控制、指代解析保留最近原文、历史接口分页契约（limit/offset + total + hasMore）。

### 16.33 Milvus 接线：VectorStore 协议适配器与向量库选型（查缺补漏③已实现）

- **背景**：FAISS 是本地 MVP（进程内库、单机文件索引、零部署），招聘市场高频考察生产级向量库；Milvus standalone 早在 compose 中预留但未接线。目标：协议适配器实现零改动切换（Agent/API 层无感知）+ FAISS 保留为可回退本地适配器。
- **实现（2026-09-18）**：
  1. `app/retrieval/milvus_store.py`：MilvusVectorStore 复用 ports.py 协议四方法（build_index/similarity_search/similarity_search_with_score/as_retriever）；collection schema：id(INT64 auto_id 主键)/content(VARCHAR 65535)/source/page/chunk 标量字段 + embedding(FLOAT_VECTOR 1024 维，bge-large-zh-v1.5)；索引 IVF_FLAT+COSINE（nlist=128，检索 nprobe=16）；已存在 collection 时惰性加载不重建。
  2. **分数语义对齐（关键设计）**：FAISS IndexFlatL2 返回 L2 距离（越小越好），tools 层 normalize_score=1/(1+d)；Milvus COSINE 返回相似度（越大越好）→ 适配器返回 `1-cosine` 伪 L2 距离，与 FAISS 分数同语义，normalize_score 及 tools/Agent/API 全链路零改动。
  3. 切换机制：`config.py` 增加 vector_backend（faiss 默认/milvus）+ milvus_uri/milvus_collection_name；`main.py` RetrievalService 按配置分支实例化；Milvus 连接失败 fail-fast（明确提示启动容器或切回 faiss）；collection 不存在时自动走 PdfDocumentLoader 解析 + build_index。
  4. `scripts/build_milvus_index.py`：灌数脚本复用 PdfDocumentLoader 切块清洗 + LocalEmbeddingProvider（与 FAISS 同一数据源、同一向量口径），174 片段全量入 Milvus，末尾抽查检索验证。
  5. compose 修正（三处）：milvus command 需 `run standalone` 位置参数（原始缺失致重启循环）；minio 镜像换 quay.io 直连（docker.io/minio/minio 被上游限制，任何加速器代理均 403）+ quay.io/minio/mc 一次性建 a-bucket；etcd advertise-client-urls 改服务名 etcd:2379（0.0.0.0 会被客户端重定向失败）。
- **验收（2026-09-18）**：
  1. Milvus vs FAISS 同一查询集 8 条（症状/方剂/条文各类）对比：top-5 完全重合 8/8、首条一致；耗时 FAISS 约 201ms vs Milvus 约 181ms（含 embedding 时间），量级持平——小数据量下 Milvus 服务化开销被 embed 耗时掩盖，零性能损失。
  2. 三端回归（Java 8080 链路真实问答）：Q1 症状 → symptom_query + 3 citations（PDF 证据来自 Milvus 检索）、Q2 方剂 → formula_query + 5 citations；严格模式症状检索路径不变。
  3. 默认 vector_backend=faiss 对现网零影响；切 milvus 仅改 services/ai-service/.env 后重启。
- **七种向量库对比与取舍**（面试高频题）：

  | 向量库 | 定位 | 优势 | 局限/适用边界 |
  |---|---|---|---|
  | FAISS | 本地库（非服务） | 零部署、单机检索极快、MVP 首选 | 无独立服务、无分布式、多进程共享弱 |
  | Milvus | 云原生分布式向量数据库 | 亿级规模、多索引类型、副本分片、监控完善 | 部署重（依赖 etcd+minio）、小数据量杀鸡用牛刀 |
  | Chroma | 轻量嵌入式向量库 | pip 即装、自带持久化、LangChain 集成好 | 单机为主、无分布式、性能上限低 |
  | pgvector | PostgreSQL 扩展 | 复用现有 PG、事务一致性、SQL 过滤一体 | 大规模召回性能弱、索引构建慢、受 PG 行模型限制 |
  | Redis(RediSearch) | 缓存型向量检索 | 超低延迟、天然缓存场景 | 内存成本高、数据集大小受限、向量是附加能力 |
  | Elasticsearch | 全文检索+向量混合 | BM25+kNN 混合检索一体、生态大 | 资源重、向量检索性能一般、运维复杂 |
  | OpenSearch | ES 开源分支 | 同上 + 协议更干净 | 同上 |
  | Qdrant | 专用向量数据库（Rust） | 单机性能好、过滤强、部署轻 | 分布式能力弱于 Milvus、生态较小 |

  **取舍结论**：本地 MVP 阶段选 FAISS（零部署、性能足够、过早优化是反模式）；生产化切 Milvus（分布式扩展 + 岗位高频技能）；两者通过 ports.py 协议适配器零改动切换，避免锁定单一向量库。若未来需要全文+向量混合检索，再评估 ES/OpenSearch。
- **踩坑记录**：
  1. docker.io/minio/minio 仓库被上游限制，换 daocloud/腾讯云加速器仍 403（加速器只是代理上游）→ 通过 quay.io API 确认真实 tag 后换 quay.io 直连解决。
  2. milvus v2.4 的 `milvus run` 需 standalone 位置参数，原始 compose 缺失导致容器重启循环（日志 `Unknown server type = --config-file=...`）。
  3. pydantic-settings `env_file=".env"` 按启动工作目录解析——根目录 .env 对 ai-service 不生效，VECTOR_BACKEND 需放在 services/ai-service/.env（此前配置值碰巧与默认一致未暴露）。
- **面试回答关键词**：适配器模式（ports.py 协议双实现）、分数语义对齐（1-cosine 伪 L2 距离）、零改动切换、向量库选型矩阵、Milvus 部署链路（etcd+minio 依赖与容器编排）。
- **验收后运营决策（2026-09-18）**：用户确认验收；因本机内存紧张（Milvus 栈约 3~5 GB）切回 FAISS——services/ai-service/.env 改 VECTOR_BACKEND=faiss + 重启 Python（日志确认加载 data/faiss_index 秒级启动），milvus/etcd/minio 容器停止（数据卷保留，随时可重启恢复）。本次切换验证了开关机制的双向可用性与 FAISS 回退路径（面试可复述：向量库切换零代码改动、服务化与本地化的取舍落地）。

### 16.34 侧栏会话列表与新建会话：DeepSeek 风格会话管理（A 轮搁置项已实现）

- **背景**：A 轮遗留两个搁置决策——前端无“新建会话”入口（localStorage 固定 sessionId 后缺少重置），历史加载失败降级策略未确认。用户拍板：像网页版 DeepSeek 一样做左侧历史会话列表 + 左上角新建会话按钮。
- **实现（2026-09-18）**：
  1. Java 新增 `GET /api/analysis/sessions`：一条原生 SQL 聚合查询返回每个会话的 sessionId/首条提问(title)/记录数/最后更新时间（含空会话 title 为 null，按最后活跃倒序）；新 DTO SessionSummary（snake_case 契约，与 HistoryMessage 风格一致）；SecurityConfig permitAll 显式放行新路径。
  2. 前端左侧侧栏（深色，DeepSeek 风格）：顶部“+ 新建会话”按钮 + 会话列表（title 单行截断、相对时间（刚刚/x 分钟前/x 天前）+ 轮数、当前会话高亮）；小屏（<md）隐藏侧栏保移动端可用；主区保持原聊天布局。
  3. 交互：新建会话 = 重新生成 sessionId 写入 localStorage + 清空视图（旧会话数据保留在库中侧栏可见）；切换会话 = 更新 localStorage + setSessionId，复用既有“sessionId 变化 → 加载历史”effect；流式 done/error/历史恢复落库后 refreshSessions 刷新侧栏（新会话自动置顶）；loading 期间禁止新建/切换防流式回调串会话。
  4. 历史加载静默降级策略（搁置项确认）：会话列表/历史加载失败均静默降级（空列表/空会话），不阻塞提问。
- **验收（2026-09-18）**：前端 tsc + Java mvn compile 通过；端到端 4 断言全过——新会话流式提问（formula_query+5 citations）→ 会话列表顶部出现且 title=首问、轮数=1 → 该会话历史加载正常 → 既有会话历史回归正常。
- **踩坑记录**：
  1. 新增接口未在 SecurityConfig 放行 → 401（Spring Security 默认 anyRequest().authenticated()，新路径必须显式 permitAll）。
  2. Hibernate 6 原生聚合查询的 timestamptz 列映射为 Instant 而非 java.sql.Timestamp → 强转 ClassCastException；修复为 instanceof 双类型兼容。
  3. 会话沙箱限制：taskkill/wmic/powershell 等进程控制命令被拦截（CreateProcessAsUserW 267），Java 重启由用户执行——环境操作边界记录。
- **面试回答关键词**：会话管理 UI（首问摘要、相对时间、聚合 SQL 一条查询出列表）、SSR 安全的 localStorage 会话标识、状态机复用（sessionId 驱动历史加载）、安全配置最小放行原则、原生查询类型映射。

### 16.35 Redis 接线：会话历史缓存 + 接口限流（⑤，2026-09-18）

- **背景**：⑤Redis 接线是市场高频技能（14 份招聘信息中 7 帖要求 Redis），也是“非 demo”生产化叙事的关键一环。用户对 Redis 不熟练，本卡点按教学式记录（含概念、命令、代码块）。
- **Redis 是什么（一句话版）**：内存键值数据库；单线程事件循环使命令串行执行（并发安全天然原子）；支持 TTL 过期删除与持久化（RDB 快照/AOF 追加日志）；本项目用它做缓存与限流计数（面试要能说清“为什么用 Redis”——内存快、原子计数、TTL 自动过期，三个点全用上）。
- **架构实现（2026-09-18）**：
  1. **会话历史上下文缓存（HistoryCacheService）**：
     - 缓存对象：buildHistoryContext 拼接的最近 5 轮 User/AI 对话文本——每轮分析请求都要查库拼接，读多写少，适合缓存。
     - Key `guilinguben:history:{sessionId}`，TTL 30 分钟；命令 GET/SET（带 TTL）；空上下文也缓存（区分“无历史”与“未缓存”）。
     - **一致性策略：写更新（append）而非写失效（evict）**——本项目最有价值的取舍：时序上每轮请求先 buildHistoryContext（miss 则 put）再落库，若落库时 evict 会删掉本请求刚写的缓存 → 串行对话永远 miss（实测发现后修复）。append 方案：落库时把新轮次追加进缓存 + 裁剪保持 5 轮与查库 findTop5 语义一致 → 连续对话命中率 100%。
  2. **接口限流（RateLimitInterceptor + WebConfig）**：
     - 固定窗口计数：Key `guilinguben:ratelimit:{ip}:{epochSecond/60}`（窗口号随分钟自然滚动）；每请求 INCR 原子自增（Redis 单线程，并发下不丢计数）；首次自增返回 1 时 EXPIRE 120s（略大于窗口，防边界 Key 提前消失）；计数 >30 次/分钟/IP → 429 + Retry-After。
     - 只拦截 `/api/analysis` 与 `/api/analysis/stream`（触发 LLM 推理的昂贵接口）；历史/列表等只读接口不限流。
     - 扩展话题（面试可讲）：固定窗口有边界突刺缺陷（窗口切换瞬间可能 2 倍流量），高并发场景改滑动窗口（ZSET）或令牌桶（Lua 脚本原子扣减）。
  3. **fail-open 容错（四层）**：
     - 启动期：lettuce 客户端惰性连接——Spring 启动只建 Bean 配置不建 TCP 连接，首次执行命令才连接 → **Redis 未启动时 Java 启动完全不报错**（实测验证）。
     - 运行期四处 try/catch：限流检查失败→放行请求；缓存读取失败→退回查库；缓存写入失败→跳过缓存；缓存删除失败→依赖 TTL 兜底。
     - 配置期：application.yml `timeout: 2s`（默认 60s）——Redis 挂了快速失败不拖慢核心链路。
     - 设计思想：**Redis 是加速/保护组件而非核心依赖，挂了就降级但功能完整**。
- **技术细节（命令行速查，用户对 Redis 不熟）**：
  - 启动容器：`docker compose up -d redis`（compose 已备 redis:7-alpine，约 30MB 内存）；进入 CLI：`docker exec -it guilinguben-redis redis-cli`。
  - 常用调试命令：`KEYS guilinguben:*`（看键）、`GET guilinguben:history:{sessionId}`（看缓存值）、`TTL 键名`（看剩余秒数）、`DEL 键名`、`FLUSHDB`（清空，慎用）。
  - Java 侧核心 API（StringRedisTemplate）：`opsForValue().get/set(k, v, TTL)`、`opsForValue().increment(k)`、`expire(k, TTL)`、`delete(k)`。
- **验收（2026-09-18）**：
  - fail-open：Redis 停时 4 条降级日志实锤（限流放行/读退回查库/写跳过/删依赖 TTL）+ 全链路正常（formula_query + 5 citations）。
  - 缓存命中：同会话 3 连问——问 1 miss 查库 0 条；问 2 命中缓存（103 字节，含问 1 完整问答）；问 3 命中缓存（259 字节，含前 2 轮）；多轮指代（“它的主治”、“前面提到的方剂”）全部正确。
  - 限流：31 个请求，前 30 个放行，第 31 个 429（日志“限流触发: ip=0:0:0:0:0:0:0:1, 本窗口请求数=31”）。
  - 三端回归：非流式 + 流式（formula_query + 5 citations + 103 事件）+ sessions/history 接口全过。
- **踩坑记录**：
  1. evict 写失效时序缺陷：put（buildHistoryContext）与 evict（落库）在同一请求内先后发生，evict 删掉自己刚写的缓存 → 串行对话永远 miss；修复为 append 写更新 + 5 轮裁剪（与 findTop5 语义一致）。
  2. 空 question 请求返回 500 而非 400（@Valid 未拦截空串，既有行为非本项引入）——限流测试脚本用空 question 触发 500 且产生失败记录落库（rl-test 测试数据待清理）。
  3. 沙箱拦截进程终止命令（taskkill 267、MSYS2 kill 不识别 Windows 原生 PID）→ Java 重启由用户执行（已记录环境操作边界）。
- **面试回答关键词**：Redis 缓存一致性（写更新 vs 写失效时序分析）、固定窗口限流（INCR 原子性、窗口滚动、边界突刺）、fail-open 降级设计、lettuce 惰性连接、StringRedisTemplate。

### 16.36 PDF 数据治理：条文编号切分 + 方剂库 4 字段 + 页码双轨四端贯通（C 轮，2026-09-18）

- **背景**：B 轮工具集的数据源质量差——检索按固定字符数切块（条文被截断、跨页条文看不到两页内容、页脚小字注释混入正文）；方剂库 JSON 是 3 字段手工整理（缺页码/组成/注意事项），方剂证据卡无法跳 PDF。用户明确要求：检索按条文编号切分（一个编号一条数据）、方剂库 4 字段（页码/方剂名/药物组成/注意事项）、方剂出现几次就几条数据、跨页条文（如【16.26】）要能看到两页内容。
- **实施三步**：
  1. **坐标实验（C1）**：PyMuPDF 分析页脚注释/页眉 y 坐标与正文分离度 → 确认坐标切割可行；页码双轨偏移 PDF_TO_BOOK_OFFSET=12（PDF 页码 = 书页 + 12，书页取自页眉 ·N· 标记）。
  2. **pdf_loader 重构（C2）**：新增 `load_cleaned_pages()` 页级清洗视图（返回 [(pdf_page, book_page, 清洗后文本)]）；全文流按 【X.Y】 编号切分，跨页条文用页偏移区间重叠法拼接（16.26 跨 PDF 169-170 两页）；三层清洗（页眉书页号/页脚注释/夹注小字）。
  3. **方剂库重建（C3）**：页级遍历提取方剂条目（标题行 + 组成 + 煎服法），4 字段（ref/book_page/formula/composition/notes），与附录二/三汤方索引双向交叉校验。
- **方剂误报过滤的核心难点**：真条目“X方”后紧跟组成（药名+剂量），提及/夹注（“X主之。（方見前）”）只是引用。先尝试前字符白名单 → NFKC 清洗把全角括号变半角，真条目大量是“（方見前)X方”形态，白名单漏杀 4 个真条目 → 最终改为 **after 内容判定**：取“方”后 25 字符，匹配 `^(俱見|主之|,)` 判为提及/夹注误报（NARRATION_PAT）。模式字符类需含 ext-A 区（“䗪” U+45EA），后缀需覆盖 湯|散|丸|酒|煎|膏|丹|餅|導|熨|洗|汁|粉|塞。
- **附录索引解析**：4 种行模式（常规“名, 页码”、行尾逗号待续、换行条目、纯页码续行）；名字清洗（去空格 + 去尾“方”）。附录语义 ⊇ 4 字段库语义（附录含提及页，库只收实质条目），交叉校验为信息性报告。
- **成果数据**：检索索引 964 条（原 174 条，每条 = 一条文）；方剂库 446 条 4 字段；附录双向差异 0（附录有/正文无=0、正文有/附录无=0）；86 处页码差全部为附录多出的提及页（已抽查确认形态）；漏提取嫌疑 0。
- **页码双轨贯通四端**：Python 证据 dict 带 pdf_page_start/end + book_page_start/end → schemas.Citation（Pydantic）→ Java AnalyzeResponse.Citation record（Jackson 反序列化）→ 前端 Citation 接口；前端跳转优先 pdf_page_start，旧历史回退 document_id 正则解析。方剂库证据 pdf_page = book_page + 12。
- **跨页渲染（C6 浏览器实测发现并修复）**：前端 PdfViewer 原只渲染单页——16.26 跨页条文第 170 页内容不可见且无翻页控件 → props 增加 endPage，区间内多 `<Page>` 渲染 + 标题区间格式“第 169-170 页”；单页无回归。
- **验收（C6 三端回归 + 浏览器实测）**：
  - 端到端（Java 8080 → Python 8001 → Ollama）：症状问题 citations 5 条全带页码双轨；方剂问题 intent=formula_query + 10 条证据（桂枝湯精确优先排序 + 含“桂枝湯”子串次匹配），pdf=book+12 全部正确。
  - 浏览器实测：方剂库卡片（书页 43）→ 模态框第 55 页 ✓；检索卡片（PDF第154页）→ 第 154 页 ✓；16.26 跨页卡片 → “第 169-170 页”区间渲染、条文结尾“其針藥，各探其源。子當辨記，勿謂不然。”完整可见 ✓；单页格式无回归 ✓。
- **踩坑记录**：
  1. .venv torch 损坏（c10.dll WinError 193）→ 索引重建必须用 torch_env conda 环境（embedding/索引类脚本通用约定）。
  2. Windows GBK 控制台：所有含中文/特殊字符输出的脚本必须 `PYTHONIOENCODING=utf-8` 前缀。
  3. 附录数字 key 残留（“108: [109]”）：纯页码续行被 `.+?` 非贪婪误匹配成 name → entry_pat 改 `[^,]+` + pages_only 优先。
  4. 9 个附录有/正文无方剂：排版空格（“大黃硝石 湯”）、FANG_PAT 后缀缺失、附录名尾“方”与提取名对比 → 三类根因逐一修复。
  5. 子串假阳性（“烏頭桂枝湯方”里的“桂枝湯方”）→ 加词边界检查（name 前不是中文字符）。
  6. 前端跳转将失效：document_id 新格式无页码 → citation 四端链路加页码字段（最小改动：4 个可选字段，旧数据回退正则解析）。
- **面试回答关键词**：PDF 文本层数据治理（页级清洗视图、页码双轨）、正则误报过滤的判定要素选择（前字符 vs after 内容）、附录索引双向交叉校验、跨页条文渲染、四端契约演进（citation 页码字段增量兼容）。

### 16.37 Chroma 切换：嵌入式向量库适配器与三后端对比（下阶段第 4 项，2026-09-19）

- **背景**：C 轮重构后索引已重建为 964 条（FAISS），顺势切换 Chroma 避免重复灌数；Chroma 较 Milvus 更轻（嵌入式 pip 即装、零容器零额外内存、支持元数据过滤）。
- **架构实现**：
  1. **ChromaVectorStore 适配器**（app/retrieval/chroma_store.py，chromadb 1.5.9 原生 SDK，不引 langchain 封装）：PersistentClient 惰性加载本地目录 data/chroma_index；collection 用 `hnsw:space=cosine`——query 返回 distance = 1-cos，与 Milvus 适配器伪 L2 距离语义一致，tools.py 的 `normalize_score=1/(1+d)` 零改动；`embedding_function=None` 显式传向量，不触发 Chroma 默认 onnx embedding 下载；metadata 标量类型保险（loader 6 字段全 str/int 直传）。
  2. **协议零改动**：ports.py VectorStore 协议不变，tools/Agent/API/Java/前端全部零改动；main.py 增加 chroma 分支（collection 存在→惰性加载，不存在→从 PDF 自动构建），config.py 增加 chroma_persist_dir/chroma_collection_name，requirements.txt 追加 chromadb==1.5.9。
  3. **灌数脚本** scripts/build_chroma_index.py：复用 loader.load() 964 条 + 分批 256 add + 抽查验证（页码双轨 metadata）。
- **验收（2026-09-19）**：
  - 8 查询 top-5 与 FAISS 对比：**40/40 完全重合 + 8/8 排序一致**（bge 向量归一化下 cosine 排序与 L2 等价，与 Milvus 验收结论一致）。
  - 三端回归（Java 8080 → Python 8001 chroma 版 → Ollama）：症状问题 5 citations 页码双轨完整且 top 命中与 FAISS 版一致；方剂问题 formula_query + 10 citations（pdf=book+12）全过。
  - 切回验证：FAISS 索引加载 + 检索正常（双向切换机制可用）。
- **三后端对比（面试可讲）**：FAISS（进程内存/本地文件，无服务依赖，单机 MVP）/ Milvus（分布式向量数据库，需 etcd+minio+容器栈，适合大规模与生产）/ Chroma（嵌入式持久化，HNSW + cosine，元数据过滤，中量级单机场景最优性价比）——三者均通过 ports.py 协议适配，vector_backend 开关一键切换，业务代码零改动。
- **踩坑记录**：
  1. chromadb 1.x 默认 embedding function（onnx MiniLM）在 add/query 未显式传向量时会尝试下载模型——适配器建 collection 时显式 `embedding_function=None` + 总是传向量规避。
  2. 临时探测脚本路径 bug（`ROOT = SCRIPT_DIR.parent` 多一层）——项目根目录下脚本 ROOT 应为 SCRIPT_DIR 本身。
  3. pydantic Settings 无 BASE_DIR 属性——BASE_DIR 是 config 模块级变量，需单独导入。
- **面试回答关键词**：多后端向量库适配器架构（协议抽象 + 配置开关）、距离语义对齐（cosine vs L2 的单调等价）、嵌入式向量库选型（Chroma vs Milvus vs FAISS 成本对比）、契约零改动切换。

### 16.38 Milvus 适配器 C 轮字段同步与恢复验证（用户指示收尾，2026-09-19）

- **背景**：16.33 验收后 milvus 因内存紧张停用切回 FAISS，其适配器 schema 停留在 C 轮之前的旧三字段（source/page/chunk）——若恢复启用，tools.py 取 metadata 页码字段为 None、证据缺页码跳转。用户指示“把尾巴收了”，直接修复而非记录技术债。
- **修复（最小改动 2 文件）**：
  1. milvus_store.py：schema 旧 page/chunk → article(VARCHAR) + pdf_page_start/end + book_page_start/end（与 Chroma 适配器字段完全一致）；灌数 rows 与 search output_fields/返回 metadata 同步为 6 字段；score 契约（1-cosine 伪距离）不变。
  2. scripts/build_milvus_index.py：抽查打印改条文编号/页码双轨。
- **验证（2026-09-19）**：
  - 容器栈（etcd/minio/milvus）由用户启动，AI 复查连接 OK 后重灌 964 条（脚本自动 drop 重建旧 174 条 collection）。
  - 8 查询 top-5 与 FAISS 对比：**40/40 完全重合 + 8/8 排序一致**。
  - 三端回归（Java → Python milvus 版 → Ollama）：症状 5 citations 页码双轨完整且 top 命中与 FAISS/Chroma 版一致；方剂 formula_query + 10 citations 全过。
  - 验收后 .env 切回 chroma 日常状态（milvus 容器栈由用户停止，三后端数据均备好随时可切）。
- **面试回答关键词**：停用适配器技术债的主动回收、契约升级的多适配器同步、三后端一致性验证（同一批查询跨库比对）。

### 16.39 ④评测集指标化（下阶段第 5 项，2026-09-19）

- **交付物**：.deepeval/eval_cases.json（20 条 = 5 类 × 4 条：症状/方剂/常识/越界/重复提问，全部 strict_mode=true）+ scripts/eval_rag.py（真实链路 Java 8080 评测 + 规则判定 + 本地 Ollama LLM judge + Markdown/JSON 报告 + --only/--skip-llm/--compare）+ .deepeval/reports/ 基线报告。
- **为何选这三项指标（选型理由）**：
  1. **工具调用精度**（输入正确性，纯规则判定）：本项目是 Agent 化 RAG（B2），答案质量上限由工具调用决定——该查不查、查错库、越界还查，后续答案必然无据可依。且 intent/citations 结构确定性强，可 100% 规则判定（零 LLM 开销），是最客观的“前置正确性”指标。
  2. **幻觉率**（证据忠实度，规则+LLM）：中医文献问答的可信度核心是“引经据典”，最大风险是系统编造条文/方剂误导用户（医疗安全场景）。规则部分（答案条文编号 ⊆ citations 编号集合）客观可判，LLM 补语义层（虚构方剂/与证据矛盾的论断）。
  3. **任务成功率**（端到端效果，LLM 语义判定为主）：覆盖前两项无法度量的“答案质量”维度——回答是否完整解决用户问题（越界类以正确拒绝为成功、重复类以两轮答案一致为成功）。
  三者关系层层递进：输入正确（工具）→ 证据忠实（无幻觉）→ 结果可用（任务成功）。
- **基线结果（2026-09-19，qwen2.5:7b CPU，全量模式）**：工具调用精度 **20/20（100%）**、幻觉率 **0/12（0%）**、任务成功率 **20/20（100%）**。分类别：症状/方剂/常识/越界/重复全部 4/4。
- **评测发现的链路缺陷与修复**（评测集价值验证）：
  1. guardrail 误拦中医常识问题（“什么是伤寒论”等 4 条判越界）→ llm.py guardrail prompt 增加 5 条中医常识 YES 示例；
  2. guardrail 误拦多轮追问（“刚才说的桂枝汤组成再重复一遍”脱离上下文无法判断领域）→ chat_guardrail 增加 history_hint 参数，nodes.py 传入历史上下文；
  3. 口径对齐：严格模式强制检索（系统设计），常识/重复类 expected_intent 改为允许集（symptom_query/formula_query 均合法）；重复类第二轮可走检索路径，方剂名出现在答案中即算命中。
- **已知限制（记录在案）**：本地 7B judge 稳定性有限（同答案不同轮次可能判 PASS/FAIL，故 prompt 加“宽松判定”条款约束）；多轮场景模型复述历史条文编号（如 9.50 不在本轮 citations）按幻觉口径从严计 1 条，属证据追溯问题，留给后续改进；“中药和西药的区别”类跨领域比较题 guardrail 拦截有合理性（已换“六经辨证”）。
- **回归用法**：prompt/模型变更后重跑 `python scripts/eval_rag.py --compare .deepeval/reports/eval-<基线>.json` 对比三项指标变化。
- **面试回答关键词**：自建评测集五类场景设计、三项指标的选型论证（Agent 前置正确性/证据忠实度/端到端效果）、规则+LLM 混合判定（规则确定性优先、LLM 语义兜底）、评测驱动修复（两处 guardrail 缺陷由评测发现）、本地 judge 局限性与宽松判定约束。

### 16.40 D 轮 JWT 鉴权 + RBAC + 登录功能（阶段三，2026-09-19）

- **背景与目标**：需求书 16.3 预研卡点（“目前 /api/analysis/** 全放行，生产化必经 JwtAuthenticationFilter + OPTIONS 精确放行”）落地。登录从硬编码 admin/admin123 + 假 token 改为查库 + BCrypt + 真 JWT；业务接口全部收口到 authenticated；前端新增登录页/登出/刷新恢复/401 全局处理；RBAC 数据模型落地。
- **交付物（三端 11 处）**：
  - 数据库：users / roles / user_roles 三表（JPA 自动建表）+ DataInitializer 幂等种子（admin / BCrypt(admin123) / ADMIN）。
  - Java：jjwt 0.12.3（api/impl/jackson）+ JwtUtil（HS256，签发参数化 TTL）+ JwtAuthenticationFilter（OncePerRequestFilter，roles 加 ROLE_ 前缀入 SecurityContext）+ SecurityConfig 重写（STATELESS、OPTIONS 精确放行、登录/健康检查 permitAll、其余 authenticated、401/403 返回 JSON、移除 httpBasic/formLogin、@EnableMethodSecurity）+ AuthController 重写（查库 + BCrypt matches，失败统一 401 防用户名枚举）+ LoginResponse(token/username/roles) + SecurityUtil（取当前用户名）。
  - 前端：api.ts 统一 Bearer 头（token 存 localStorage）+ login() + 401 全局回调；page.tsx 登录卡片（含演示账号提示）/ 顶栏用户名+登出 / 刷新恢复登录态（mounted 防 hydration 不一致）。
  - @CrossOrigin 补 allowedHeaders（Authorization/Content-Type/Last-Event-ID）。
- **三处取舍的详细说明（用户 2026-09-19 确认，未实现部分已搭架子）**：
  1. **RBAC 只落数据模型，不建 role 表抽象层**：完整企业级做法是 users/roles/user_roles 三表 + 角色管理接口 + 动态授权，本项做到“三表 + @ManyToMany 关联 + 登录查询带回角色 + JWT 携带 roles + @PreAuthorize(hasRole) 方法级鉴权能力”即止——多角色扩展只需向 roles 表插数据，机制零改动。当前只有 admin 一个用户，建角色管理后台是过度设计。**架子已就绪**：三表实体/仓库/种子/JWT roles claim/过滤器 ROLE_ 前缀/@PreAuthorize 可用。
  2. **数据隔离未启用，但架子已铺好**：analysis_sessions / analysis_records 新增 owner_username 列（可空，旧数据兼容）；写路径（建会话/成功落库/失败落库）已落当前登录用户；仓库预留 findByOwnerUsername 查询；读路径（history/sessions 聚合 SQL）暂不过滤——MVP 单用户无隔离意义，多用户启用时查询叠加 owner 过滤即可，改动只在读路径。
  3. **token 与配套设施简化，预留点齐备**：仅签发 24h access token（无 refresh token）——JwtUtil 签发方法参数化 TTL、application.yml 已留 jwt.refresh-expiration-days、LoginResponse 注释预留 refreshToken 字段，静默续期只需在 login 多签一个；限流保持 IP 维度（RateLimitInterceptor 已抽 buildIpKey/buildUserKey 双 key 设计，按用户限流切换仅一处调用点）；Python 8001 直连无鉴权——config.py 预留 ai_service_api_key（空=关闭）+ main.py 全局 verify_api_key 依赖（配置非空即全接口校验）+ Java AiServiceClient 预留 api-key 头注入，生产两端各配一处即启用。
- **验收（2026-09-19 全过）**：无 token POST /api/analysis 与 GET /sessions → 401 JSON；伪造 token → 401；错误密码 → 401；正确登录 → token(含 roles claim)；带 token sessions → 200；OPTIONS 预检（声明 authorization/content-type/last-event-id）→ 200 + Access-Control-Allow-Headers 完整；带 token 非流式问答（桂枝汤组成）→ 200 + 证据答案；带 token 流式 SSE 正常推送；psql 复查 users/roles/user_roles（admin→ADMIN）与 sessions/records.owner_username=admin 落库正确。**浏览器自动化实测（登录卡片 → 登录 → 流式问答 → 刷新保持 → 登出）复测全过**；首轮实测暴露出两个鉴权接入坑（见下）并已修复复验：流式 49s/157 事件完整结束无 ERR_INCOMPLETE_CHUNKED_ENCODING、刷新登录态保持、登出回登录卡片、流式落库 owner=admin。
- **踩坑 1（Map.of 不支持 null）**：自定义 401/403 JSON 体用 Map.of("data", null) 构造，匿名访问被拒时 AuthenticationEntryPoint 抛 NPE → 500（响应体为 Spring 默认错误 JSON，掩盖了 401 语义）。根因：Map.of 拒绝 null 键值；修复：换 LinkedHashMap 逐项 put。教训：鉴权失败出口是“请求必经路径”，必须真实验证其响应状态码而非只看登录成功路径。
- **踩坑 2（AuthorizationFilter 参与 ASYNC dispatch 致 SSE 连接非正常关闭，本轮最重要）**：SseEmitter 完成时 Tomcat 发起 ASYNC dispatch 重入过滤器链；JwtAuthenticationFilter 是 OncePerRequestFilter 默认跳过该 dispatch → SecurityContext 为空 → AuthorizationFilter（注册了 DispatcherType.ASYNC）拒绝 → 响应已提交后异常 → 连接被粗暴关闭（浏览器 ERR_INCOMPLETE_CHUNKED_ENCODING、curl exitcode 18，回答内容完整但连接未正常终止）。D 轮前全 permitAll 无此问题，收口 authenticated() 后爆发；评测脚本与早期实测只校验内容不校验连接关闭，故长期未暴露。修复：`dispatcherTypeMatchers(DispatcherType.ASYNC).permitAll()`。教训：SSE/WebFlux 长连接接入 Spring Security 后，除内容正确性外必须验证**连接正常关闭**（curl exitcode 应为 0），且 async dispatch 的认证语义与同步请求不同（异步线程无 SecurityContext）。
- **踩坑 3（异步线程 SecurityContext 丢失致 owner 落空）**：流式 done 落库回调在 reactor 异步线程执行，SecurityContextHolder（ThreadLocal）已被 SecurityContextHolderFilter 清空 → SecurityUtil.getCurrentUsername() 返回 null → owner_username 落库为空。修复：请求同步线程捕获 username，经闭包传入异步落库回调（落库方法增加指定属主重载）。教训：无状态 JWT 的认证信息只存活于请求线程，跨线程回调必须显式传递身份参数而非依赖 ThreadLocal。
- **前端小修复**：未登录时页面初始化仍拉取会话历史（必然 401 且控制台报错），effect 增加 auth 依赖——未登录不拉历史。
- **已知边界（记录在案）**：用户数据隔离读路径未启用（见取舍 2）；无 refresh token（token 过期后前端 401 自动回登录页重新登录）；限流仍 IP 维度；ai-service 直连 8001 无鉴权（生产启用预留开关）；users 表无注册接口（用户由种子/迁移创建）。
- **面试回答关键词**：无状态 JWT（HS256 + 过滤器链 + SecurityContext）、OPTIONS 预检精确放行（16.3 预研落地）、401/403 JSON 化（前端统一跳登录）、RBAC 数据模型（三表 + ROLE_ 前缀 + @PreAuthorize）、防用户名枚举（登录失败统一 401）、数据隔离“写路径落 owner、读路径预留”的分阶段策略、安全入口失败路径实测（Map.of null 坑）、SSE 长连接安全接入（ASYNC dispatch 放行 + 异步线程身份显式传递）。

### 16.41 ⑥审计日志与调用指标（阶段三，2026-09-19）

- **背景与目标**：补齐“非 demo”生产化叙事的最后一块——重要操作留痕（谁在何时做了什么、成功与否、耗时多久）与 AI 调用可观测性（接口与模型两层指标）。方案经用户确认后编码：审计落 PostgreSQL，指标进程内聚合不持久化（默认取舍）。
- **交付物（双端 9 处）**：
  - Java 审计四件套：AuditLog 实体（IDENTITY Long 主键，流水表标准做法——区别于业务实体 UUID，查询按 id 倒序）+ AuditLogRepository（findByAction 分页）+ AuditService.record（8 参统一入口：username/action/sessionId/question 截断 200/result/durationMs/ip/detail 截断 500；写入失败只记日志绝不向上抛——审计不能反过来影响业务主流程）+ AuditPageResponse（避免直接序列化 Spring Data Page）+ AuditController GET /api/audit（limit/offset + action 过滤，@PreAuthorize("hasRole('ADMIN')")——D 轮 RBAC 架子的第一次实际使用）。
  - Java 埋点 5 类：LOGIN_SUCCESS / LOGIN_FAIL（AuthController，失败 detail 记真实原因但对外仍统一 401 防枚举）/ ANALYZE / ANALYZE_STREAM / EXPLAIN（AnalysisController，成功记耗时 + intent/citations 摘要，异常记 FAIL + 错误信息）；读接口（history/sessions）不记（避免查询类操作刷库）；埋点直接 try/finally 调 AuditService，不引入 AOP（仅 5 处，切面收益低）。
  - 流式埋点设计：AnalysisStreamService.startStream 增加第五参 errorHandler（上游异常回调，controller 审计 FAIL 埋点）；done 回调包装为 onStreamDone（落库成功记 SUCCESS、解析/落库失败记 FAIL）；username/ip 由请求同步线程捕获传入异步闭包（16.40 踩坑 3 教训直接复用）。
  - Python 指标：app/metrics.py（全局锁保护的进程内聚合：接口层 analyze/analyze_stream/explain 记 total/success/fail/总耗时/最长耗时；LLM 层记 total/fail/总耗时 + 最近 20 次明细 deque）+ GET /metrics 快照接口（uptime + 两层聚合）。
  - Python 埋点 5 处（llm.py）：chat_with_tools / chat_guardrail / chat_final_answer / summarize_history / local_llm_response 各记调用次数/失败/耗时（方案 B 四调用点之外多埋 local_llm_response 覆盖 explain 底层模型调用）。
- **踩坑 1（函数命名不一致致 Python 启动 ImportError）**：metrics.py 函数名与 main.py 导入名不一致（编码后自测用自取名验证通过，但 py_compile 只查语法不查 import 未暴露）→ uvicorn 启动即 ImportError 退出。修复：统一命名。教训：语法检查不能替代导入链路验证——跨模块新增导入必须真实 import 一次（from app.main import app 级别）。
- **验收（2026-09-19 全过）**：无 token /api/audit → 401 JSON；admin token → 200；登录失败/成功 → 2 条审计（LOGIN_FAIL 89ms / LOGIN_SUCCESS 194ms）；非流式问答 → ANALYZE SUCCESS 43925ms（detail intent=formula_query）；选词解释 → EXPLAIN SUCCESS 20700ms；流式问答 → ANALYZE_STREAM SUCCESS 24522ms（curl EXIT 0 连接正常关闭）；越界问题 → ANALYZE SUCCESS（intent=out_of_scope，越界拦截也是正常业务结果）；psql 复查 6 条记录字段完整（username/ip/duration/detail 中文正常）；Python /metrics 计数与明细正确（analyze total=2 含越界、guardrail 3 次、chat_with_tools 4 次、recent 明细逐条记录）。
- **已知边界（记录在案）**：指标进程内聚合、重启清零（与 Java 会话缓冲同生命周期，不持久化）；审计日志不自动清理（MVP 无归档策略）；前端无指标/审计展示页（数据留接口供后续接监控面板）；读接口不审计；/api/audit 仅 ADMIN 可见。
- **面试回答关键词**：审计埋点的“最小集合”设计（重要操作而非全量请求）、审计失败不影响主流程（吞异常降级）、流水表自增主键与业务 UUID 的区分、@PreAuthorize 方法级鉴权首次落地、异步线程审计身份显式传递、进程内指标聚合的 MVP 取舍（何时才值得上 Prometheus）、跨模块导入的运行时验证。

### 16.42 E 轮 Docker Compose 全栈一键启动（阶段三，2026-09-20）

- **背景与目标**：需求书 15.8 阶段八收尾——postgres 容器 compose 管理化迁移 + 三端一键启动编排 + 本地部署文档。调研发现运行中的 guilinguben-postgres 为早期 docker run 创建、挂匿名卷，与 compose 的 named volume 不一致（直接 compose up 会另起容器丢数据），须先迁移；三端日常为开发模式（Java mvn / Python torch_env uvicorn / 前端 npm dev），Ollama 为 Windows 原生进程。
- **编排取舍（用户拍板方案丙）**：方案甲三端全容器化（真·一键、环境可复制，但 torch 镜像数 GB、构建慢、迭代需重建、内存压力大——有 milvus 停用前科）；方案乙启动脚本（compose 管中间件 + 脚本管三端，迭代快、内存可控，依赖宿主机环境）；**方案丙 = 乙为主体 + 三端 Dockerfile 可选资产**（面试展示用，默认注释不启用）→ 用户选丙。
- **交付物（8 处，三端业务代码零改动）**：
  - docker-compose.yml：postgres/redis 加 healthcheck（pg_isready / redis-cli ping）；rabbitmq profiles ["mq"]；milvus 栈 4 服务 profiles ["milvus"]（默认不拉起，恢复命令加 --profile milvus）；末尾三端容器化注释块（SPRING_DATASOURCE_URL / SPRING_DATA_REDIS_HOST / AI_SERVICE_BASEURL 指向 host.docker.internal + extra_hosts host-gateway + ai-service 根路径挂载 + ENV 覆盖）；顺手移除过时 version 字段（compose config 警告）。
  - scripts/start-all.sh：只读前置检查（docker ps 探测中间件容器——未就绪仅提示并退出，不自行拉起，容器生命周期归用户；Ollama /api/tags）→ 顺序后台启动三端（mvn spring-boot:run / activate torch_env + uvicorn（先 cd services/ai-service：pydantic-settings 按工作目录读 .env）/ npm run dev，日志 + PID 落 logs/）→ wait_http 就绪等待 + already_up 幂等跳过 → 三端健康汇总。
  - scripts/stop-all.sh：读 logs/*.pid → taskkill //F //T 树杀（连带 mvn/npm 包装进程的 java/node 子进程）→ kill -9 兜底（覆盖 MSYS 伪 PID）→ 端口 8080/8001/3000 残留扫描兜底；只停应用不动容器。
  - 三端 Dockerfile + .dockerignore（可选资产）：java-backend maven 多阶段（pom 先行依赖层缓存）→ temurin JRE；ai-service（构建上下文为项目根；容器内 BASE_DIR=parents[3]=/，挂载 ./models:/models ./data:/data ./guilinguben.pdf:/guilinguben.pdf；ENV 覆盖本机 .env 的 Windows 绝对路径——环境变量优先级高于 .env）；frontend node 三阶段 + next start（无 standalone 需拷 node_modules）。
  - docs/DEPLOY.md：架构总览 / 环境要求 / 首次初始化 / 日常操作 / 验证清单 / profiles 扩展 / 容器化说明 / FAQ。
- **静态验证（2026-09-20 全过）**：bash -n 两脚本语法通过；docker compose config 渲染通过且 profiles 生效（默认仅 postgres+redis；--profile mq 增 rabbitmq；--profile milvus 增 4 服务）。
- **预防性设计（非实际踩坑）**：git bash 中 mvn/npm 的 $! 可能是 MSYS 伪 PID，taskkill 需 Windows PID → stop-all.sh 三层兜底（taskkill 树杀 → kill -9 → 端口扫描）；env_file 按启动工作目录解析 → start-all.sh 必须先 cd services/ai-service；容器内无 .env → Dockerfile ENV 覆盖路径。
- **验收（待用户执行，5 条）**：①postgres 迁移（pg_dump → rm -f → compose up -d postgres → psql 恢复）后三表行数与基线一致；②docker compose up -d 仅拉起 postgres+redis；③start-all.sh 一键三端就绪 → 登录 + 流式问答 + /metrics 计数增加；④stop-all.sh 停三端、容器仍在运行；⑤按 docs/DEPLOY.md 独立走一遍可复现。
- **面试回答关键词**：compose profiles 按需启用中间件（内存受限场景避免无谓占用）、healthcheck 驱动编排依赖（service_healthy）、启动脚本幂等设计、Windows 进程树杀（taskkill /T 连带 mvn/npm 子进程）、容器化路径语义适配（parents[3] 根挂载 + ENV 覆盖 .env）、host.docker.internal 宿主机访问。

### 16.43 postgres 迁移后 Java 密码认证失败排查（E 轮验收，2026-09-20）

- **背景与现象**：E 轮验收③ start-all.sh 启动 Java 时 HikariCP fail-fast 报 FATAL: password authentication failed for user "guilinguben"，mvn 构建失败退出。
- **排查三层（由浅入深）**：①字面对比：application.yml 与 compose 的 POSTGRES_PASSWORD 均为 123，排除配置不一致；②容器内测试陷阱：psql 用 123 连容器 localhost:5432 成功 ≠ 密码正确——官方镜像 pg_hba 对 127.0.0.1/32 为 trust 不验密码，用错误密码实测照样通过（trust bypass）坐实假象；③决定性测试：用容器自身 IP（172.18.0.2）连接走 host all all all scram-sha-256 真认证 → 123 失败 → 容器真实密码 ≠ 123。
- **根因**：迁移后容器挂载的命名卷 guilinguben_postgres_data 是更早某次初始化留下的（内含旧密码），compose 的 POSTGRES_PASSWORD 只在空卷首次 initdb 时生效、对已有卷静默忽略 → 密码漂移；旧 docker run 容器（匿名卷，密码 123）换卷后暴露不一致。
- **修复（用户执行 ALTER，两条链路已验证全过）**：ALTER USER guilinguben WITH PASSWORD '123'（容器内 trust 通道重置）→ 与 Java 配置、compose 定义三方对齐；验证：容器 IP scram + 123 → SELECT 1 通过；临时容器经 host.docker.internal（宿主机映射路径，即 Java 的 127.0.0.1 链路）→ SELECT 1 通过。将来即使销毁卷重建，POSTGRES_PASSWORD=123 也会生效，不再漂移。
- **附加卡点（JDBC URL 加固，建议保留）**：application.yml 的 url 从 localhost 改为 127.0.0.1（加注释说明）。Windows 上 JVM 解析 localhost 优先 IPv6 ::1，而 ::1:5432 被 wslrelay（WSL 转发）监听、0.0.0.0:5432 由 com.docker.backend（Docker 映射）监听——强制 IPv4 直达 Docker 映射，绕开 ::1 多一跳与潜在 WSL 服务冲突。
- **剩余验证（待用户重启 Java）**：start-all.sh 启动 Java 无 FATAL、/actuator/health UP → E 轮验收③继续。
- **面试回答关键词**：pg_hba trust 假象（容器内 localhost 免密测试不能验证密码，必须用非 loopback 地址做真认证）、postgres 镜像初始化语义（POSTGRES_PASSWORD 仅空卷首次 initdb 生效）、卷迁移密码漂移与 ALTER USER 三方对齐、Windows localhost 双栈解析（::1 优先）与 wslrelay/com.docker.backend 端口拓扑、127.0.0.1 强制 IPv4 的确定性。

### 16.44 ai-service 启动失败：Windows 下 Python 重定向 stdout 的 GBK 编码（E 轮验收，2026-09-20）

- **背景与现象**：E 轮验收③ start-all.sh 启动 ai-service 失败——logs/ai-service.log 报 UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'（main.py 第 89 行 print 的 ✓），lifespan 启动中断退出；日志前半段中文呈乱码。
- **根因**：start-all.sh 将 uvicorn stdout 重定向到文件（> logs/ai-service.log 2>&1）后，Python 检测 stdout 非终端，Windows 上默认改用 locale 编码（GBK/cp936）写文件；业务 print 中的 ✓（U+2713）不在 GBK 字符集 → UnicodeEncodeError；中文虽在 GBK 内但文件按 UTF-8 读取显示乱码。此前 AI 手动在终端启动未触发（终端编码环境不同）。
- **修复（编排层，业务代码零改动）**：start-all.sh 的 ai-service 启动命令前置 PYTHONIOENCODING=utf-8（Python 官方标准变量，强制 stdout/stderr 使用 UTF-8）——一处修复覆盖 main.py 全部 print（含 3 处 ✓）与未来新增字符；bash -n 验证通过。
- **验收（待用户重跑 start-all.sh）**：ai-service 启动成功、/health 200、logs/ai-service.log 中文与 ✓ 无乱码无报错 → E 轮验收③继续。
- **面试回答关键词**：Windows 控制台与文件重定向的编码差异（stdout 非终端时 Python 用 locale 编码）、PYTHONIOENCODING 标准解法、UnicodeEncodeError 与 GBK 字符集边界（✓ 不在 GBK）、启动脚本重定向日志的编码工程细节。

### 16.45 stop-all.sh 停止失效：PID 文件缺失跳过 + kill -9 孤儿误报（E 轮验收，2026-09-20）

- **背景与现象**：E 轮验收④执行 stop-all.sh 提示“三端已停止”，但复测发现 8080（java.exe）与 3000（node.exe）仍在监听——Java 与前端进程残留，仅 ai-service 真正停止。
- **根因（两个缺陷叠加）**：①stop_by_pidfile 在 PID 文件不存在时直接“跳过”返回——前端因 start-all.sh 的 already_up 幂等跳过而未写 frontend.pid，非本脚本启动的进程完全漏杀；②kill -9 对 MSYS 伪 PID 只杀 mvn/npm 的 MSYS 包装进程（cmd/bash 中间层），Windows 侧的 java/node 子进程成为孤儿继续监听，而 stop_pid 返回成功 → 端口兜底分支不执行 → 误报“已停止”。
- **修复（stop-all.sh 重构 stop_endpoint）**：停止逻辑以“端口释放”为最终判据——①有 PID 文件则优先 taskkill //F //T 树杀 + kill -9 兜底（无论成败）；②无条件按监听端口 8080/8001/3000 扫描残留（netstat 取 Windows PID）并树杀；③端口无监听时明确输出“已释放”。bash -n 通过。
- **验收（待用户重跑）**：当前残留 java 20172 / node 22496 由修复版 stop-all.sh 重跑一次清理；三端端口全部释放、容器 postgres/redis 仍在运行。
- **面试回答关键词**：停止脚本以“端口释放”而非“命令返回值”为最终判据、MSYS 伪 PID 与 Windows PID 的双层进程树语义（kill 只杀包装进程、java/node 孤儿化）、taskkill /T 树杀兜底、幂等启动（already_up）与停止（无 PID 文件靠端口扫描）的闭环设计。

### 16.46 java.log 中文乱码：JVM 默认编码 GBK 写文件（E 轮验收，2026-09-20）

- **背景与现象**：E 轮验收③后检查 logs/java.log，中文日志呈乱码（[□□ʽ] □յ□□□ʽ…），服务功能正常；16.44 修复 Python 后 Java 侧同类问题暴露。
- **根因**：java-backend 无 logback 自定义配置，Spring Boot 默认 ConsoleAppender 用平台默认编码（Windows 中文 locale = GBK/cp936）；start-all.sh 将 mvn 输出重定向到文件后，应用日志以 GBK 字节写入、按 UTF-8 读取即乱码。终端交互式运行不乱（控制台同为 GBK）。
- **修复（编排层，业务代码零改动）**：start-all.sh 的 mvn 启动命令追加 -Dspring-boot.run.jvmArguments=-Dfile.encoding=UTF-8（Spring Boot Maven 插件官方传参给 fork JVM），应用 JVM 默认编码改为 UTF-8，日志落盘即 UTF-8；与 16.44 合并后 Windows 三端日志统一 UTF-8。
- **验收（2026-09-20 通过）**：用户重跑 start-all.sh 后 logs/java.log 中文正常无乱码。
- **面试回答关键词**：logback ConsoleAppender 的平台默认编码语义、JVM file.encoding 与终端/重定向的编码一致性、spring-boot.run.jvmArguments 传参、Windows 三端日志统一 UTF-8 的工程实践。

## 17. 面试可直接复述的总结

这项目的核心价值不在于"堆了多少中间件"，而在于把真实医学文献知识管理、AI 任务编排和权限边界做成了一个可验证闭环。我做的事情可以概括为：

1. 先把 Java 业务层和 Python AI 层连接起来；
2. 再用真实 PDF 作为知识源；
3. 再把 RAG 的 Embedding、向量库、检索和 LLM 生成接上；
4. 最后保留扩展接口，方便未来切换 Milvus、接入 RabbitMQ、增加鉴权和审计。

最大的难点不是"做出一个能跑的 demo"，而是把"真实环境、真实数据、真实需求、真实工程约束"四者同时放进去，并在组件不稳定时仍然保留可演进的架构边界。这个过程里，最重要的不是一次性做完，而是把每一个关键卡点都拆出来、定位根因、确认修复路径，并把它们写进项目需求书和迭代顺序里。

**关键技术决策**：
- 本地 Ollama + Qwen 是默认模型运行方式，产品打包必须保留本地模型部署路径。
- Streamlit 保留为早期演示入口，生产业务入口以 Java API 为准。
- 不把"能生成回答"视为产品完成，必须同时具备引用、风险提示、审计和失败处理。
- **性能优化策略**：先解决核心瓶颈（Embedding 模型重复加载、索引重建），再考虑架构升级（Milvus）。
- **技术选型原则**：MVP 阶段用简单方案（FAISS），生产阶段再引入复杂中间件（Milvus），避免过早优化。
- **市场对照（2026-09-17 岗位纠偏）**：项目技术路线（Python/LangGraph Agent/RAG/Tool Calling + Java 后端）与深圳大模型应用岗高频技能一致；纠偏后 Milvus、评测集、Redis、审计日志列入近期查缺补漏，详见 15.11 与 16.26-16.29。
