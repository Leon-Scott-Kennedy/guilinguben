"""
端到端测试脚本
测试已运行的 Python AI 服务
"""
import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✓ 状态码: {r.status_code}")
        print(f"✓ 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
        return True
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False


def test_agent_analyze():
    """测试分析接口"""
    print("\n" + "=" * 60)
    print("测试 2: RAG 分析接口（端到端）")
    print("=" * 60)
    
    payload = {
        "sessionId": "test-session-001",
        "question": "辨证论治的思路是什么",
        "strictMode": True,
        "topK": 3
    }
    
    print(f"请求: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print("\n正在调用...")
    
    start_time = time.time()
    try:
        r = requests.post(
            f"{BASE_URL}/api/agent/analyze",
            json=payload,
            timeout=120
        )
        elapsed = time.time() - start_time
        
        print(f"\n✓ 状态码: {r.status_code}")
        print(f"✓ 响应时间: {elapsed:.2f} 秒")
        
        response = r.json()
        print(f"\n回答长度: {len(response.get('answer', ''))} 字符")
        print(f"引用数量: {len(response.get('citations', []))}")
        print(f"意图: {response.get('intent')}")
        print(f"状态: {response.get('status')}")
        
        if response.get('citations'):
            print("\n引用来源:")
            for i, citation in enumerate(response['citations'][:3], 1):
                print(f"  {i}. {citation.get('title')}")
                print(f"     相关性: {citation.get('score')}")
        
        print("\n回答预览（前 200 字符）:")
        print(response.get('answer', '')[:200] + "...")
        
        return True
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n✗ 失败 (耗时 {elapsed:.2f} 秒): {e}")
        return False


if __name__ == "__main__":
    print("\n桂林古本 AI 服务端到端测试")
    print("=" * 60)
    
    health_ok = test_health()
    if not health_ok:
        print("\n❌ 服务未运行，请先启动 Python 服务")
        exit(1)
    
    analyze_ok = test_agent_analyze()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"健康检查: {'✓ 通过' if health_ok else '✗ 失败'}")
    print(f"RAG 分析: {'✓ 通过' if analyze_ok else '✗ 失败'}")
    print("=" * 60)
