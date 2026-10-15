from src.core.agent_graph import AgentGraph, build_langgraph_agent


class FakeRetriever:
    def get_retriever(self):
        return object()


class FakeLLM:
    def invoke(self, *args, **kwargs):
        return "ok"


def test_agent_graph_accepts_legacy_signature():
    graph = AgentGraph(FakeRetriever(), FakeLLM(), strict_mode=True)
    assert hasattr(graph, "_app")


def test_build_langgraph_agent_legacy_factory_signature():
    app = build_langgraph_agent(FakeRetriever(), FakeLLM(), prompt_template=None, strict_mode=True)
    assert app is not None
