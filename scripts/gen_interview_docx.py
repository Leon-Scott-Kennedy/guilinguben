# -*- coding: utf-8 -*-
"""生成面试技术文档 Word（桂林古本智能辅助诊疗平台）。

运行：python scripts/gen_interview_docx.py
输出：docs/桂林古本智能辅助诊疗平台_技术面试文档.docx
内容来源：docs/PROJECT_REQUIREMENTS.md（需求书）、实际代码与 E 轮验收记录。
图表表达：表格 + 文本块图（Word 原生渲染，用户确认的方案）。
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = r"docs/桂林古本智能辅助诊疗平台_技术面试文档.docx"
BODY_FONT = "微软雅黑"
CODE_FONT = "Consolas"

doc = Document()
# 页边距
for sec in doc.sections:
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)


def _ea(run, name):
    """设置东亚字体（Word 中文字体必须同时设 ascii 与 eastAsia）。"""
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


def style_run(run, name=BODY_FONT, size=None, bold=None, color=None):
    run.font.name = name
    _ea(run, name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    return run


def h1(text):
    pgh = doc.add_heading(level=1)
    run = pgh.add_run(text)
    style_run(run, size=18, bold=True, color=(0x1F, 0x3B, 0x63))
    return pgh


def h2(text):
    pgh = doc.add_heading(level=2)
    run = pgh.add_run(text)
    style_run(run, size=15, bold=True, color=(0x2E, 0x5A, 0x8F))
    return pgh


def h3(text):
    pgh = doc.add_heading(level=3)
    run = pgh.add_run(text)
    style_run(run, size=13, bold=True, color=(0x33, 0x33, 0x33))
    return pgh


def p(text, bold=False, size=10.5):
    pgh = doc.add_paragraph()
    run = pgh.add_run(text)
    style_run(run, size=size, bold=bold)
    return pgh


def bullet(text, level=0):
    pgh = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    run = pgh.add_run(text)
    style_run(run, size=10.5)
    return pgh


def code(text):
    """等宽字体代码块（文本图/命令）。"""
    for line in text.split("\n"):
        pgh = doc.add_paragraph()
        pgh.paragraph_format.space_after = Pt(0)
        run = pgh.add_run(line if line else " ")
        style_run(run, name=CODE_FONT, size=9)
        run.font.name = CODE_FONT
        # 浅灰底纹
        pPr = pgh._element.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "F2F2F2")
        pPr.append(shd)


def table(headers, rows, col_widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(htext)
        style_run(run, size=9.5, bold=True)
        # 表头底纹
        tcPr = hdr[i]._element.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "D9E2F3")
        tcPr.append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, cell_text in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(cell_text))
            style_run(run, size=9)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    return t


# ==================== 封面 ====================
for _ in range(5):
    doc.add_paragraph()
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(title.add_run("桂林古本智能辅助诊疗平台"), size=26, bold=True, color=(0x1F, 0x3B, 0x63))
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(sub.add_run("产品与技术面试文档"), size=18, bold=True, color=(0x2E, 0x5A, 0x8F))
doc.add_paragraph()
info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(info.add_run(
    "技术栈：Java 17 + Spring Boot 3.3 ｜ Python + FastAPI + LangGraph ｜ Next.js 15\n"
    "中间件：PostgreSQL 16 · Redis 7 · Chroma/FAISS/Milvus · Ollama + Qwen2.5\n"
    "文档版本：1.0 ｜ 生成日期：2026-09-22 ｜ 用途：面试准备与项目讲解"),
    size=10.5, color=(0x55, 0x55, 0x55))
doc.add_page_break()

# ==================== 目录 ====================
h1("目录")
toc = [
    ("1", "产品背景与定位"),
    ("2", "技术选型"),
    ("3", "系统总体架构"),
    ("4", "核心功能模块"),
    ("5", "数据库设计"),
    ("6", "接口文档"),
    ("7", "核心时序图"),
    ("8", "功能流转图"),
    ("9", "UML 结构图"),
    ("10", "关键工程实践"),
    ("11", "踩坑与解决方案精选"),
    ("12", "部署与运维"),
    ("13", "后续规划与未完成工作"),
    ("14", "面试高频问答准备"),
]
for num, name in toc:
    pgh = doc.add_paragraph()
    style_run(pgh.add_run(f"{num}. {name}"), size=12, bold=True)
doc.add_page_break()

# ==================== 1. 产品背景与定位 ====================
h1("1. 产品背景与定位")

h2("1.1 要解决的问题")
bullet("中医经典文献（《桂林古本伤寒杂病论》）检索难：条文分散、古文理解门槛高、症状与条文对应关系隐晦。")
bullet("AI 回答缺乏证据溯源：通用 LLM 会“编造条文”，需要把回答约束在真实文献证据上。")
bullet("知识安全边界：医学场景必须区分“辅助研究”与“自动诊断”，越界请求要有围栏拦截与免责声明。")

h2("1.2 产品定位")
p("系统定位是“辅助研究与辅助决策工具”——不是自动诊断、处方或替代专业医师。所有结果保留知识来源、"
  "免责声明与人工复核边界。核心链路：用户 → Java 业务后端（唯一对外入口）→ Python AI 服务（Agent）"
  "→ RAG/LLM/工具 → PostgreSQL 持久化。")

h2("1.3 用户与角色")
table(
    ["角色", "核心能力"],
    [
        ["普通用户", "登录、智能问答（严格/自由模式）、PDF 选词解释、会话历史"],
        ["研究人员/专家", "审核疑难病案、标注 AI 回答质量（RLHF 反馈）、知识库版本管理"],
        ["管理员", "用户/角色/权限管理、审计日志与调用日志、模型参数与安全策略配置"],
    ],
    col_widths=[4, 12],
)

h2("1.4 MVP 已实现 vs 产品愿景")
p("MVP 已完成（对应需求书 2.1 七条目标）：登录鉴权、症状/文献问答、Java↔Python 调用、意图识别 + "
  "RAG + 安全围栏、结构化回答（引用/置信/风险/requestId）、会话与审计持久化、健康检查。", bold=True)
p("产品愿景（规划中）：多端客户端（PC/安卓/iOS）、会员分级功能、病案录入→向量化入库→用户自主公开"
  "→被他人检索（来源标注）→授权作为训练数据参与模型迭代、高并发分布式架构、多 Agent 协作模式。"
  "当前系统是 Web MVP + 本地部署形态，愿景对应需求书 2.2 后续目标与阶段五规划。")
doc.add_page_break()

# ==================== 2. 技术选型 ====================
h1("2. 技术选型")

h2("2.1 选型总览")
table(
    ["层", "选型", "版本/说明", "选型理由"],
    [
        ["业务后端", "Java 17 + Spring Boot", "3.3.x + Maven", "稳定业务边界、数据一致性、生态成熟（岗位要求 Java）"],
        ["AI 服务", "Python + FastAPI", "3.13（torch_env）", "AI 生态最丰富；FastAPI 异步原生、自动 OpenAPI"],
        ["Agent 框架", "LangGraph", "状态机图 + 检查点", "可控的图编排 + 持久化检查点，比 LangChain 单链更可演进"],
        ["LLM", "Ollama + Qwen2.5:7b", "本地部署", "本地可复现、无 API 成本；保留模型可替换边界"],
        ["Embedding", "BGE-large-zh-v1.5", "本地加载，1024 维", "中文语义最优的开源模型之一，本地离线可用"],
        ["向量库", "Chroma（当前）", "嵌入式持久化", "协议适配器三选一可切换：FAISS→Chroma→Milvus"],
        ["前端", "Next.js 15 + TS", "react-pdf", "SSR 成熟、生态大；react-pdf 内嵌古籍阅读器"],
        ["数据库", "PostgreSQL 16", "compose + healthcheck", "jsonb 存 citations、事务一致性、RBAC 数据模型"],
        ["缓存", "Redis 7", "spring-data-redis", "会话历史缓存 + 接口限流"],
        ["鉴权", "JWT（jjwt HS256）+ BCrypt", "Spring Security", "无状态认证；密码散列不可逆"],
        ["评测", "自建评测集 + Ollama judge", "20 条基线", "规则 + 本地 LLM 双评判，无需外部 API"],
    ],
    col_widths=[2.2, 3.6, 3.2, 7],
)

h2("2.2 关键选型对比（面试常问）")
h3("2.2.1 向量数据库三选一")
table(
    ["维度", "FAISS", "Chroma（当前默认）", "Milvus 2.4（可切换）"],
    [
        ["定位", "库而非数据库，MVP 快速验证", "嵌入式持久化向量库", "分布式生产级向量数据库"],
        ["部署", "进程内，零依赖", "进程内，本地持久化文件", "独立容器栈（etcd/minio/milvus）"],
        ["适用", "单机小数据量、跑通 RAG 链路", "单机中量数据、工程期持久化", "生产多实例、海量向量"],
        ["本项目", "第一版适配器（已实现）", "C 轮后切换（964 条文灌入，top-5 与 FAISS 40/40 重合）", "适配器已实现并验收（top-5 与 FAISS 完全重合），因本机内存切回"],
    ],
    col_widths=[2.2, 3.6, 4.2, 6],
)
p("选型原则：业务代码只依赖统一协议 ports.py（build_index / similarity_search / "
  "similarity_search_with_score / as_retriever），切换向量库只换适配器 + .env 配置，"
  "Agent/API/Java/前端零改动——用适配器模式把“选型”变成“配置”。")

h3("2.2.2 会话检查点存储三选一")
table(
    ["方案", "MemorySaver", "SqliteSaver（已选）", "PostgresSaver"],
    [
        ["持久化", "仅内存，重启丢失", "本地文件 data/checkpoints.sqlite", "入库，与业务库同源"],
        ["线程安全", "弱（需锁）", "check_same_thread=False + 内部锁", "数据库事务保证"],
        ["适用", "演示/单进程原型", "单机服务、重启可恢复", "多实例共享、生产级"],
        ["选择理由", "—", "单机 MVP 下代价最低且满足“重启持久化”验收断言；升级 PostgresSaver 仅改一行连接配置", "—"],
    ],
    col_widths=[2.2, 3.4, 5.4, 5],
)

h2("2.3 岗位市场对照（选型纠偏依据）")
p("归纳 14 份深圳大模型应用/Agent 岗招聘（2026-09）技能频次：Python 13、Agent 应用开发 13、"
  "RAG 12、大模型 API 集成 12、LangChain 系 10、Tool Calling/MCP 7、Prompt Engineering 7、"
  "Redis 7、Java 7、FastAPI/Flask 7、向量数据库 6、Docker/CI-CD 5、评测体系 3。"
  "据此把 Milvus 接线、Redis 缓存限流、评测集指标化、审计日志四项从阶段五提前执行——"
  "项目技术路线与市场高频考点完全一致。")
doc.add_page_break()

# ==================== 3. 系统总体架构 ====================
h1("3. 系统总体架构")

h2("3.1 总体架构图")
code(
"┌─────────────┐   HTTP/SSE   ┌──────────────────┐   HTTP   ┌─────────────────────┐\n"
"│  Next.js 前端 │ ───────────→ │  Java 业务后端     │ ───────→ │  Python AI 服务      │\n"
"│  3000 端口    │ ←─────────── │  8080 端口         │ ←─────── │  8001 端口            │\n"
"└─────────────┘              │ （唯一对外入口）     │          │  LangGraph Agent     │\n"
"        │                    └──────┬───────────┘          └─────────┬───────────┘\n"
"        │ PDF 渲染                    │ JPA 持久化 / 缓存 / 限流       │ 向量检索 / LLM / 工具\n"
"        ▼                             ▼                              ▼\n"
"  ┌──────────┐        ┌───────────────┬───────────────┐      ┌──────────────┐\n"
"  │ react-pdf │        │ PostgreSQL 16 │   Redis 7     │      │ Chroma 向量库 │  Ollama\n"
"  │ 古籍原文   │        │ （用户/会话/审计）│ （缓存/限流）   │      │ （964 条文向量） │  Qwen2.5:7b\n"
"  └──────────┘        └───────────────┴───────────────┘      └──────────────┘\n"
"                            ▲ docker compose 统一编排（healthcheck + profiles）"
)

h2("3.2 三端职责边界")
table(
    ["端", "职责", "不做什么"],
    [
        ["Java 业务后端", "认证鉴权、会话/审计持久化、AI 调用编排（超时/重试/降级）、SSE 转发与缓冲、限流、对外 REST 唯一入口", "不做模型推理、不做向量检索"],
        ["Python AI 服务", "意图识别、RAG 检索、LangGraph Agent 循环、工具调用、安全围栏、结构化输出", "不直接认证用户、不直接改业务库"],
        ["前端", "聊天式消息 UI、SSE 打字机渲染、PDF 阅读器与选词解释、会话列表", "不保存业务数据、不做推理"],
    ],
    col_widths=[3, 9.5, 3.5],
)

h2("3.3 关键架构决策")
bullet("Java 是唯一对外入口：Python 不直接暴露给浏览器，跨域、认证、审计在 Java 统一收口。")
bullet("向量库适配器模式：ports.py 协议 + 三实现（FAISS/Chroma/Milvus），.env 开关切换。")
bullet("LangGraph 状态机：guardrail → agent ⇄ tools（MAX_ITERATIONS=3）→ final_answer，"
       "检查点按 thread_id=session_id 持久化（SqliteSaver）。")
bullet("SSE 三端链路：Python 逐 token 发射 → Java WebFlux WebClient 消费 + SseEmitter 转发 + "
       "每会话缓冲 → 前端 fetch 手动解析打字机渲染；断连恢复见第 7 章。")
bullet("部署编排（方案丙）：Docker Compose 管中间件（healthcheck + profiles），"
       "scripts/start-all.sh / stop-all.sh 管三端应用（幂等启动、以端口释放为停止判据）。")

h2("3.4 数据流（一次流式问答）")
code(
"浏览器(fetch SSE) → Java /api/analysis/stream → Python /api/agent/analyze/stream(stream:true)\n"
"  → LangGraph: guardrail(围栏) → agent(LLM 决策) ⇄ tools(向量检索/方剂查询) → final_answer\n"
"  → Ollama 逐 token → Python SSE 事件(event_id 自增) → Java SseEmitter 转发 + 每会话缓冲\n"
"  → 前端打字机渲染 → done 事件 → Java 落库(analysis_sessions/records) + 审计埋点"
)
doc.add_page_break()

# ==================== 4. 核心功能模块 ====================
h1("4. 核心功能模块")

h2("4.1 智能问答 Agent（LangGraph 状态机）")
bullet("意图识别：症状查询（触发 RAG）／追问（携带历史上下文）／越界（围栏拦截）。")
bullet("严格模式：强制基于检索证据回答，无证据说明不确定性；代码层兜底——未调工具直接丢弃回答并强制注入检索。")
bullet("自由模式：通用 LLM 聊天 + 免责声明；弱兜底——无证据且含条文编号时追加警示。")
bullet("双层安全围栏：关键词快路径（毫秒级硬拦截）+ LLM few-shot 越界判定（fail-open 不阻断可用性）。")
bullet("循环截断：final_answer 节点基于已有证据强制生成回答，工具异常不中断循环。")

h2("4.2 方剂检索（结构化工具调用）")
bullet("lookup_formula 工具：方剂库 446 条（页码/方剂名/药物组成/注意事项），zhconv 繁简全量转换解决繁简不匹配。")
bullet("结构化引用：工具结果与检索证据同构（document_id 前缀 formula_db:），统一计入 citations，纯方剂问题 intent=formula_query。")

h2("4.3 PDF 选词解释")
bullet("内嵌 react-pdf 阅读器：964 条文“一个编号一条数据”切分，页码双轨四端贯通（PDF/向量库/引用/前端跳转）。")
bullet("选词解释：用户光标选中古籍片段 → Java /api/explain → Python LLM 生成白话文解释。")
bullet("双向联动：点击 AI 回答引用卡片，PDF 自动跳转对应页码。")

h2("4.4 会话管理")
bullet("浏览器内固定 sessionId（localStorage 持久化），同一标签页多轮对话共享会话。")
bullet("多轮记忆：最近 5 条历史注入 → 滑动窗口摘要化（最近 1 轮原文 + 更早轮次 LLM 要点摘要 + 增量缓存）。")
bullet("侧栏会话列表：聚合 SQL 出首问标题/轮数/更新时间；历史加载失败静默降级不阻塞提问。")

h2("4.5 登录鉴权与 RBAC")
bullet("JWT（HS256）+ BCrypt；Spring Security 过滤器链收口 authenticated；401/403 统一 JSON。")
bullet("RBAC 三表：users / roles / user_roles（ManyToMany），管理接口 @PreAuthorize(\"hasRole('ADMIN')\")。")

h2("4.6 审计与调用指标")
bullet("audit_logs 表 + 5 类动作埋点：登录/问答/流式/解释；记录 username/action/durationMs/ip/result。")
bullet("GET /api/audit 管理员专属；Python /metrics 双层指标（全局计数 + 明细），Actuator 预留 Prometheus。")

h2("4.7 接口限流")
bullet("固定窗口 INCR：30 次/分钟/IP，超限 429；Redis 故障四层 fail-open 降级（不影响主流程可用性）。")

h2("4.8 评测体系")
bullet("自建 20 条评测集（症状/方剂/常识/越界/重复提问各 4 条）+ scripts/eval_rag.py。")
bullet("三指标基线：工具调用精度 20/20、幻觉率 0/12、任务成功率 20/20；评测驱动修复 guardrail 两处误拦。")
doc.add_page_break()

# ==================== 5. 数据库设计 ====================
h1("5. 数据库设计")

h2("5.1 ER 关系")
code(
"users (1) ──── (N) user_roles (N) ──── (1) roles          ←  RBAC 三表\n"
"users (1) ──── (N) analysis_sessions（ownerUsername 记录属主）\n"
"analysis_sessions (1) ──── (N) analysis_records（sessionId 关联）\n"
"audit_logs（独立审计表，记录所有关键动作，不参与业务外键）"
)

h2("5.2 表结构")
h3("users（用户）")
table(["字段", "类型", "说明"], [
    ["id", "String (UUID)", "主键"],
    ["username", "String unique", "登录名"],
    ["passwordHash", "String", "BCrypt 散列，绝不明文"],
    ["roles", "Set<Role>", "ManyToMany → user_roles 中间表"],
    ["createdAt", "Instant", "创建时间"],
], col_widths=[3, 4, 9])
h3("roles / user_roles（角色）")
table(["字段", "类型", "说明"], [
    ["roles.id / name / description", "String", "name 唯一（USER/ADMIN）"],
    ["user_roles", "关联表", "users 与 roles 的 ManyToMany 中间表"],
], col_widths=[5, 3, 8])
h3("analysis_sessions（分析会话）")
table(["字段", "类型", "说明"], [
    ["id", "String (UUID)", "主键"],
    ["sessionId", "String", "业务会话 ID（前端生成，与 Python thread_id 对齐）"],
    ["ownerUsername", "String", "属主（数据隔离 owner 写路径）"],
    ["createdAt", "Instant", "创建时间"],
], col_widths=[3, 4, 9])
h3("analysis_records（分析记录）")
table(["字段", "类型", "说明"], [
    ["id", "String (UUID)", "主键"],
    ["sessionId", "String", "所属会话（业务字段关联，非主键）"],
    ["question / answer", "TEXT", "用户问题 / AI 回答"],
    ["citations", "String(JSON)", "引用证据 JSON 字符串，读取时反序列化并解析失败兜底"],
    ["ownerUsername", "String", "属主"],
    ["createdAt", "Instant", "创建时间"],
], col_widths=[3, 4, 9])
h3("audit_logs（审计日志）")
table(["字段", "类型", "说明"], [
    ["id", "Long", "自增主键"],
    ["username / action", "String", "操作人 / 动作类型（登录/问答/流式/解释）"],
    ["sessionId / question", "String", "会话 ID / 问题摘要（截断 200 字符）"],
    ["result / durationMs / ip", "—", "结果（success/error）/ 耗时 / 来源 IP"],
    ["detail", "String(500)", "补充信息"],
    ["createdAt", "Instant", "审计时间"],
], col_widths=[4.5, 3.5, 8])

h2("5.3 关键设计点")
bullet("数据隔离：记录带 ownerUsername，查询按属主过滤（数据隔离 owner 写路径，D 轮三取舍之一）。")
bullet("citations 用 jsonb/JSON 字符串：结构化引用随记录持久化，历史接口反序列化时解析失败兜底为空列表。")
bullet("时区治理：PostgreSQL 时区强制 Asia/Shanghai（ALTER DATABASE + compose TZ/-c timezone 双保险），杜绝 8 小时偏差。")
bullet("Python 侧检查点：SqliteSaver → data/checkpoints.sqlite，thread_id=session_id，与业务库职责分离。")
doc.add_page_break()

# ==================== 6. 接口文档 ====================
h1("6. 接口文档")

h2("6.1 Java 对外接口（唯一入口，/api 前缀）")
table(
    ["方法", "路径", "鉴权", "说明"],
    [
        ["GET", "/api/health", "公开", "健康检查"],
        ["POST", "/api/auth/login", "公开", "登录：{username, password} → {token, username, roles}；BCrypt 校验 + JWT 签发"],
        ["POST", "/api/analysis", "JWT", "非流式问答：{sessionId, question, strictMode} + historyContext → 结构化回答"],
        ["POST", "/api/analysis/stream", "JWT", "流式问答（SSE）：同请求体，逐事件转发；支持 Last-Event-ID 断点续发"],
        ["GET", "/api/analysis/history", "JWT", "会话历史（分页 limit/offset + total/hasMore，倒序取页反转升序）"],
        ["GET", "/api/analysis/sessions", "JWT", "侧栏会话列表（首问标题/轮数/更新时间聚合）"],
        ["POST", "/api/explain", "JWT", "PDF 选词解释：选中文本 + 上下文 → 白话文解释"],
        ["GET", "/api/audit", "JWT + ADMIN", "审计日志查询（@PreAuthorize hasRole('ADMIN')）"],
    ],
    col_widths=[1.6, 4.6, 2.6, 7.2],
)

h2("6.2 Python 内部接口（Java 直连，不对浏览器）")
table(
    ["方法", "路径", "说明"],
    [
        ["GET", "/health", "健康检查"],
        ["GET", "/metrics", "进程内双层指标（全局计数 + 明细，重启清零）"],
        ["POST", "/api/agent/analyze", "非流式分析：Agent 图 invoke，返回 answer/intent/citations/warnings/status/requestId"],
        ["POST", "/api/agent/analyze/stream", "流式分析：stream:true，Ollama 逐 token + ContextVar 事件发射 + 有界队列丢弃防内存膨胀"],
        ["POST", "/api/agent/explain", "选词解释：LLM 生成白话释义/辨证分析"],
    ],
    col_widths=[1.8, 5.2, 9],
)

h2("6.3 核心数据结构")
code(
"AnalyzeRequest   : { sessionId, question, strictMode, historyContext[] }\n"
"AnalyzeResponse  : { answer, intent(symptom_query/formula_query/out_of_scope/chat/error),\n"
"                     citations[{document_id, title, content, score, page}],\n"
"                     warnings[], status(success/fallback/out_of_scope/error), requestId }\n"
"SSE 事件流        : data:{type: token/done/error, event_id(自增), content, citations...}\n"
"                  事件带 Last-Event-ID 协议头语义，用于断点续发（详见第 7 章）"
)

h2("6.4 错误码与调用约束")
table(
    ["场景", "约定"],
    [
        ["401/403", "未认证/无权限 → 统一 JSON 错误体（SecurityConfig 收口）"],
        ["429", "限流超限（30 次/分钟/IP，固定窗口）"],
        ["503", "AI 服务不可用 → 前端维护页面；Java 侧统一业务错误码转换"],
        ["调用约束", "Java→Python 必须设连接/读取超时；可重试请求带幂等 requestId；日志不记录密码与敏感病例"],
    ],
    col_widths=[3, 13],
)
doc.add_page_break()

# ==================== 7. 核心时序图 ====================
h1("7. 核心时序图")
p("以下时序图以“步骤表格”表达（Word 原生渲染方案），每行 = 一次交互。")

h2("7.1 登录时序")
table(["#", "参与方", "动作", "关键点"], [
    ["1", "前端", "POST /api/auth/login {username, password}", "登录页表单"],
    ["2", "Java AuthController", "委托 Spring Security 认证", "UserDetailsService 加载用户"],
    ["3", "Java", "BCrypt.matches 校验密码散列", "明文不落库、不比对"],
    ["4", "Java", "签发 JWT（HS256，含 username/roles）", "无状态令牌"],
    ["5", "前端", "token 存 localStorage，后续请求带 Authorization: Bearer", "401 全局拦截回登录页"],
    ["6", "Java", "审计埋点：login 动作落 audit_logs", "username/result/durationMs/ip"],
], col_widths=[1, 3.4, 7, 4.6])

h2("7.2 流式问答时序（核心）")
table(["#", "参与方", "动作", "关键点"], [
    ["1", "前端", "fetch POST /api/analysis/stream（stream:true）", "手动解析 SSE 流"],
    ["2", "Java AnalysisController", "组装 historyContext（Redis 缓存 + DB 兜底）转发 Python", "每会话事件缓冲开启"],
    ["3", "Python guardrail 节点", "围栏判定（关键词快路径 → LLM few-shot）", "越界毫秒级拦截，无 LLM 生成"],
    ["4", "agent ⇄ tools 循环", "LLM 决策调用 retrieve_guilinguben / lookup_formula", "MAX_ITERATIONS=3 防死循环"],
    ["5", "Python", "Ollama stream:true 逐 token，ContextVar 事件发射 + 有界队列", "事件不入图状态，丢弃防内存膨胀"],
    ["6", "Java", "WebFlux WebClient 消费 + SseEmitter 转发", "断连不取消订阅，照常落库"],
    ["7", "前端", "event_id 去重 + 打字机渲染", "token/done 事件分型处理"],
    ["8", "Java", "done 事件落库 records + 更新会话缓存 + 审计埋点", "每会话缓冲 TTL 5 分钟"],
], col_widths=[1, 3.6, 7.2, 4.2])

h2("7.3 断连恢复时序（SSE 三件套）")
table(["#", "参与方", "动作", "关键点"], [
    ["1", "前端", "断连检测（网络异常/页面刷新）", "记录最后收到的 event_id"],
    ["2", "前端", "重连带 Last-Event-ID 请求头", "自增 event_id 是续传锚点"],
    ["3", "Java", "缓冲命中 → 从断点续发后续事件（去重）", "短断连无损恢复"],
    ["4", "Java", "缓冲过期（TTL 5 分钟）→ 返回历史恢复指引", "长断连降级路径"],
    ["5", "前端", "拉取 /api/analysis/history 渲染完整回答", "最终兜底：历史数据一定完整"],
], col_widths=[1, 3.6, 7.2, 4.2])

h2("7.4 越界拦截时序（围栏快路径）")
table(["#", "参与方", "动作", "关键点"], [
    ["1", "前端", "提问（如“帮我开个方子治癌症”）", "正常请求"],
    ["2", "Python guardrail", "关键词快路径命中 → 直接降级回答", "实测 43ms，零 LLM 调用"],
    ["3", "Python", "返回 out_of_scope + 免责声明 + 人工复核引导", "fail-open 不阻塞"],
    ["4", "Java", "正常落库 + 审计", "越界请求也留痕"],
], col_widths=[1, 3.6, 7.2, 4.2])

doc.add_page_break()

# ==================== 8. 功能流转图 ====================
h1("8. 功能流转图")
p("每个功能的完整流转以“阶段流转表”表达：输入 → 处理步骤 → 输出。")

def flow(name, steps):
    h3(name)
    table(["阶段", "处理内容", "产物/输出"], steps, col_widths=[2.2, 9, 4.8])

flow("8.1 智能问答（严格模式）", [
    ["输入", "用户提问 + sessionId + strictMode=true", "请求体"],
    ["围栏", "关键词快路径 → LLM few-shot 越界判定", "放行 / out_of_scope 拦截"],
    ["决策", "agent 节点 LLM 决策是否调工具（动态 RAG 开关）", "tool_calls / 直接回答"],
    ["检索", "retrieve_guilinguben 向量检索 + lookup_formula 方剂查询", "证据列表（含 document_id/score）"],
    ["兜底", "严格模式未调工具 → 丢弃直接回答强制注入检索", "代码层确定性兜底"],
    ["生成", "final_answer 基于证据强制生成（循环截断）", "answer + citations"],
    ["输出", "结构化响应 → Java 落库 → 前端渲染引用卡片", "可溯源回答"],
])

flow("8.2 选词解释", [
    ["输入", "用户光标选中 PDF 古籍片段", "选中文本 + 上下文"],
    ["转发", "前端 → Java /api/explain（JWT）→ Python /api/agent/explain", "跨端调用链"],
    ["生成", "LLM 生成白话文解释/辨证分析", "解释文本"],
    ["落库", "Java 审计埋点（explain 动作）", "audit_logs"],
    ["输出", "前端展示解释结果", "用户可理解的释义"],
])

flow("8.3 会话历史与侧栏列表", [
    ["输入", "前端请求历史/列表（带 JWT）", "分页参数"],
    ["历史", "GET /api/analysis/history：分页查询 records（limit clamp 1~200）", "total/hasMore + 升序消息"],
    ["列表", "GET /api/analysis/sessions：聚合 SQL（首问标题/轮数/更新时间）", "DeepSeek 风格侧栏"],
    ["降级", "加载失败静默降级，不阻塞提问", "fail-open"],
    ["输出", "前端渲染消息气泡 + 引用证据卡", "多轮可回溯对话"],
])

flow("8.4 接口限流", [
    ["输入", "高频请求（同 IP）", "HTTP 请求"],
    ["计数", "Redis INCR 固定窗口计数（30 次/分钟/IP）", "计数键按 IP 维度"],
    ["判定", "超阈值 → 429；未超 → 放行", "429 响应"],
    ["降级", "Redis 故障 → 四层 fail-open 放行", "可用性优先"],
])

flow("8.5 审计埋点", [
    ["输入", "关键动作：登录/问答/流式/解释", "业务事件"],
    ["采集", "controller 层统一埋点（username/action/durationMs/ip/result）", "audit_logs 记录"],
    ["查询", "GET /api/audit（ADMIN）", "管理端视图"],
])

flow("8.6 评测流程", [
    ["输入", "20 条评测集（症状/方剂/常识/越界/重复各 4 条）", "评测数据"],
    ["执行", "scripts/eval_rag.py 逐条调用真实链路", "真实响应"],
    ["评判", "规则判定 + 本地 Ollama judge 双评判", "三指标得分"],
    ["回归", "基线比对（20/20、0/12、20/20）→ 驱动修复", "质量护栏"],
])

doc.add_page_break()

# ==================== 9. UML 结构图 ====================
h1("9. UML 结构图")

h2("9.1 Java 端分层与类结构")
code(
"controller（对外 REST）\n"
"  ├─ HealthController      GET /api/health\n"
"  ├─ AuthController        POST /api/auth/login\n"
"  ├─ AnalysisController    POST /api/analysis | /api/analysis/stream | GET history/sessions | POST /api/explain\n"
"  └─ AuditController       GET /api/audit（@PreAuthorize ADMIN）\n"
"        │\n"
"service（业务编排）\n"
"  ├─ AuthService           认证 + JWT 签发\n"
"  ├─ AnalysisService       非流式编排 + 落库 + Redis 缓存\n"
"  ├─ AnalysisStreamService 流式转发 + 每会话事件缓冲（Last-Event-ID 续发）\n"
"  ├─ AuditService          审计埋点\n"
"  └─ AiClient/AiStreamClient  WebClient 调 Python（超时/降级/幂等）\n"
"        │\n"
"repository（数据访问，spring-data-jpa）\n"
"  ├─ UserRepository / RoleRepository\n"
"  ├─ AnalysisSessionRepository / AnalysisRecordRepository（显式 @Query 语义分离）\n"
"  └─ AuditLogRepository\n"
"        │\n"
"model（实体）\n"
"  ├─ User / Role（ManyToMany → user_roles）\n"
"  ├─ AnalysisSession / AnalysisRecord（citations JSON 字符串）\n"
"  └─ AuditLog\n"
"config（安全）\n"
"  ├─ SecurityConfig（过滤器链收口 authenticated，OPTIONS 精确放行，401/403 JSON）\n"
"  └─ JwtAuthenticationFilter（OncePerRequestFilter 解析校验 JWT）\n"
)

h2("9.2 Python Agent 状态机（LangGraph 图）")
code(
"          ┌──────────┐\n"
"          │ START     │\n"
"          └────┬─────┘\n"
"               ▼\n"
"          ┌──────────┐  越界  ┌──────────────┐\n"
"          │ guardrail │ ─────→ │ final_answer │（降级回答 + 免责声明）\n"
"          │ 双层围栏    │        └──────────────┘\n"
"          └────┬─────┘\n"
"        放行   │\n"
"               ▼\n"
"          ┌──────────┐  tool_calls  ┌──────────────┐\n"
"          │  agent    │ ───────────→ │    tools     │（retrieve_guilinguben / lookup_formula）\n"
"          │ LLM 决策   │ ←─────────── │  结构化证据    │\n"
"          └────┬─────┘   循环 ≤3 次    └──────────────┘\n"
"        无工具 │\n"
"               ▼\n"
"          ┌──────────────┐\n"
"          │ final_answer  │（基于已有证据强制生成，循环截断收敛）\n"
"          └──────┬───────┘\n"
"                 ▼\n"
"               END（检查点：SqliteSaver，thread_id=session_id）\n"
)

h2("9.3 向量库适配器（ports.py 协议）")
code(
"VectorStore（协议，定义 4 个契约方法）\n"
"  ├─ build_index(documents)\n"
"  ├─ similarity_search(query, k)\n"
"  ├─ similarity_search_with_score(query, k)\n"
"  └─ as_retriever()\n"
"        ▲\n"
"        ├── FaissVectorStore（本地 .faiss 索引，MVP 快速验证）\n"
"        ├── ChromaVectorStore（chromadb 嵌入式持久化，当前默认）\n"
"        └── MilvusVectorStore（分布式生产级，IVF_FLAT + COSINE）\n"
"切换方式：.env vector_backend 开关，tools/Agent/API 零改动\n"
)

doc.add_page_break()

# ==================== 10. 关键工程实践 ====================
h1("10. 关键工程实践")

h2("10.1 SSE 流式三件套（面试高频）")
table(["机制", "实现", "解决的问题"], [
    ["事件去重", "自增 event_id，前端按 id 丢弃重复", "网络重放/重复事件"],
    ["断点续发", "Java 每会话事件缓冲（TTL 5 分钟），Last-Event-ID 命中续发", "短断连不丢内容"],
    ["历史恢复", "缓冲过期引导前端拉历史接口", "长断连最终一致"],
], col_widths=[2.6, 8.4, 5])

h2("10.2 限流与降级 fail-open")
bullet("固定窗口限流：Redis INCR + 过期时间，30 次/分钟/IP，超限 429。")
bullet("四层 fail-open：Redis 连接失败/命令异常等逐层降级，最终放行——可用性优先于限流准确性。")

h2("10.3 多轮记忆治理")
bullet("滑动窗口摘要：最近 1 轮保留原文（指代解析），更早轮次 LLM 要点摘要 + 增量缓存（同会话每请求至多 1 次摘要调用）。")
bullet("失败 fail-open 降级截断；自由模式弱兜底（无证据 + 条文编号 → 追加警示）。")

h2("10.4 安全设计")
bullet("密码 BCrypt 散列；JWT HS256 无状态认证；SecurityConfig 收口 authenticated + OPTIONS 精确放行 + 401/403 JSON。")
bullet("双层围栏：关键词快路径（毫秒级）+ LLM few-shot（fail-open）；越界回答带免责声明与人工复核引导。")
bullet("数据隔离 owner 写路径：记录带 ownerUsername，查询按属主过滤。")

h2("10.5 部署编排工程")
bullet("compose profiles：rabbitmq/milvus 栈默认不拉起，按需 --profile 扩展。")
bullet("healthcheck：postgres pg_isready / redis redis-cli ping，start-all.sh 前置检查依赖健康状态。")
bullet("脚本幂等：already_up 检测跳过；停止以“端口释放”为最终判据（netstat 扫描 + taskkill //F //T 树杀）。")
bullet("Windows 编码治理：Python 用 PYTHONIOENCODING=utf-8、Java 用 -Dfile.encoding=UTF-8，三端日志统一 UTF-8。")

doc.add_page_break()

# ==================== 11. 踩坑与解决方案精选 ====================
h1("11. 踩坑与解决方案精选")
p("从需求书 46 个卡点中精选 12 个最有面试价值的（编号对应需求书卡点）。")

h2("11.1 架构与选型类")
table(["卡点", "现象/根因", "解法", "面试点"], [
    ["16.4 架构平衡", "“快跑通”与“过早扩展”的拉扯", "MVP 用简单方案（FAISS），生产再复杂中间件（Milvus）；先协议后实现", "技术演进节奏判断"],
    ["16.24 检查点选型", "会话状态存哪：内存/文件/数据库", "三方案权衡后选 SqliteSaver（单机代价最低且满足重启持久化），升级路径只改连接配置", "权衡思维 + 演进路径"],
    ["16.26/16.37 向量库可替换", "绑定单一向量库是技术债", "ports.py 协议 + 三适配器，切换只改配置；Chroma 切换后 top-5 与 FAISS 40/40 重合", "适配器模式落地"],
    ["16.27 平台化取舍", "自研 LangGraph vs Dify/Coze", "自研：可演进、可写进简历的底层能力；平台：快但黑盒", "技术路线决策依据"],
], col_widths=[2.6, 3.6, 6, 3.8])

h2("11.2 RAG 与数据类")
table(["卡点", "现象/根因", "解法", "面试点"], [
    ["16.6 PDF 清洗", "扫描 PDF 文本层缺失、页眉页脚噪声、中文编码", "文本层渲染 + 空白规范化 + 换行修正 + 页眉页脚过滤", "真实数据治理"],
    ["16.23 方剂繁简", "“麻黄汤”vs 繁体原文检索空结果", "zhconv 全量繁简转换替代硬编码映射表", "数据标准化策略"],
    ["16.36 数据切分", "按段落切分导致条文破碎", "“一个条文一条数据”按编号切分 964 条 + 方剂库 4 字段重构 446 条 + 页码双轨贯通", "领域驱动的切分策略"],
    ["16.14 时区", "入库时间与北京时间差 8 小时", "PG 时区 Asia/Shanghai（ALTER DATABASE + compose TZ 双保险）", "容器时区治理"],
], col_widths=[2.6, 3.6, 6, 3.8])

h2("11.3 Agent 与流式类")
table(["卡点", "现象/根因", "解法", "面试点"], [
    ["16.19 历史污染", "多轮历史旧答案让模型跳过工具复述幻觉条文", "system prompt 双重强化 + 严格模式 user 级强制指令", "Prompt 工程对抗上下文污染"],
    ["16.20 冷启动", "小模型首轮不调工具直接编造条文", "代码层确定性兜底：未调工具则丢弃回答强制注入检索", "不依赖模型自觉的工程兜底"],
    ["16.30 SSE 陷阱", "①未声明 charset=UTF-8 中文被误读 ②SseEmitter.send 带 MediaType 绕过 SseEventBuilder 拆包事件静默丢失", "响应头 charset 显式声明 + 严格按 SseEventBuilder API 发送", "协议细节决定成败"],
], col_widths=[2.6, 3.6, 6, 3.8])

h2("11.4 环境与工程类")
table(["卡点", "现象/根因", "解法", "面试点"], [
    ["16.43 密码漂移", "postgres 迁移后 Java 密码认证失败；容器内 localhost 是 trust 不验密码的假象", "用容器自身 IP 走 scram 真认证定位；POSTGRES_PASSWORD 仅空卷首次 initdb 生效；ALTER USER 三方对齐；JDBC URL 用 127.0.0.1 避 IPv6 ::1 撞 WSL", "信任边界 + 分层排查"],
    ["16.44/16.46 编码", "Python ✓ 抛 UnicodeEncodeError、Java 日志 GBK 乱码（重定向到文件后走平台默认编码）", "PYTHONIOENCODING=utf-8 + -Dfile.encoding=UTF-8 统一三端 UTF-8", "Windows 编码工程化"],
    ["16.45 进程孤儿", "kill -9 伪 PID 只杀 MSYS 包装进程，java/node 子进程成孤儿继续监听且误报成功", "停止脚本以“端口释放”为最终判据：netstat 取 Windows PID + taskkill //F //T 树杀", "进程树与跨层生命周期"],
], col_widths=[2.6, 3.6, 6, 3.8])

doc.add_page_break()

# ==================== 12. 部署与运维 ====================
h1("12. 部署与运维")

h2("12.1 编排方案（方案丙）")
p("Docker Compose 管中间件，启动脚本管三端应用；三端容器化为可选资产（面试展示），默认不启用。")
table(["组件", "运行方式", "端口", "健康检查"], [
    ["postgres / redis", "docker compose up -d", "5432 / 6379", "pg_isready / redis-cli ping"],
    ["Java 后端", "start-all.sh（mvn spring-boot:run）", "8080", "GET /api/health"],
    ["ai-service", "start-all.sh（uvicorn + torch_env）", "8001", "GET /health"],
    ["前端", "start-all.sh（next dev）", "3000", "页面入口"],
    ["Ollama", "宿主机进程（qwen2.5:7b）", "11434", "三端共同依赖"],
], col_widths=[3.2, 5.6, 2.4, 4.8])

h2("12.2 日常操作")
code(
"启动：docker compose up -d postgres redis && bash scripts/start-all.sh\n"
"停止：bash scripts/stop-all.sh（只停三端，不动容器；以端口释放为最终判据）\n"
"日志：tail -f logs/java.log / logs/ai-service.log / logs/frontend.log\n"
"验证：curl :8080/api/health、curl :8001/health、docker compose ps、浏览器问答一轮\n"
)

h2("12.3 按需扩展（profiles）")
code(
"docker compose --profile mq up -d rabbitmq        # 阶段五长任务队列\n"
"docker compose --profile milvus up -d etcd minio   # 切回 Milvus 时按三步拉起\n"
)

doc.add_page_break()

# ==================== 13. 后续规划与未完成工作 ====================
h1("13. 后续规划与未完成工作")

h2("13.1 阶段五规划中待办（4 项）")
table(["#", "事项", "技术方向", "面试价值"], [
    ["1", "RabbitMQ 文献处理与长任务队列", "异步任务、重试、死信队列", "消息队列工程化"],
    ["2", "MinIO 文献资产管理", "对象存储、上传解析流水线", "文献入库闭环"],
    ["3", "监控告警（Prometheus + Grafana）", "已有 /metrics 埋点 + Actuator 预留", "可观测性"],
    ["4", "CI/CD（GitHub Actions）", "构建/测试/部署流水线", "工程化交付"],
], col_widths=[1, 5.6, 5.4, 4])

h2("13.2 远期功能")
table(["#", "事项", "要点"], [
    ["1", "病案录入与 RLHF 闭环（需求书 5.3）", "病案向量化入库 → 用户自主公开 → 他人检索（来源标注“原文/客户病案”）→ 授权作为训练数据迭代模型；专家审核 + RLHF 反馈"],
    ["2", "会员角色与权限管理（需求书 5.4）", "注册/资料管理、会员等级、Redis 用量额度控制（每日调用次数）"],
], col_widths=[1, 5.4, 9.6])

h2("13.3 产品愿景演进路线")
table(["阶段", "形态", "关键增量"], [
    ["当前（MVP）", "Web + 本地部署（单机）", "RAG 问答/Agent/流式/鉴权/审计/评测全部闭环"],
    ["近期", "生产化", "阶段五 4 项：队列/资产/监控/CI-CD"],
    ["中期", "多端 + 多用户", "PC/安卓/iOS 客户端、会员分级、病案公开检索"],
    ["远期", "分布式 + 多 Agent", "高并发拆分、Milvus 集群化、多 Agent 协作模式、病案作为训练数据迭代"],
], col_widths=[2.6, 4.4, 9])

doc.add_page_break()

# ==================== 14. 面试高频问答准备 ====================
h1("14. 面试高频问答准备")

h2("14.1 项目总览类")
table(["问题", "回答要点"], [
    ["用一句话介绍项目", "基于《桂林古本伤寒杂病论》真实文献的中医 RAG 辅助诊疗平台：Java 业务后端 + Python LangGraph Agent + Next.js 前端三端架构，回答可溯源（引用/页码）、带安全围栏、SSE 流式、JWT+RBAC、审计与评测闭环。"],
    ["为什么 Java + Python 双后端", "岗位要求 Java，AI 生态在 Python：Java 守业务边界（认证/持久化/审计/编排），Python 做 Agent/RAG/LLM。接口契约先行，联调后稳定。"],
    ["项目最大难点", "不是跑通 demo，而是把真实数据、真实约束、真实工程问题同时放进一个可演进架构：46 个卡点全部定位根因、修复、验收、沉淀。"],
], col_widths=[3.4, 12.6])

h2("14.2 RAG / Agent 类")
table(["问题", "回答要点"], [
    ["RAG 流程怎么做的", "PDF 按条文编号切分 964 条 → BGE-large-zh 本地嵌入（1024 维）→ Chroma 向量库（协议适配器三选一）→ 检索 top-5 → LLM 基于证据生成 + citations 溯源。"],
    ["怎么防幻觉", "四层：严格模式强制证据生成、未调工具代码兜底、双层围栏拦截越界、引用与回答一致性校验（16.25）。评测集幻觉率基线 0/12。"],
    ["Agent 循环怎么设计的", "LangGraph 状态机：guardrail → agent ⇄ tools（MAX_ITERATIONS=3）→ final_answer 强制收敛；检查点 SqliteSaver 按 thread_id 持久化；工具异常不中断循环。"],
    ["向量库选型怎么考虑的", "统一协议 ports.py，MVP 用 FAISS，工程期切 Chroma，生产可切 Milvus——只改配置不改业务代码。"],
], col_widths=[3.4, 12.6])

h2("14.3 工程实践类")
table(["问题", "回答要点"], [
    ["SSE 流式怎么保证不丢内容", "三件套：自增 event_id 去重、Java 每会话缓冲 + Last-Event-ID 断点续发（TTL 5 分钟）、缓冲过期引导历史恢复。"],
    ["接口限流怎么做", "Redis INCR 固定窗口 30 次/分钟/IP，超限 429；Redis 故障四层 fail-open 放行，可用性优先。"],
    ["鉴权怎么做的", "Spring Security + JWT（HS256）+ BCrypt；过滤器链收口 authenticated；RBAC 三表；管理接口 @PreAuthorize；数据隔离 owner 写路径。"],
    ["多轮记忆怎么管", "滑动窗口：最近 1 轮原文 + 更早轮次 LLM 要点摘要（增量缓存，至多 1 次摘要调用/请求）；失败降级截断。"],
    ["怎么保障质量回归", "自建 20 条评测集 + 三指标基线（工具调用精度/幻觉率/任务成功率），规则 + Ollama judge 双评判，评测驱动修复。"],
], col_widths=[3.4, 12.6])

h2("14.4 收尾建议")
p("面试讲解顺序建议：产品背景（1 章）→ 架构图（3 章）→ 一次流式问答的完整链路（7.2 时序）→ "
  "挑 2-3 个踩坑讲排查过程（11 章）→ 后续规划（13 章）。每个技术点都能落到代码、卡点编号与验收数据，"
  "体现“真实项目、真实问题、真实闭环”。")

# ==================== 保存 ====================
import os
os.makedirs("docs", exist_ok=True)
doc.save(OUT)
print(f"已生成：{OUT}")
print(f"章节：14 章 | 表格与文本图已内嵌 | 页数约 {len(doc.element.body.findall('.//' + qn('w:p')))} 段落")

