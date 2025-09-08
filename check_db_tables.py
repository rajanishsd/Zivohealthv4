#!/usr/bin/env python3
import psycopg2
import os
from urllib.parse import urlparse

# Get database URL from environment
db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
if not db_url:
    print('❌ SQLALCHEMY_DATABASE_URI not found in environment')
    exit(1)

print(f'🔗 Database URL: {db_url[:50]}...')

# Parse the URL
parsed = urlparse(db_url)
conn = psycopg2.connect(
    host=parsed.hostname,
    port=parsed.port,
    database=parsed.path[1:],
    user=parsed.username,
    password=parsed.password
)

cur = conn.cursor()

# Check if nutrition_meal_plans table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'nutrition_meal_plans'
    );
""")
meal_plans_exists = cur.fetchone()[0]
print(f'📋 nutrition_meal_plans table exists: {meal_plans_exists}')

# Check if user_nutrient_focus has goal_id column
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_nutrient_focus'
        AND column_name = 'goal_id'
    );
""")
goal_id_exists = cur.fetchone()[0]
print(f'📋 user_nutrient_focus.goal_id column exists: {goal_id_exists}')

# Show all nutrition-related tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%nutrition%' OR table_name LIKE '%meal%' OR table_name LIKE '%user_nutrient%')
    ORDER BY table_name;
""")
tables = cur.fetchall()
print('📋 Nutrition-related tables:')
for table in tables:
    print(f'  - {table[0]}')

# Show table structure for nutrition_meal_plans if it exists
if meal_plans_exists:
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'nutrition_meal_plans'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    print('📋 nutrition_meal_plans table structure:')
    for col in columns:
        print(f'  - {col[0]}: {col[1]} (nullable: {col[2]})')

conn.close()
print('✅ Database check completed!')
