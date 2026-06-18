#!/usr/bin/env python3
"""
Pre-deployment checklist validator
Checks if all files are in place before deployment
"""
import os
from pathlib import Path

def check_file_exists(path, description):
    """Check if file exists"""
    if os.path.exists(path):
        print(f"✓ {description}")
        return True
    else:
        print(f"✗ {description} - MISSING: {path}")
        return False

def main():
    base_dir = Path(__file__).parent
    
    print("=" * 60)
    print("Polis Backend Pre-Deployment Checklist")
    print("=" * 60)
    
    checks = []
    
    print("\n[1] Core Application Files")
    checks.append(check_file_exists(base_dir / "app/main.py", "Main application"))
    checks.append(check_file_exists(base_dir / "app/config.py", "Configuration"))
    checks.append(check_file_exists(base_dir / "app/database.py", "Database module"))
    checks.append(check_file_exists(base_dir / "app/auth.py", "Auth utilities"))
    checks.append(check_file_exists(base_dir / "app/dependencies.py", "Dependencies"))
    checks.append(check_file_exists(base_dir / "app/models.py", "Pydantic models"))
    
    print("\n[2] API Routes")
    checks.append(check_file_exists(base_dir / "app/routes/__init__.py", "Routes package"))
    checks.append(check_file_exists(base_dir / "app/routes/auth.py", "Auth routes"))
    checks.append(check_file_exists(base_dir / "app/routes/tasks.py", "Task routes"))
    checks.append(check_file_exists(base_dir / "app/routes/agents.py", "Agent routes"))
    
    print("\n[3] Database Migrations")
    checks.append(check_file_exists(base_dir / "migrations/001_initial_schema.sql", "Up migration"))
    checks.append(check_file_exists(base_dir / "migrations/001_initial_schema_down.sql", "Down migration"))
    checks.append(check_file_exists(base_dir / "migrate.py", "Migration tool"))
    
    print("\n[4] Configuration & Documentation")
    checks.append(check_file_exists(base_dir / "requirements.txt", "Dependencies"))
    checks.append(check_file_exists(base_dir / ".env.example", "Config template"))
    checks.append(check_file_exists(base_dir / "README.md", "Documentation"))
    checks.append(check_file_exists(base_dir / ".gitignore", "Git ignore"))
    
    print("\n[5] Testing")
    checks.append(check_file_exists(base_dir / "test_api.py", "API test script"))
    checks.append(check_file_exists(base_dir / "Polis_API.postman_collection.json", "Postman collection"))
    
    print("\n[6] Scripts")
    checks.append(check_file_exists(base_dir / "start.sh", "Startup script"))
    
    print("\n[7] Environment Check")
    env_exists = check_file_exists(base_dir / ".env", "Environment config (.env)")
    if not env_exists:
        print("   ⚠ Create .env from .env.example before deployment")
    
    print("\n" + "=" * 60)
    
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✓ ALL CHECKS PASSED ({passed}/{total})")
        print("\nReady for deployment!")
        print("\nNext steps:")
        print("1. Create Supabase project")
        print("2. Copy .env.example to .env")
        print("3. Fill in DATABASE_URL and JWT_SECRET_KEY")
        print("4. Run: python migrate.py up")
        print("5. Run: ./start.sh")
        print("6. Test: python test_api.py")
        return 0
    else:
        print(f"✗ CHECKS FAILED ({passed}/{total} passed)")
        return 1

if __name__ == "__main__":
    exit(main())
