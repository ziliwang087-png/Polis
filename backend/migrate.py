"""
Polis Database Migration Manager
Manages Supabase Postgres migrations
"""
import os
import sys
from pathlib import Path

def get_supabase_url():
    """Get Supabase URL from environment"""
    url = os.getenv('SUPABASE_URL')
    if not url:
        print("ERROR: SUPABASE_URL environment variable not set")
        print("Please set: export SUPABASE_URL='postgresql://postgres:[password]@[project-ref].supabase.co:5432/postgres'")
        sys.exit(1)
    return url

def run_migration(direction='up'):
    """Run database migration"""
    import psycopg2
    
    url = get_supabase_url()
    migration_file = Path(__file__).parent / 'migrations' / f'001_initial_schema{"_down" if direction == "down" else ""}.sql'
    
    if not migration_file.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"Running migration: {migration_file.name}")
    
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        cur.execute(sql)
        conn.commit()
        
        print(f"✓ Migration {direction} completed successfully")
        
        # Verify tables
        if direction == 'up':
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            print(f"\n✓ Created {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    direction = sys.argv[1] if len(sys.argv) > 1 else 'up'
    if direction not in ['up', 'down']:
        print("Usage: python migrate.py [up|down]")
        sys.exit(1)
    run_migration(direction)
