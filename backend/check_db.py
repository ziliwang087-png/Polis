#!/usr/bin/env python3
from app.database import get_db_connection

with get_db_connection() as conn:
    cur = conn.cursor()
    
    # 检查表是否存在
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('notifications', 'badges', 'task_ratings', 'posts', 'comments', 'tasks')
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    print("=== 存在的表 ===")
    for t in tables:
        print(f"  - {t['table_name']}")
    
    # 检查 agents 表游戏化字段
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'agents' 
        AND column_name IN ('xp', 'level', 'total_tasks_completed', 'total_tasks_failed')
        ORDER BY column_name
    """)
    
    agent_cols = cur.fetchall()
    print("\n=== agents 表游戏化字段 ===")
    if agent_cols:
        for c in agent_cols:
            print(f"  - {c['column_name']}")
    else:
        print("  ⚠️ 没有游戏化字段！")
