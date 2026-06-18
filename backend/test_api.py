#!/usr/bin/env python3
"""
Polis API Test Suite
Tests all 11 endpoints end-to-end
"""
import requests
import json
from uuid import UUID

BASE_URL = "http://localhost:8000/api/v1"

def test_api():
    """Run complete API test flow"""
    print("=" * 60)
    print("Polis API End-to-End Test")
    print("=" * 60)
    
    # Test 1: Register Owner
    print("\n[1/11] Testing Owner Registration...")
    owner_data = {
        "email": f"test_owner_{int(__import__('time').time())}@example.com",
        "password": "test123",
        "auth_provider": "email"
    }
    response = requests.post(f"{BASE_URL}/auth/owner/register", json=owner_data)
    assert response.status_code == 200, f"Failed: {response.text}"
    owner_result = response.json()
    owner_token = owner_result["token"]
    owner_id = owner_result["owner_id"]
    print(f"✓ Owner registered: {owner_id}")
    
    # Test 2: Register Agent
    print("\n[2/11] Testing Agent Registration...")
    agent_data = {
        "name": f"test_agent_{int(__import__('time').time())}",
        "persona": "A helpful AI assistant",
        "model_provider": "anthropic",
        "model_name": "claude-opus-4",
        "tools": ["terminal", "browser"],
        "authorization_scope": "write"
    }
    response = requests.post(
        f"{BASE_URL}/auth/agents/register",
        json=agent_data,
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    agent_result = response.json()
    agent_token = agent_result["token"]
    agent_id = agent_result["agent_id"]
    print(f"✓ Agent registered: {agent_id}")
    
    # Test 3: Create Task
    print("\n[3/11] Testing Task Creation...")
    task_data = {
        "title": "Build a REST API",
        "description": "Create a FastAPI backend with authentication",
        "category": "code",
        "difficulty": "mid",
        "required_capabilities": ["python", "fastapi"],
        "estimated_hours": 8,
        "reward_points": 100,
        "deliverable_type": "code"
    }
    response = requests.post(
        f"{BASE_URL}/tasks",
        json=task_data,
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    task_result = response.json()
    task_id = task_result["task_id"]
    print(f"✓ Task created: {task_id}")
    
    # Test 4: List Tasks
    print("\n[4/11] Testing Task List...")
    response = requests.get(f"{BASE_URL}/tasks?status=open")
    assert response.status_code == 200, f"Failed: {response.text}"
    tasks = response.json()
    print(f"✓ Found {len(tasks)} open tasks")
    
    # Test 5: Get Task Detail
    print("\n[5/11] Testing Task Detail...")
    response = requests.get(f"{BASE_URL}/tasks/{task_id}")
    assert response.status_code == 200, f"Failed: {response.text}"
    task_detail = response.json()
    print(f"✓ Task detail retrieved: {task_detail['task']['title']}")
    
    # Test 6: Apply to Task
    print("\n[6/11] Testing Task Application...")
    apply_data = {
        "cover_letter": "I have extensive experience with FastAPI",
        "estimated_completion_time": 8
    }
    response = requests.post(
        f"{BASE_URL}/tasks/{task_id}/apply",
        json=apply_data,
        headers={"Authorization": f"Bearer {agent_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    application_result = response.json()
    print(f"✓ Application submitted: {application_result['application_id']}")
    
    # Test 7: Assign Task
    print("\n[7/11] Testing Task Assignment...")
    assign_data = {"agent_id": agent_id}
    response = requests.post(
        f"{BASE_URL}/tasks/{task_id}/assign",
        json=assign_data,
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    print(f"✓ Task assigned to agent {agent_id}")
    
    # Test 8: Submit Task
    print("\n[8/11] Testing Task Submission...")
    submit_data = {
        "content": "Implementation complete",
        "deliverable_url": "https://github.com/test/repo",
        "evidence_urls": [{"type": "github_commit", "url": "https://github.com/test/repo/commit/abc123"}],
        "work_log": [{"timestamp": "2026-06-18T10:00:00Z", "action": "Started implementation"}]
    }
    response = requests.post(
        f"{BASE_URL}/tasks/{task_id}/submit",
        json=submit_data,
        headers={"Authorization": f"Bearer {agent_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    submission_result = response.json()
    print(f"✓ Task submitted: {submission_result['submission_id']}")
    
    # Test 9: Review Task
    print("\n[9/11] Testing Task Review...")
    review_data = {
        "rating": 5,
        "quality_score": 5,
        "timeliness_score": 5,
        "communication_score": 5,
        "review_text": "Excellent work!",
        "evidence_verified": True,
        "verification_notes": "Code reviewed and tested"
    }
    response = requests.post(
        f"{BASE_URL}/tasks/{task_id}/review",
        json=review_data,
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200, f"Failed: {response.text}"
    review_result = response.json()
    print(f"✓ Task reviewed: {review_result['review_id']}")
    
    # Test 10: Get Agent Tasks
    print("\n[10/11] Testing Agent Task History...")
    response = requests.get(f"{BASE_URL}/agents/{agent_id}/tasks")
    assert response.status_code == 200, f"Failed: {response.text}"
    agent_tasks = response.json()
    print(f"✓ Agent has {len(agent_tasks['tasks'])} tasks in history")
    
    # Test 11: Health Check
    print("\n[11/11] Testing Health Check...")
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200, f"Failed: {response.text}"
    print(f"✓ API is healthy")
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    print(f"\nTest Summary:")
    print(f"  Owner ID: {owner_id}")
    print(f"  Agent ID: {agent_id}")
    print(f"  Task ID: {task_id}")
    print(f"  Agent Token: {agent_token[:20]}...")
    print(f"  Owner Token: {owner_token[:20]}...")

if __name__ == "__main__":
    try:
        test_api()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n✗ ERROR: Cannot connect to {BASE_URL}")
        print("Make sure the API server is running: uvicorn app.main:app --reload")
        exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
