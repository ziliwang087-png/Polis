#!/usr/bin/env python3
"""
P1 代码完整性检查
验证所有 P1 功能是否正确实现
"""
import os
import sys
from pathlib import Path

def check_file_exists(path, description):
    """检查文件是否存在"""
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✅ {description}: {path} ({size} bytes)")
        return True
    else:
        print(f"❌ {description}: {path} 不存在")
        return False

def check_import_in_file(filepath, import_statement, description):
    """检查文件中是否包含特定导入"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if import_statement in content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description}: 未找到 '{import_statement}'")
                return False
    except Exception as e:
        print(f"❌ {description}: 读取失败 - {e}")
        return False

def check_function_in_file(filepath, function_name, description):
    """检查文件中是否定义了特定函数"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if f"def {function_name}" in content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description}: 未找到函数 '{function_name}'")
                return False
    except Exception as e:
        print(f"❌ {description}: 读取失败 - {e}")
        return False

def main():
    print("=" * 70)
    print("Polis P1 代码完整性检查")
    print("=" * 70)
    
    checks_passed = 0
    checks_total = 0
    
    # 1. 检查新增文件
    print("\n### 1. 新增文件检查")
    files_to_check = [
        ("app/fraud_detection.py", "防刷检测模块"),
        ("app/routes/reputation.py", "Reputation API 路由"),
        ("test_p1_features.py", "P1 测试脚本"),
        ("P1_IMPLEMENTATION.md", "P1 实现文档"),
    ]
    
    for filepath, desc in files_to_check:
        checks_total += 1
        if check_file_exists(filepath, desc):
            checks_passed += 1
    
    # 2. 检查关键函数
    print("\n### 2. 防刷检测函数检查")
    functions_to_check = [
        ("app/fraud_detection.py", "detect_collusion", "串通检测算法"),
        ("app/fraud_detection.py", "calculate_work_reputation", "工作声望计算"),
        ("app/fraud_detection.py", "calculate_total_reputation", "总声望计算"),
    ]
    
    for filepath, func_name, desc in functions_to_check:
        checks_total += 1
        if check_function_in_file(filepath, func_name, desc):
            checks_passed += 1
    
    # 3. 检查 API 端点
    print("\n### 3. Reputation API 端点检查")
    api_functions = [
        ("app/routes/reputation.py", "get_agent_reputation", "GET /reputation/agents/{id}"),
        ("app/routes/reputation.py", "get_leaderboard", "GET /reputation/leaderboard"),
    ]
    
    for filepath, func_name, desc in api_functions:
        checks_total += 1
        if check_function_in_file(filepath, func_name, desc):
            checks_passed += 1
    
    # 4. 检查集成
    print("\n### 4. 集成检查")
    integrations = [
        ("app/routes/tasks.py", "from app.fraud_detection import detect_collusion", 
         "tasks.py 导入防刷模块"),
        ("app/routes/tasks.py", "detect_collusion(owner_id, submission['agent_id'], task_id)", 
         "review_task 调用防刷检测"),
        ("app/main.py", "from app.routes import auth, tasks, agents, reputation", 
         "main.py 导入 reputation router"),
        ("app/main.py", "app.include_router(reputation.router", 
         "main.py 注册 reputation router"),
    ]
    
    for filepath, search_string, desc in integrations:
        checks_total += 1
        if check_import_in_file(filepath, search_string, desc):
            checks_passed += 1
    
    # 5. 语法检查
    print("\n### 5. Python 语法检查")
    python_files = [
        "app/fraud_detection.py",
        "app/routes/reputation.py",
        "app/routes/tasks.py",
        "app/main.py",
        "test_p1_features.py",
    ]
    
    for filepath in python_files:
        checks_total += 1
        result = os.system(f"python -m py_compile {filepath} 2>&1 > /dev/null")
        if result == 0:
            print(f"✅ {filepath} 语法正确")
            checks_passed += 1
        else:
            print(f"❌ {filepath} 语法错误")
    
    # 总结
    print("\n" + "=" * 70)
    print(f"检查结果: {checks_passed}/{checks_total} 通过")
    
    if checks_passed == checks_total:
        print("✅ 所有检查通过！P1 代码实现完整。")
        return 0
    else:
        print(f"❌ {checks_total - checks_passed} 项检查失败")
        return 1

if __name__ == "__main__":
    os.chdir("/Users/a1111/projects/ai-society/backend")
    sys.exit(main())
