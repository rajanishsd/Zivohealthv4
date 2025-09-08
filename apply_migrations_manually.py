#!/usr/bin/env python3
import psycopg2
import os
from urllib.parse import urlparse

# Get database URL from environment
db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
if not db_url:
    print('❌ SQLALCHEMY_DATABASE_URI not found in environment')
    exit(1)

print(f'🔗 Connecting to database...')

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

try:
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
    
    # Apply Migration 028: Create nutrition_meal_plans table
    if not meal_plans_exists:
        print('🚀 Applying Migration 028: Creating nutrition_meal_plans table...')
        cur.execute("""
            CREATE TABLE nutrition_meal_plans (
                id SERIAL PRIMARY KEY,
                goal_id INTEGER NOT NULL,
                meal_type VARCHAR(50) NOT NULL,
                meal_name VARCHAR(200) NOT NULL,
                calories_kcal INTEGER,
                protein_g FLOAT,
                carbohydrate_g FLOAT,
                fat_g FLOAT,
                fiber_g FLOAT,
                preparation_time_min INTEGER,
                difficulty VARCHAR(20),
                ingredients TEXT,
                micronutrients TEXT,
                notes TEXT,
                is_recommended BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT fk_nutrition_meal_plans_goal_id 
                    FOREIGN KEY (goal_id) REFERENCES nutrition_goals(id) ON DELETE CASCADE
            );
        """)
        
        # Create indexes
        cur.execute("CREATE INDEX ix_nutrition_meal_plans_goal_id ON nutrition_meal_plans (goal_id);")
        cur.execute("CREATE INDEX ix_nutrition_meal_plans_meal_type ON nutrition_meal_plans (meal_type);")
        
        print('✅ Migration 028 completed: nutrition_meal_plans table created')
    else:
        print('⏭️ Migration 028 skipped: nutrition_meal_plans table already exists')
    
    # Apply Migration 030: Modify meal plans to store JSON strings
    if meal_plans_exists:
        print('🚀 Applying Migration 030: Modifying meal plans to store JSON strings...')
        
        # Drop the existing table and recreate with new structure
        cur.execute("DROP INDEX IF EXISTS ix_nutrition_meal_plans_meal_type;")
        cur.execute("DROP INDEX IF EXISTS ix_nutrition_meal_plans_goal_id;")
        cur.execute("DROP TABLE nutrition_meal_plans;")
        
        # Create new table with simplified structure
        cur.execute("""
            CREATE TABLE nutrition_meal_plans (
                id SERIAL PRIMARY KEY,
                goal_id INTEGER NOT NULL,
                breakfast TEXT,
                lunch TEXT,
                dinner TEXT,
                snacks TEXT,
                recommended_options TEXT,
                total_calories_kcal INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT fk_nutrition_meal_plans_goal_id 
                    FOREIGN KEY (goal_id) REFERENCES nutrition_goals(id) ON DELETE CASCADE
            );
        """)
        
        # Create index
        cur.execute("CREATE INDEX ix_nutrition_meal_plans_goal_id ON nutrition_meal_plans (goal_id);")
        
        print('✅ Migration 030 completed: nutrition_meal_plans table restructured')
    else:
        print('⏭️ Migration 030 skipped: nutrition_meal_plans table does not exist')
    
    # Apply Migration 031: Add goal_id to user_nutrient_focus
    if not goal_id_exists:
        print('🚀 Applying Migration 031: Adding goal_id to user_nutrient_focus...')
        
        # Add goal_id column
        cur.execute("ALTER TABLE user_nutrient_focus ADD COLUMN goal_id INTEGER;")
        
        # Add foreign key constraint
        cur.execute("""
            ALTER TABLE user_nutrient_focus 
            ADD CONSTRAINT fk_user_nutrient_focus_goal_id 
            FOREIGN KEY (goal_id) REFERENCES nutrition_goals(id) ON DELETE CASCADE;
        """)
        
        # Drop the old unique constraint
        cur.execute("ALTER TABLE user_nutrient_focus DROP CONSTRAINT IF EXISTS uq_user_nutrient;")
        
        # Create new unique constraint that includes goal_id
        cur.execute("""
            ALTER TABLE user_nutrient_focus 
            ADD CONSTRAINT uq_user_nutrient_goal 
            UNIQUE (user_id, nutrient_id, goal_id);
        """)
        
        # Create index on goal_id
        cur.execute("CREATE INDEX ix_user_nutrient_focus_goal_id ON user_nutrient_focus (goal_id);")
        
        print('✅ Migration 031 completed: goal_id added to user_nutrient_focus')
    else:
        print('⏭️ Migration 031 skipped: goal_id column already exists')
    
    # Commit all changes
    conn.commit()
    print('✅ All migrations completed successfully!')
    
    # Verify final state
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'nutrition_meal_plans'
        );
    """)
    meal_plans_exists = cur.fetchone()[0]
    
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_nutrient_focus'
            AND column_name = 'goal_id'
        );
    """)
    goal_id_exists = cur.fetchone()[0]
    
    print(f'📊 Final state:')
    print(f'  - nutrition_meal_plans table exists: {meal_plans_exists}')
    print(f'  - user_nutrient_focus.goal_id column exists: {goal_id_exists}')
    
except Exception as e:
    print(f'❌ Error: {e}')
    conn.rollback()
    raise
finally:
    conn.close()
