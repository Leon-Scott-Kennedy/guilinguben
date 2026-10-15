# -*- coding: utf-8 -*-
"""生成 Word 版简历（大模型应用开发工程师方向）。

运行：python scripts/gen_resume_docx.py
输出：docs/李文琪_大模型应用开发工程师_简历.docx
章节顺序（用户确认）：个人信息 → 个人总结 → 技能 → 技术关键词 → 项目经历（AI 项目置顶）→ 工作经历 → 教育经历
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = r"docs/李文琪_大模型应用开发工程师_简历.docx"
BODY_FONT = "微软雅黑"
ACCENT = (0x1F, 0x3B, 0x63)

doc = Document()
for sec in doc.sections:
    sec.left_margin = Cm(1.8)
    sec.right_margin = Cm(1.8)
    sec.top_margin = Cm(1.5)
    sec.bottom_margin = Cm(1.5)


def _ea(run, name):
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


def para(text="", size=9.5, bold=False, color=None, space_after=2, align=None):
    pgh = doc.add_paragraph()
    pgh.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        pgh.alignment = align
    if text:
        style_run(pgh.add_run(text), size=size, bold=bold, color=color)
    return pgh


def title_line(left, right, size=10.5):
    """左粗体 + 右对齐时间（制表位）的一行。"""
    pgh = doc.add_paragraph()
    pgh.paragraph_format.space_after = Pt(1)
    pgh.paragraph_format.tab_stops.add_tab_stop(Cm(17.4), WD_TAB_ALIGNMENT.RIGHT)
    style_run(pgh.add_run(left), size=size, bold=True)
    style_run(pgh.add_run("\t" + right), size=9, color=(0x66, 0x66, 0x66))
    return pgh


def sub_line(label, text, size=9.5):
    pgh = doc.add_paragraph()
    pgh.paragraph_format.space_after = Pt(1)
    style_run(pgh.add_run(label), size=size, bold=True)
    style_run(pgh.add_run(text), size=size)
    return pgh


def bullet(text, size=9.5):
    pgh = doc.add_paragraph()
    pgh.paragraph_format.left_indent = Cm(0.4)
    pgh.paragraph_format.space_after = Pt(1)
    style_run(pgh.add_run("• "), size=size, bold=True, color=ACCENT)
    style_run(pgh.add_run(text), size=size)
    return pgh


def section(text):
    pgh = doc.add_paragraph()
    pgh.paragraph_format.space_before = Pt(8)
    pgh.paragraph_format.space_after = Pt(3)
    style_run(pgh.add_run(text), size=12.5, bold=True, color=ACCENT)
    pPr = pgh._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "1F3B63")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return pgh


# ==================== 个人信息 ====================
p = para("李文琪", size=20, bold=True, color=ACCENT, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
p = para("大模型应用开发工程师", size=11, bold=True, color=(0x2E, 0x5A, 0x8F), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
p = para("15327392742 ｜ 543129186@qq.com ｜ 男 ｜ 籍贯：湖北武汉",
         size=9, color=(0x55, 0x55, 0x55), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)

# ==================== 个人总结 ====================
section("个人总结")
para("5年Java后端开发经验，具备扎实的工程功底和系统设计能力，近一年深度投身大模型应用开发（RAG/Agent方向）。"
     "主导过从LCEL固定流水线到LangGraph状态机的完整重构，具备独立设计生产级AI系统的能力；"
     "完整落地RAG检索、Agent工具调用、SSE流式输出与断连恢复、评测体系与安全合规闭环。"
     "对技术有极致追求，能在代码审查中发现性能瓶颈并提出优化方案，具备良好的跨团队沟通和协作能力。")

# ==================== 技能 ====================
section("技能")
sub_line("编程语言：", "Java（5年实战），Python（大模型应用开发）")
sub_line("大模型与AI框架：", "LangGraph，LangChain，DeepEval，FastAPI")
sub_line("RAG技术栈：", "Chroma，FAISS，Milvus（向量库协议适配器三选一可切换），BGE，HuggingFace，Sentence-Transformers")
sub_line("大模型部署：", "Ollama，Qwen2.5:7B，本地私有化部署，医疗数据合规")
sub_line("后端与微服务：", "Spring Boot，Spring Cloud，Apollo，Nacos，OpenFeign，Sentinel")
sub_line("数据层：", "MySQL，Oracle，OpenGauss，OceanBase，Redis，MongoDB，ElasticSearch，PostgreSQL")
sub_line("消息与中间件：", "RocketMQ，ActiveMQ，Kafka")
sub_line("架构与运维：", "Skywalking链路追踪，Nginx反向代理，Shell自动化运维，分布式系统设计，异地双中心，DevOps CI/CD，Linux，Docker Compose")
sub_line("前端与部署：", "Next.js，Streamlit，Tomcat")

# ==================== 技术关键词 ====================
section("技术关键词")
para("RAG，LangGraph，LangChain，FAISS，Chroma，Milvus，BGE，Qwen，Ollama，DeepEval，SSE流式，断连恢复，评测体系，"
     "FastAPI，JWT/RBAC，Redis限流，Java，Spring Boot，Spring Cloud，Dubbo，RocketMQ，ElasticSearch，Redis，Kafka，"
     "OceanBase，OpenGauss，PostgreSQL，系统设计，微服务架构", size=9, space_after=2)

# ==================== 项目经历 ====================
section("项目经历")

# ---- 项目一：桂林古本（重点，置顶 + 最大篇幅）----
title_line("桂林古本《伤寒杂病论》智能辅助诊疗系统", "2026.07 - 至今")
sub_line("项目背景：", "某中医机构使用《桂林古本伤寒杂病论》进行教学与临床辅助，需要一套AI辅助问答工具。"
         "核心挑战：古文理解门槛高、用户意图开放（症状描述/方剂追问/闲聊测试）、医疗场景要求回答可溯源且合规。")
sub_line("技术架构：", "三端架构（Next.js 15前端：react-pdf内嵌古籍阅读器、选词解释、SSE打字机 ｜ "
         "Java 17 + Spring Boot 3.3业务后端：唯一对外入口 ｜ Python FastAPI + LangGraph Agent服务）")
bullet("RAG层：PDF按条文编号切分964条 + 方剂库446条（页码/方剂名/药物组成/注意事项）；BGE-large-zh（1024维）本地嵌入；"
       "向量库协议适配器三选一可切换（FAISS/Chroma/Milvus，当前Chroma），切换零业务改动")
bullet("Agent层：LangGraph状态机 guardrail → agent ⇄ tools（≤3轮防死循环）→ final_answer强制收敛；"
       "Tool Calling动态RAG开关（LLM自主决策是否检索）；双层安全围栏（关键词快路径毫秒级拦截 + LLM few-shot判定）；"
       "SqliteSaver检查点按会话持久化")
bullet("生成层：Ollama + Qwen2.5:7B本地私有化部署，推理链路全离线；回答强制携带条文级citations溯源")
bullet("流式与记忆：SSE三端链路（Python逐token → Java WebFlux转发 + 每会话事件缓冲 → 前端打字机）；"
       "断连恢复三件套（自增event_id去重、Last-Event-ID断点续发、缓冲过期引导历史恢复）；"
       "多轮记忆滑动窗口摘要（最近1轮原文 + 更早轮次LLM要点摘要 + 增量缓存）")
bullet("工程化：JWT + RBAC鉴权、Redis会话缓存与接口限流（30次/分/IP + fail-open降级）、审计日志、"
       "Docker Compose编排（healthcheck + profiles）")
sub_line("核心贡献：", "")
bullet("架构演进（V1 → V5.2 → 当前）：初期多分类方案（TF-IDF + 逻辑回归）Top-3召回率仅30%，转向语义检索 + RAG；"
       "V5.2主导LangChain LCEL固定流水线向LangGraph状态机的重构，设计三路条件路由（症状检索/上下文追问/越界拦截），"
       "终结“追问加减药物时强行检索误召回”造成的幻觉污染")
bullet("SSE流式与断连恢复工程：主导三端SSE打通与断连三件套落地，实测解决中文charset声明缺失、"
       "SseEventBuilder拆包事件静默丢失两个协议级坑，短断连无损续传、长断连历史兜底")
bullet("数据与检索治理：主导“一个条文一条数据”切分重构（964条）与方剂库4字段结构化，"
       "zhconv繁简全量转换解决繁体原文检索空结果；向量库适配器模式让选型变成配置")
bullet("质量与安全闭环：自建20条评测集（症状/方剂/常识/越界/重复各4条）三指标基线——工具调用精度20/20、"
       "幻觉率0/12、任务成功率20/20，评测驱动修复围栏两处误拦；JWT+RBAC+审计+限流保障医疗合规")
sub_line("项目成果：", "")
bullet("系统支持症状问答、方剂追问、越界拒答、选词解释、会话管理完整闭环，多轮指代追问验证通过")
bullet("形成基于LangGraph的Agentic RAG脚手架（可迁移金融、法律等垂直领域），沉淀46个工程卡点的排查与修复记录")
bullet("后续规划：病案录入与RLHF闭环、会员分级体系、RabbitMQ长任务队列、Milvus集群化")

# ---- 项目二：北京银行 ----
title_line("北京银行——企业手机银行后端系统", "2024.12 - 2025.07")
sub_line("项目背景：", "根据国家战略实施信创改造，实现国有软件自主可控。将原有系统迁移至国产化技术栈"
         "（OceanBase、OpenGauss等），保障金融系统信息安全。")
sub_line("技术架构：", "DevOps CI/CD + 云平台部署；SpringBoot + SpringCloud（OpenFeign、Sentinel）；"
         "Nacos服务注册与配置管理；Redis + MongoDB + Kafka；OceanBase + OpenGauss国产数据库；"
         "Nginx反向代理；Skywalking全链路追踪。")
sub_line("核心贡献：", "")
bullet("主导代码迁移和数据库贯标工作，将原有业务逻辑平滑迁移至国产数据库")
bullet("参与设计数据同步方案，经多方论证确认可行，保障新旧系统数据一致性")
bullet("负责多系统联调及测试，应急处理线上各类问题")
bullet("通过Skywalking链路追踪定位性能瓶颈，优化慢SQL和接口响应时间")
sub_line("项目成果：", "顺利完成信创改造目标，系统在国产技术栈上稳定运行；数据同步方案成为团队后续项目的参考模板。")

# ---- 项目三：邮储银行 ----
title_line("中国邮政储蓄银行信用卡中心——信用卡智能通知系统", "2022.02 - 2024.11")
sub_line("项目背景：", "根据上游系统的实时交易结果或接收来自企业消息总线的大数据量批量文件，对数据进一步处理后，"
         "向下游发送短信、微信、App消息及邮件，最终送达各类用户。系统具备本地化功能，可灵活承接各种业务需求。")
sub_line("技术架构：", "异地双中心架构，数据库异地主备；SpringBoot + Dubbo；Apollo配置中心 + Nacos注册中心；"
         "RocketMQ异步消息队列；HDFS分布式文件系统；ElasticSearch日志采集与检索；Redis热点数据缓存；"
         "OpenGauss磁盘数据库；Prometheus实时监控。")
sub_line("核心贡献：", "")
bullet("负责需求分析与业务沟通，编写开发测试文档，主导核心后端模块开发")
bullet("搭建系统环境并完成服务部署，每日进行系统巡检和交易日志分析")
bullet("通过Nginx反向代理访问ElasticSearch客户端Kibana，实现真实服务器IP对客户端不可见")
bullet("编写Shell脚本每日定时比对批量文件的数据差异，保障数据一致性")
bullet("根据Prometheus实时监控数据分析系统运行状态，应急处理线上各类问题")
bullet("手动编写轮询访问多IP的业务代码，实现高可用故障自动切换")
sub_line("项目成果：", "系统稳定支撑每日千万级消息推送，满足邮储银行信用卡中心业务需求；异地双中心架构保障了系统的高可用性和灾备能力。")

# ==================== 工作经历 ====================
section("工作经历")
title_line("中电金信软件有限公司", "Java研发工程师 ｜ 2025.07 - 至今")
title_line("北京兆日科技有限公司", "Java研发工程师 ｜ 2024.12 - 2025.07")
title_line("天阳宏业科技有限公司", "Java研发工程师 ｜ 2022.02 - 2024.11")
title_line("北京宇信科技集团股份有限公司", "Java研发工程师 ｜ 2020.12 - 2022.02")
title_line("北京直真科技股份有限公司", "Java研发工程师 ｜ 2020.07 - 2020.11")

# ==================== 教育经历 ====================
section("教育经历")
title_line("长江大学 ｜ 软件工程 ｜ 本科", "2016.9 - 2020.7")

# ==================== 保存 ====================
import os
os.makedirs("docs", exist_ok=True)
doc.save(OUT)
print(f"已生成：{OUT}")
