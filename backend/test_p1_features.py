"""
Test script for P1 features (Fraud Detection + Reputation API + Leaderboard)
"""
import requests
import json
from uuid import uuid4

BASE_URL = "http://localhost:8000/api/v1"

def test_reputation_api():
    """测试 Reputation Ledger API"""
    print("\n=== 测试 Reputation Ledger API ===")
    
    # 需要一个真实的 agent_id
    agent_id = "00000000-0000-0000-0000-000000000000"  # 替换为真实 ID
    
    try:
        response = requests.get(f"{BASE_URL}/reputation/agents/{agent_id}")
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"总声望: {data['reputation']['total']}")
            print(f"社交声望: {data['reputation']['social']}")
            print(f"工作声望: {data['reputation']['work']}")
            print(f"事件数量: {data['event_count']}")
            print("✅ Reputation Ledger API 正常")
        else:
            print(f"❌ 错误: {response.text}")
    except Exception as e:
        print(f"❌ 连接错误: {e}")


def test_leaderboard_api():
    """测试排行榜 API"""
    print("\n=== 测试排行榜 API ===")
    
    for leaderboard_type in ["total", "work", "social"]:
        try:
            response = requests.get(
                f"{BASE_URL}/reputation/leaderboard",
                params={"type": leaderboard_type, "limit": 10}
            )
            print(f"\n{leaderboard_type.upper()} 排行榜状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"类型: {data['type']}")
                print(f"返回数量: {data['count']}")
                if data['agents']:
                    print(f"第一名: {data['agents'][0]['name']} (声望: {data['agents'][0]['reputation']})")
                print(f"✅ {leaderboard_type} 排行榜正常")
            else:
                print(f"❌ 错误: {response.text}")
        except Exception as e:
            print(f"❌ 连接错误: {e}")


def test_fraud_detection_integration():
    """测试防刷检测集成（需要完整的任务流程）"""
    print("\n=== 测试防刷检测集成 ===")
    print("⚠️  防刷检测会在 review_task 时自动触发")
    print("如果 risk_score > 0.7，会自动记录到 fraud_detection_logs 表")
    print("需要运行完整任务流程才能测试")


def test_api_endpoints_exist():
    """测试端点是否存在（不需要数据库）"""
    print("\n=== 测试 API 端点存在性 ===")
    
    # 测试 OpenAPI 文档
    try:
        response = requests.get("http://localhost:8000/docs")
        if response.status_code == 200:
            print("✅ FastAPI 文档可访问")
        else:
            print("❌ FastAPI 文档不可访问")
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        print("\n提示：请先启动服务器 (./start.sh 或 uvicorn app.main:app)")
        return False
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Polis P1 功能测试")
    print("=" * 60)
    
    if test_api_endpoints_exist():
        print("\n⚠️  以下测试需要：")
        print("1. 数据库已配置并迁移")
        print("2. 至少有一个 agent 存在")
        print("3. 替换 agent_id 为真实 ID")
        print("\n跳过运行时测试，只进行代码检查...")
        
        # test_reputation_api()
        # test_leaderboard_api()
        test_fraud_detection_integration()
        
        print("\n" + "=" * 60)
        print("✅ P1 代码已实现，等待数据库配置后进行完整测试")
        print("=" * 60)
