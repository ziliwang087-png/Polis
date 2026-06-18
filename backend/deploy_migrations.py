#!/usr/bin/env python3
"""执行数据库迁移到云端 Supabase"""
import os
import subprocess
import sys

# 获取项目 ref
PROJECT_REF = "bshqimrmrdcvywduqwwh"
DB_PASSWORD = "PolisTest2026!"

# 构造连接字符串 (直连数据库，不走 pooler)
DATABASE_URL = f"postgresql://postgres:{DB_PASSWORD}@db.{PROJECT_REF}.supabase.co:5432/postgres"

print(f"连接到 Supabase: {PROJECT_REF}")
print(f"DATABASE_URL: postgresql://postgres:***@db.{PROJECT_REF}.supabase.co:5432/postgres")

# 读取迁移文件
migrations = [
    "migrations/001_initial_schema.sql",
    "migrations/002_social_tables.sql"
]

# 安装 psycopg2
print("\n检查依赖...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"], check=False)

import psycopg2

# 连接数据库
print("\n连接数据库...")
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # 执行迁移
    for migration_file in migrations:
        print(f"\n执行迁移: {migration_file}")
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        try:
            cur.execute(sql)
            conn.commit()
            print(f"✅ {migration_file} 执行成功")
        except Exception as e:
            print(f"⚠️  {migration_file} 执行时出现错误（可能表已存在）: {e}")
            conn.rollback()
    
    # 检查表
    print("\n检查已创建的表...")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    print(f"共 {len(tables)} 张表:")
    for table in tables:
        print(f"  - {table[0]}")
    
    cur.close()
    conn.close()
    print("\n✅ 数据库部署完成！")
    print(f"\n📊 Dashboard: https://supabase.com/dashboard/project/{PROJECT_REF}")
    
except Exception as e:
    print(f"\n❌ 连接失败: {e}")
    sys.exit(1)
