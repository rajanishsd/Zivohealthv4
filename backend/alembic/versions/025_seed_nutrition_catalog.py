"""seed nutrition objectives and nutrient catalog

Revision ID: 025_seed_nutrition_catalog
Revises: 024_add_nutrition_goals_tables
Create Date: 2025-09-03 00:15:00

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '025_seed_nutrition_catalog'
down_revision: Union[str, None] = '024_add_nutrition_goals_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Seed nutrition objectives
    objectives = [
        ("weight_management", "Weight Management Counseling", "Goal-oriented nutrition for weight management"),
        ("diabetic_diet", "Diabetic Diet Counseling", "Nutrition support for diabetes management"),
        ("weight_gain_diet", "Weight Gain Diet Counseling", "Nutrition support for healthy weight gain"),
        ("therapeutic_diet", "Therapeutic Diets", "Dietary plans for therapeutic needs"),
        ("healthy_skin_diet", "Diet for a Healthy Skin", "Nutrition to support skin health"),
        ("detox_diet", "Detox Diet", "Dietary plans for detoxification support"),
    ]
    for code, name, desc in objectives:
        conn.execute(
            sa.text(
                """
                INSERT INTO nutrition_objectives (code, display_name, description, created_at, updated_at)
                VALUES (:code, :name, :desc, NOW(), NOW())
                ON CONFLICT (code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    updated_at = NOW()
                """
            ),
            {"code": code, "name": name, "desc": desc}
        )

    # Seed nutrient catalog based on NutritionRawData columns
    nutrients = [
        # Macronutrients & energy
        ("calories", "Calories", "macronutrient", "kcal"),
        ("protein_g", "Protein", "macronutrient", "g"),
        ("fat_g", "Fat", "macronutrient", "g"),
        ("carbs_g", "Carbohydrates", "macronutrient", "g"),
        ("fiber_g", "Fiber", "macronutrient", "g"),
        ("sugar_g", "Sugar", "macronutrient", "g"),
        ("sodium_mg", "Sodium", "mineral", "mg"),
        # Vitamins
        ("vitamin_a_mcg", "Vitamin A", "vitamin", "mcg"),
        ("vitamin_c_mg", "Vitamin C", "vitamin", "mg"),
        ("vitamin_d_mcg", "Vitamin D", "vitamin", "mcg"),
        ("vitamin_e_mg", "Vitamin E", "vitamin", "mg"),
        ("vitamin_k_mcg", "Vitamin K", "vitamin", "mcg"),
        ("vitamin_b1_mg", "Vitamin B1 (Thiamine)", "vitamin", "mg"),
        ("vitamin_b2_mg", "Vitamin B2 (Riboflavin)", "vitamin", "mg"),
        ("vitamin_b3_mg", "Vitamin B3 (Niacin)", "vitamin", "mg"),
        ("vitamin_b6_mg", "Vitamin B6", "vitamin", "mg"),
        ("vitamin_b12_mcg", "Vitamin B12", "vitamin", "mcg"),
        ("folate_mcg", "Folate", "vitamin", "mcg"),
        # Minerals
        ("calcium_mg", "Calcium", "mineral", "mg"),
        ("iron_mg", "Iron", "mineral", "mg"),
        ("magnesium_mg", "Magnesium", "mineral", "mg"),
        ("phosphorus_mg", "Phosphorus", "mineral", "mg"),
        ("potassium_mg", "Potassium", "mineral", "mg"),
        ("zinc_mg", "Zinc", "mineral", "mg"),
        ("copper_mg", "Copper", "mineral", "mg"),
        ("manganese_mg", "Manganese", "mineral", "mg"),
        ("selenium_mcg", "Selenium", "mineral", "mcg"),
    ]

    for key, name, category, unit in nutrients:
        conn.execute(
            sa.text(
                """
                INSERT INTO nutrition_nutrient_catalog (key, display_name, category, unit, is_enabled, created_at, updated_at)
                VALUES (:key, :name, :category, :unit, TRUE, NOW(), NOW())
                ON CONFLICT (key) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    category = EXCLUDED.category,
                    unit = EXCLUDED.unit,
                    is_enabled = TRUE,
                    updated_at = NOW()
                """
            ),
            {"key": key, "name": name, "category": category, "unit": unit}
        )


def downgrade() -> None:
    # Remove seeded objectives
    op.execute(
        sa.text(
            """
            DELETE FROM nutrition_objectives
            WHERE code IN (
                'weight_management','diabetic_diet','weight_gain_diet','therapeutic_diet','healthy_skin_diet','detox_diet'
            )
            """
        )
    )
    # Remove seeded nutrients
    keys = [
        'calories','protein_g','fat_g','carbs_g','fiber_g','sugar_g','sodium_mg',
        'vitamin_a_mcg','vitamin_c_mg','vitamin_d_mcg','vitamin_e_mg','vitamin_k_mcg','vitamin_b1_mg','vitamin_b2_mg','vitamin_b3_mg','vitamin_b6_mg','vitamin_b12_mcg','folate_mcg',
        'calcium_mg','iron_mg','magnesium_mg','phosphorus_mg','potassium_mg','zinc_mg','copper_mg','manganese_mg','selenium_mcg'
    ]
    op.execute(
        sa.text(
            "DELETE FROM nutrition_nutrient_catalog WHERE key = ANY(:keys)"
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": keys}
    )


