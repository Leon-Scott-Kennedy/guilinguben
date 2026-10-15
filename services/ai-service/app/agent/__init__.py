"""Agent 包：ai-service 内的 LangGraph Agent 实现（B1 接线版）

B 轮目标：把 main.py 的"向量检索 -> 拼 Prompt 生成"两步写死函数调用，
演进为 LangGraph 图引擎驱动的 Agent（B2 起引入 Tool Calling 与动态 RAG 开关）。
"""
