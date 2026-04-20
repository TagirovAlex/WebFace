"""
Database Migration Script for WebFace v2.0

This script performs database migration from v1.x to v2.0 adding:
- Token balance system (token_balances, token_transactions)
- Pricing system (pricing)
- Token rules (token_rules)
- User priority fields (priority, token_period, last_token_reset)

Usage:
    python migrate_db.py                    # Run with default database
    python migrate_db.py --dry-run      # Show what would be done
    python migrate_db.py --backup       # Create backup before migrating
    python migrate_db.py --reset-db     # Drop and recreate all tables (WARNING!)
"""

import os
import sys
import argparse
import shutil
import sqlite3
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import GenerationType, User, Generation, TokenBalance, TokenTransaction, Pricing, TokenRule


def get_engine():
    """Get SQLAlchemy engine from app context"""
    return db.engine


def table_exists(table_name):
    """Check if table exists in database"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        )
        return result.fetchone() is not None


def column_exists(table_name, column_name):
    """Check if column exists in table"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in result.fetchall()]
        return column_name in columns


def get_table_row_count(table_name):
    """Get row count for table"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return result.fetchone()[0]


def create_backup(db_path):
    """Create database backup"""
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"  [BACKUP] Created: {backup_path}")
    return backup_path


def migrate_token_balance():
    """Create token_balances table"""
    if table_exists('token_balances'):
        print("  [SKIP] token_balances already exists")
        return False

    db.create_all()
    print("  [OK] Created token_balances table")
    return True


def migrate_token_transactions():
    """Create token_transactions table"""
    if table_exists('token_transactions'):
        print("  [SKIP] token_transactions already exists")
        return False

    db.create_all()
    print("  [OK] Created token_transactions table")


def migrate_pricing():
    """Create pricing table and add default pricing"""
    if table_exists('pricing'):
        print("  [SKIP] pricing already exists")
        return False

    db.create_all()

    default_pricing = [
        {'module_key': 'wan22', 'base_cost': 10, 'cost_per_width': 2, 'cost_per_height': 2, 'cost_per_second': 0},
        {'module_key': 'wan22_video', 'base_cost': 50, 'cost_per_width': 0, 'cost_per_height': 0, 'cost_per_second': 5},
        {'module_key': 'qwen_single', 'base_cost': 15, 'cost_per_width': 2, 'cost_per_height': 2, 'cost_per_second': 0},
        {'module_key': 'qwen_multi', 'base_cost': 25, 'cost_per_width': 3, 'cost_per_height': 3, 'cost_per_second': 0},
    ]

    with app.app_context():
        for p in default_pricing:
            pricing = Pricing(**p)
            db.session.add(pricing)
        db.session.commit()

    print("  [OK] Created pricing table with defaults")
    return True


def migrate_token_rules():
    """Create token_rules table and add default rules"""
    if table_exists('token_rules'):
        print("  [SKIP] token_rules already exists")
        return False

    db.create_all()

    default_rules = [
        {'name': 'Daily Bonus', 'rule_type': 'daily', 'amount': 50, 'max_uses': 1},
        {'name': 'Weekly Bonus', 'rule_type': 'weekly', 'amount': 200, 'max_uses': 1},
        {'name': 'Monthly Bonus', 'rule_type': 'monthly', 'amount': 500, 'max_uses': 1},
        {'name': 'First Generation', 'rule_type': 'first_generation', 'amount': 100, 'max_uses': 1},
    ]

    with app.app_context():
        for r in default_rules:
            rule = TokenRule(**r)
            db.session.add(rule)
        db.session.commit()

    print("  [OK] Created token_rules table with defaults")
    return True


def migrate_user_priority():
    """Add priority fields to users table"""
    if column_exists('users', 'priority'):
        print("  [SKIP] users.priority already exists")
        return False

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute("ALTER TABLE users ADD COLUMN priority INTEGER DEFAULT 50 NOT NULL")
        conn.execute("ALTER TABLE users ADD COLUMN token_period VARCHAR(20) DEFAULT 'monthly' NOT NULL")
        conn.execute("ALTER TABLE users ADD COLUMN last_token_reset TIMESTAMP")
        conn.commit()

    print("  [OK] Added priority, token_period, last_token_reset to users")
    return True


def migrate_hidden_field():
    """Add hidden_from_user field to generations table"""
    if column_exists('generations', 'hidden_from_user'):
        print("  [SKIP] generations.hidden_from_user already exists")
        return False

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute("ALTER TABLE generations ADD COLUMN hidden_from_user BOOLEAN DEFAULT 0 NOT NULL")
        conn.commit()

    print("  [OK] Added hidden_from_user to generations")
    return True


def init_user_balances():
    """Initialize token balances for existing users"""
    with app.app_context():
        users = User.query.all()
        for user in users:
            existing = TokenBalance.query.filter_by(user_id=user.id).first()
            if not existing:
                balance = TokenBalance(user_id=user.id, balance=0)
                db.session.add(balance)

        db.session.commit()
        print(f"  [OK] Initialized balances for {len(users)} users")
        return len(users)


def show_status():
    """Show current database status"""
    print("\n=== Database Status ===\n")

    tables = {
        'generation_types': 'GenerationType',
        'users': 'User',
        'generations': 'Generation',
        'token_balances': 'TokenBalance',
        'token_transactions': 'TokenTransaction',
        'pricing': 'Pricing',
        'token_rules': 'TokenRule',
    }

    for table_name, model_name in tables.items():
        exists = table_exists(table_name)
        count = get_table_row_count(table_name) if exists else 0
        status = f"{count} rows" if exists else "MISSING"
        print(f"  {table_name}: {status}")

    print("\n=== User Fields ===\n")
    fields = ['priority', 'token_period', 'last_token_reset']
    for field in fields:
        exists = column_exists('users', field)
        print(f"  users.{field}: {'OK' if exists else 'MISSING'}")

    print()


def reset_database():
    """Drop and recreate all tables"""
    confirm = input("WARNING: This will delete ALL data. Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return

    print("\nDropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    print("Done. Database reset complete.")


def run_migration(dry_run=False, create_backup_flag=False, show_only=False):
    """Run main migration"""

    # Get database path
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
    else:
        db_path = 'webface.db'

    print(f"\n=== WebFace Database Migration ===")
    print(f"Database: {db_path}")
    print(f"Dry run: {dry_run}")
    print()

    # Show status before
    show_status()

    if show_only:
        return

    # Create backup if requested
    if create_backup_flag and os.path.exists(db_path):
        create_backup(db_path)

    if dry_run:
        print("[DRY RUN] No changes made.")
        return

    # Run migrations
    print("\n=== Running Migrations ===\n")

    with app.app_context():
        migrate_token_balance()
        migrate_token_transactions()
        migrate_pricing()
        migrate_token_rules()
        migrate_user_priority()
        migrate_hidden_field()
        init_user_balances()

    # Show status after
    print("\n=== After Migration ===\n")
    show_status()

    print("\n✓ Migration complete!")


def main():
    parser = argparse.ArgumentParser(description='WebFace Database Migration')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--backup', action='store_true', help='Create backup before migrating')
    parser.add_argument('--reset-db', action='store_true', help='Drop and recreate all tables (WARNING!)')
    parser.add_argument('--status', action='store_true', help='Show database status only')
    args = parser.parse_args()

    if args.reset_db:
        reset_database()
        return

    if args.status:
        show_status()
        return

    run_migration(
        dry_run=args.dry_run,
        create_backup_flag=args.backup,
        show_only=args.status
    )


if __name__ == '__main__':
    main()