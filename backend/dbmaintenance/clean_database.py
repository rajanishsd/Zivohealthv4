#!/usr/bin/env python3
"""
Database Cleanup Script

This script cleans up PostgreSQL database tables while preserving
user and doctor data. Use with caution - this will permanently delete data.
"""

import psycopg2
import sys
import os
from typing import List, Dict, Any
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def get_database_config() -> Dict[str, str]:
    """Get database configuration from environment or defaults"""
    return {
        'host': os.getenv('DATABASE_HOST', 'localhost'),
        'port': os.getenv('DATABASE_PORT', '5432'),
        'database': os.getenv('DATABASE_NAME', 'zivohealth'),
        'user': os.getenv('DATABASE_USER', 'rajanishsd'),
        'password': os.getenv('DATABASE_PASSWORD', '')
    }

def connect_to_database():
    """Connect to PostgreSQL database"""
    config = get_database_config()
    
    try:
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("✅ Connected to PostgreSQL successfully")
        return conn
    except psycopg2.Error as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

def get_all_tables(conn: psycopg2.extensions.connection) -> List[str]:
    """Get list of all tables in the database"""
    cursor = conn.cursor()
    
    query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name;
    """
    
    cursor.execute(query)
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    
    return tables

def get_table_row_counts(conn: psycopg2.extensions.connection, tables: List[str]) -> Dict[str, int]:
    """Get row counts for all tables"""
    cursor = conn.cursor()
    row_counts = {}
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            result = cursor.fetchone()
            count = result[0] if result is not None else 0
            row_counts[table] = count
        except psycopg2.Error:
            row_counts[table] = 0
    cursor.close()
    return row_counts

def display_database_stats(all_tables: List[str], row_counts: Dict[str, int], preserve_tables: List[str]):
    """Display database statistics"""
    tables_to_clean = [table for table in all_tables if table not in preserve_tables]
    
    print(f"\n📊 Database Summary:")
    print(f"   Total Tables: {len(all_tables)}")
    print(f"   Tables to Preserve: {len(preserve_tables)}")
    print(f"   Tables to Clean: {len(tables_to_clean)}")
    
    print(f"\n🔒 Preserved Tables:")
    for table in preserve_tables:
        if table in all_tables:
            count = row_counts.get(table, 0)
            print(f"   ✅ {table}: {count:,} rows")
        else:
            print(f"   ⚠️  {table}: (table not found)")
    
    print(f"\n🧹 Tables to Clean:")
    total_rows_to_delete = 0
    for table in tables_to_clean:
        count = row_counts.get(table, 0)
        total_rows_to_delete += count
        print(f"   🗑️  {table}: {count:,} rows")
    
    print(f"\n📈 Total Data Impact:")
    print(f"   Rows to Delete: {total_rows_to_delete:,}")
    preserved_rows = sum(row_counts.get(table, 0) for table in preserve_tables if table in all_tables)
    print(f"   Rows to Preserve: {preserved_rows:,}")

def clean_database_tables(conn: psycopg2.extensions.connection, tables_to_clean: List[str], dry_run: bool = True) -> Dict[str, Any]:
    """Clean database tables"""
    if not tables_to_clean:
        return {'tables_cleaned': 0, 'rows_deleted': 0}
    print(f"\n🧹 {'[DRY RUN] ' if dry_run else ''}Starting database cleanup...")
    
    cursor = conn.cursor()
    results = {
        'tables_cleaned': 0,
        'rows_deleted': 0,
        'cleaned_tables': []
    }
    
    try:
        # Disable foreign key checks temporarily
        if not dry_run:
            cursor.execute("SET session_replication_role = replica;")
        
        for table in tables_to_clean:
            try:
                # Get row count before deletion
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count_result = cursor.fetchone()
                row_count = row_count_result[0] if row_count_result is not None else 0

                if row_count > 0:
                    print(f"   {'[DRY RUN] ' if dry_run else ''}Cleaning {table}: {row_count:,} rows...")
                    if not dry_run:
                        # Use TRUNCATE for faster deletion, fallback to DELETE if it fails
                        try:
                            cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                        except psycopg2.Error:
                            cursor.execute(f"DELETE FROM {table}")
                    
                    results['tables_cleaned'] += 1
                    results['rows_deleted'] += row_count
                    results['cleaned_tables'].append({'table': table, 'rows': row_count})
                else:
                    print(f"   ⏭️  {table}: already empty")
                
            except psycopg2.Error as e:
                print(f"   ❌ Error cleaning {table}: {e}")
        
        # Re-enable foreign key checks
        if not dry_run:
            cursor.execute("SET session_replication_role = DEFAULT;")
        
    except psycopg2.Error as e:
        print(f"❌ Database error during cleanup: {e}")
        if not dry_run:
            cursor.execute("SET session_replication_role = DEFAULT;")
    
    finally:
        cursor.close()
    
    return results

def clean_vitals_tables_only(conn: psycopg2.extensions.connection, dry_run: bool = True) -> Dict[str, Any]:
    """Clean only vitals-related tables"""
    vitals_tables = [
        'vitals_raw_categorized',
        'vitals_hourly_aggregates', 
        'vitals_daily_aggregates',
        'vitals_weekly_aggregates',
        'vitals_monthly_aggregates',
        'vitals_sync_status'
    ]
    
    # Get all tables to check which vitals tables exist
    all_tables = get_all_tables(conn)
    existing_vitals_tables = [table for table in vitals_tables if table in all_tables]
    
    if not existing_vitals_tables:
        print("\n✨ No vitals tables found in database!")
        return {'tables_cleaned': 0, 'rows_deleted': 0}
    
    print(f"\n🩺 {'[DRY RUN] ' if dry_run else ''}Cleaning Vitals Tables Only...")
    print(f"   Found {len(existing_vitals_tables)} vitals tables to clean")
    
    # Fix psycopg2.extensions import error by using just "psycopg2" for type hinting
    return clean_database_tables(conn, existing_vitals_tables, dry_run)

def clean_nutrition_tables_only(conn: psycopg2.extensions.connection, dry_run: bool = True) -> Dict[str, Any]:
    """Clean only nutrition-related tables"""
    nutrition_tables = [
        'nutrition_raw_data',
        'nutrition_daily_aggregates',
        'nutrition_weekly_aggregates',
        'nutrition_monthly_aggregates',
        'nutrition_sync_status'
    ]
    
    # Get all tables to check which nutrition tables exist
    all_tables = get_all_tables(conn)
    existing_nutrition_tables = [table for table in nutrition_tables if table in all_tables]
    
    if not existing_nutrition_tables:
        print("\n✨ No nutrition tables found in database!")
        return {'tables_cleaned': 0, 'rows_deleted': 0}
    
    print(f"\n🍽️ {'[DRY RUN] ' if dry_run else ''}Cleaning Nutrition Tables Only...")
    print(f"   Found {len(existing_nutrition_tables)} nutrition tables to clean")
    
    return clean_database_tables(conn, existing_nutrition_tables, dry_run)

def clean_lab_reports_tables_only(conn: psycopg2.extensions.connection, dry_run: bool = True) -> Dict[str, Any]:
    """Clean only lab reports-related tables"""
    lab_reports_tables = [
        'lab_report_categorized',
        'lab_reports_daily',
        'lab_reports_monthly', 
        'lab_reports_quarterly',
        'lab_reports_yearly'
    ]
    
    # Get all tables to check which lab reports tables exist
    all_tables = get_all_tables(conn)
    existing_lab_reports_tables = [table for table in lab_reports_tables if table in all_tables]
    
    if not existing_lab_reports_tables:
        print("\n✨ No lab reports tables found in database!")
        return {'tables_cleaned': 0, 'rows_deleted': 0}
    
    print(f"\n🧪 {'[DRY RUN] ' if dry_run else ''}Cleaning Lab Reports Tables Only...")
    print(f"   Found {len(existing_lab_reports_tables)} lab reports tables to clean")
    
    return clean_database_tables(conn, existing_lab_reports_tables, dry_run)

def main():
    """Main function with interactive menu"""
    print("🧹 Database Cleanup Tool")
    print("=" * 40)
    
    # Default tables to preserve
    DEFAULT_PRESERVE_TABLES = ['users', 'doctors', 'alembic_version']
    
    conn = connect_to_database()
    
    try:
        while True:
            # Get current database stats
            all_tables = get_all_tables(conn)
            row_counts = get_table_row_counts(conn, all_tables)
            
            if not all_tables:
                print("\n✨ No tables found in database!")
                break
            
            print(f"\n🛠️  Cleanup Options:")
            print(f"   1. Clean all tables (preserve users, doctors, alembic_version)")
            print(f"   2. Clean all tables (preserve only users, doctors)")
            print(f"   3. Clean vitals tables only")
            print(f"   4. Clean nutrition tables only")
            print(f"   5. Clean lab reports tables only")
            print(f"   6. View database statistics only")
            print(f"   7. Exit")
            
            choice = input(f"\nSelect option (1-7): ").strip()
            
            if choice == '7':
                print("👋 Goodbye!")
                break
            
            elif choice == '6':
                display_database_stats(all_tables, row_counts, DEFAULT_PRESERVE_TABLES)
                input("\nPress Enter to continue...")
                continue
            
            elif choice == '5':
                # Clean lab reports tables only
                lab_reports_tables = [
                    'lab_report_categorized',
                    'lab_reports_daily',
                    'lab_reports_monthly', 
                    'lab_reports_quarterly',
                    'lab_reports_yearly'
                ]
                existing_lab_reports_tables = [table for table in lab_reports_tables if table in all_tables]
                
                if not existing_lab_reports_tables:
                    print("\n✨ No lab reports tables found in database!")
                    input("Press Enter to continue...")
                    continue
                
                # Display lab reports tables stats
                print(f"\n🧪 Lab Reports Tables Summary:")
                total_lab_reports_rows = 0
                for table in existing_lab_reports_tables:
                    count = row_counts.get(table, 0)
                    total_lab_reports_rows += count
                    print(f"   🗑️  {table}: {count:,} rows")
                
                print(f"\n📈 Total Lab Reports Data to Delete: {total_lab_reports_rows:,} rows")
                
                if total_lab_reports_rows == 0:
                    print("\n✨ All lab reports tables are already empty!")
                    input("Press Enter to continue...")
                    continue
                
                # Confirm and execute
                dry_run = input("\nRun in dry-run mode first? (Y/n): ").strip().lower() != 'n'
                
                results = clean_lab_reports_tables_only(conn, dry_run)
                
                # Display results
                print(f"\n{'🧪 DRY RUN RESULTS:' if dry_run else '✅ LAB REPORTS CLEANUP COMPLETE:'}")
                print(f"   Lab reports tables {'would be' if dry_run else ''} cleaned: {results['tables_cleaned']}")
                print(f"   Lab reports rows {'would be' if dry_run else ''} deleted: {results['rows_deleted']:,}")
                
                if dry_run and results['tables_cleaned'] > 0:
                    confirm = input("\nProceed with actual lab reports cleanup? (y/N): ").strip().lower()
                    if confirm == 'y':
                        print("\n⚠️  FINAL CONFIRMATION ⚠️")
                        print(f"This will PERMANENTLY DELETE {results['rows_deleted']:,} rows from {results['tables_cleaned']} lab reports tables.")
                        final_confirm = input("Type 'DELETE' to confirm: ").strip()
                        
                        if final_confirm == 'DELETE':
                            results = clean_lab_reports_tables_only(conn, False)
                            print(f"\n✅ ACTUAL LAB REPORTS CLEANUP COMPLETE:")
                            print(f"   Lab reports tables cleaned: {results['tables_cleaned']}")
                            print(f"   Lab reports rows deleted: {results['rows_deleted']:,}")
                        else:
                            print("❌ Lab reports cleanup cancelled.")
            
            elif choice == '4':
                # Clean nutrition tables only
                nutrition_tables = [
                    'nutrition_raw_data',
                    'nutrition_daily_aggregates',
                    'nutrition_weekly_aggregates',
                    'nutrition_monthly_aggregates',
                    'nutrition_sync_status'
                ]
                existing_nutrition_tables = [table for table in nutrition_tables if table in all_tables]
                
                if not existing_nutrition_tables:
                    print("\n✨ No nutrition tables found in database!")
                    input("Press Enter to continue...")
                    continue
                
                # Display nutrition tables stats
                print(f"\n🍽️ Nutrition Tables Summary:")
                total_nutrition_rows = 0
                for table in existing_nutrition_tables:
                    count = row_counts.get(table, 0)
                    total_nutrition_rows += count
                    print(f"   🗑️  {table}: {count:,} rows")
                
                print(f"\n📈 Total Nutrition Data to Delete: {total_nutrition_rows:,} rows")
                
                if total_nutrition_rows == 0:
                    print("\n✨ All nutrition tables are already empty!")
                    input("Press Enter to continue...")
                    continue
                
                # Confirm and execute
                dry_run = input("\nRun in dry-run mode first? (Y/n): ").strip().lower() != 'n'
                
                results = clean_nutrition_tables_only(conn, dry_run)
                
                # Display results
                print(f"\n{'🧪 DRY RUN RESULTS:' if dry_run else '✅ NUTRITION CLEANUP COMPLETE:'}")
                print(f"   Nutrition tables {'would be' if dry_run else ''} cleaned: {results['tables_cleaned']}")
                print(f"   Nutrition rows {'would be' if dry_run else ''} deleted: {results['rows_deleted']:,}")
                
                if dry_run and results['tables_cleaned'] > 0:
                    confirm = input("\nProceed with actual nutrition cleanup? (y/N): ").strip().lower()
                    if confirm == 'y':
                        print("\n⚠️  FINAL CONFIRMATION ⚠️")
                        print(f"This will PERMANENTLY DELETE {results['rows_deleted']:,} rows from {results['tables_cleaned']} nutrition tables.")
                        final_confirm = input("Type 'DELETE' to confirm: ").strip()
                        
                        if final_confirm == 'DELETE':
                            results = clean_nutrition_tables_only(conn, False)
                            print(f"\n✅ ACTUAL NUTRITION CLEANUP COMPLETE:")
                            print(f"   Nutrition tables cleaned: {results['tables_cleaned']}")
                            print(f"   Nutrition rows deleted: {results['rows_deleted']:,}")
                        else:
                            print("❌ Nutrition cleanup cancelled.")
            
            elif choice == '3':
                # Clean vitals tables only
                vitals_tables = [
                    'vitals_raw_categorized',
                    'vitals_hourly_aggregates', 
                    'vitals_daily_aggregates',
                    'vitals_weekly_aggregates',
                    'vitals_monthly_aggregates',
                    'vitals_sync_status'
                ]
                existing_vitals_tables = [table for table in vitals_tables if table in all_tables]
                
                if not existing_vitals_tables:
                    print("\n✨ No vitals tables found in database!")
                    input("Press Enter to continue...")
                    continue
                
                # Display vitals tables stats
                print(f"\n🩺 Vitals Tables Summary:")
                total_vitals_rows = 0
                for table in existing_vitals_tables:
                    count = row_counts.get(table, 0)
                    total_vitals_rows += count
                    print(f"   🗑️  {table}: {count:,} rows")
                
                print(f"\n📈 Total Vitals Data to Delete: {total_vitals_rows:,} rows")
                
                if total_vitals_rows == 0:
                    print("\n✨ All vitals tables are already empty!")
                    input("Press Enter to continue...")
                    continue
                
                # Confirm and execute
                dry_run = input("\nRun in dry-run mode first? (Y/n): ").strip().lower() != 'n'
                
                results = clean_vitals_tables_only(conn, dry_run)
                
                # Display results
                print(f"\n{'🧪 DRY RUN RESULTS:' if dry_run else '✅ VITALS CLEANUP COMPLETE:'}")
                print(f"   Vitals tables {'would be' if dry_run else ''} cleaned: {results['tables_cleaned']}")
                print(f"   Vitals rows {'would be' if dry_run else ''} deleted: {results['rows_deleted']:,}")
                
                if dry_run and results['tables_cleaned'] > 0:
                    confirm = input("\nProceed with actual vitals cleanup? (y/N): ").strip().lower()
                    if confirm == 'y':
                        print("\n⚠️  FINAL CONFIRMATION ⚠️")
                        print(f"This will PERMANENTLY DELETE {results['rows_deleted']:,} rows from {results['tables_cleaned']} vitals tables.")
                        final_confirm = input("Type 'DELETE' to confirm: ").strip()
                        
                        if final_confirm == 'DELETE':
                            results = clean_vitals_tables_only(conn, False)
                            print(f"\n✅ ACTUAL VITALS CLEANUP COMPLETE:")
                            print(f"   Vitals tables cleaned: {results['tables_cleaned']}")
                            print(f"   Vitals rows deleted: {results['rows_deleted']:,}")
                        else:
                            print("❌ Vitals cleanup cancelled.")
            
            elif choice in ['1', '2']:
                # Determine preserve tables
                if choice == '1':
                    preserve_tables = DEFAULT_PRESERVE_TABLES
                else:  # choice == '2'
                    preserve_tables = ['users', 'doctors']
                
                # Display what will be affected
                display_database_stats(all_tables, row_counts, preserve_tables)
                
                tables_to_clean = [table for table in all_tables if table not in preserve_tables]
                
                if not tables_to_clean:
                    print("\n✨ No tables to clean!")
                    input("Press Enter to continue...")
                    continue
                
                # Confirm and execute
                dry_run = input("\nRun in dry-run mode first? (Y/n): ").strip().lower() != 'n'
                
                results = clean_database_tables(conn, tables_to_clean, dry_run)
                
                # Display results
                print(f"\n{'🧪 DRY RUN RESULTS:' if dry_run else '✅ CLEANUP COMPLETE:'}")
                print(f"   Tables {'would be' if dry_run else ''} cleaned: {results['tables_cleaned']}")
                print(f"   Rows {'would be' if dry_run else ''} deleted: {results['rows_deleted']:,}")
                
                if dry_run and results['tables_cleaned'] > 0:
                    confirm = input("\nProceed with actual cleanup? (y/N): ").strip().lower()
                    if confirm == 'y':
                        print("\n⚠️  FINAL CONFIRMATION ⚠️")
                        print(f"This will PERMANENTLY DELETE {results['rows_deleted']:,} rows from {results['tables_cleaned']} tables.")
                        final_confirm = input("Type 'DELETE' to confirm: ").strip()
                        
                        if final_confirm == 'DELETE':
                            results = clean_database_tables(conn, tables_to_clean, False)
                            print(f"\n✅ ACTUAL CLEANUP COMPLETE:")
                            print(f"   Tables cleaned: {results['tables_cleaned']}")
                            print(f"   Rows deleted: {results['rows_deleted']:,}")
                        else:
                            print("❌ Cleanup cancelled.")
                
            else:
                print("❌ Invalid option. Please try again.")
            
            input("\nPress Enter to continue...")
            print("\n" + "=" * 50)
    
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Cleanup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
