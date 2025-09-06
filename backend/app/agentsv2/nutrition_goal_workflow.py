"""
Nutritional Goal Workflow (agentsv2, placeholders)

Three nodes:
- collect_and_update_data
- prepare_nutrition_goal
- set_nutrition_goal
"""

from __future__ import annotations

from typing import Dict, Any, Optional, TypedDict
from uuid import uuid4
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.core.config import settings
from app.core.database_utils import get_raw_db_connection
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import json
import re
from app.agentsv2.nutrition_agent import NutritionAgentLangGraph
from app.agentsv2.tools.nutrition_tools import internet_search_tool
from app.agentsv2.tools.url_reader_tool import fetch_and_read_url
from app.agentsv2.customer_workflow import ask_user_question


class NutritionalGoalState(TypedDict):
    request_id: str
    user_id: int
    session_id: Optional[int]
    request_data: Dict[str, Any]
    collected_context: Dict[str, Any]
    proposed_goal: Dict[str, Any]
    set_goal_result: Dict[str, Any]
    collect_done: bool
    prepare_done: bool
    set_done: bool
    error_message: Optional[str]


class NutritionalGoalWorkflow:
    def __init__(self, nutrition_agent_instance: NutritionAgentLangGraph | None = None):
        self.memory = MemorySaver()
        self.workflow = self._build_workflow()
        # Prefer injected instance; otherwise create a local one
        self.nutrition_agent = nutrition_agent_instance or NutritionAgentLangGraph()

    def _build_workflow(self):
        g = StateGraph(NutritionalGoalState)
        g.add_node("collect_and_update_data", self.collect_and_update_data)
        g.add_node("prepare_nutrition_goal", self.prepare_nutrition_goal)
        g.add_node("set_nutrition_goal", self.set_nutrition_goal)
        g.add_node("set_nutrition_targets", self.set_nutrition_targets)
        g.add_node("set_nutrition_meal_plans", self.set_nutrition_meal_plans)
        g.add_node("handle_error", self.handle_error)

        g.add_edge(START, "collect_and_update_data")
        g.add_conditional_edges(
            "collect_and_update_data",
            self.route_after_collect,
            {"ok": "prepare_nutrition_goal", "error": "handle_error"},
        )
        g.add_conditional_edges(
            "prepare_nutrition_goal",
            self.route_after_prepare,
            {"ok": "set_nutrition_goal", "error": "set_nutrition_goal"},
        )
        g.add_conditional_edges(
            "set_nutrition_goal",
            self.route_after_set_goal,
            {"ok": "set_nutrition_targets", "error": "handle_error"},
        )
        g.add_conditional_edges(
            "set_nutrition_targets",
            self.route_after_set_targets,
            {"ok": "set_nutrition_meal_plans", "error": "handle_error"},
        )
        g.add_conditional_edges(
            "set_nutrition_meal_plans",
            self.route_after_set_meal_plans,
            {"ok": END, "error": "handle_error"},
        )
        g.add_edge("handle_error", END)
        return g.compile(checkpointer=self.memory)

    def route_after_collect(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("collect_done") else "error"

    def route_after_prepare(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("prepare_done") else "error"

    def route_after_set_goal(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("goal_created") else "error"
    
    def route_after_set_targets(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("targets_created") else "error"
    
    def route_after_set_meal_plans(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("meal_plans_created") else "error"

    async def run(self, initial: NutritionalGoalState) -> NutritionalGoalState:
        return await self.workflow.ainvoke(initial, config={"configurable": {"thread_id": initial["request_id"]}})

    async def collect_and_update_data(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Gather user profile and context for diet planning using a ReAct agent that
        prefers tools (DB first) and then asks clarifying questions, modeled after
        assess_user_intent in customer_workflow.
        """
        user_id = state["user_id"]
        session_id = state.get("session_id")
        request = state.get("request_data", {})
        objective = request.get("original_prompt", "unspecified")
        # Preseed from request if present
        preseed_goal_name = request.get("goal_name") or objective
        preseed_goal_description = request.get("goal_description") or request.get("notes")

        collected: Dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "requested_objective": objective,
            "survey_responses": {},
            "goal_name": preseed_goal_name,
            "goal_description": preseed_goal_description
        }
        if session_id and user_id:
            @tool
            async def ask_clarifying_questions(questions: str) -> str:
                """Ask the user multiple clarifying questions and return their responses organized by category.
                
                Args:
                    questions: A string containing multiple questions separated by newlines, with category prefixes like "PERSONAL_DEMOGRAPHICS: What is your age?"
                
                Returns:
                    JSON string with all responses organized by category
                """
                import json
                
                # Split questions by newlines
                question_list = [q.strip() for q in questions.split('\n') if q.strip()]
                
                if not question_list:
                    question_list = [questions.strip()]
                
                responses = {}
                for question in question_list:
                    # Parse category and question
                    if ':' in question:
                        category, question_text = question.split(':', 1)
                        category = category.strip().lower()
                        question_text = question_text.strip()
                    else:
                        category = "general"
                        question_text = question
                    
                    if question_text and not question_text.endswith('?'):
                        question_text += '?'
                    
                    print(f"🤖 Agent asked: {question_text}")
                    response = await ask_user_question(question_text, session_id, str(user_id))
                    print(f"👤 User responded: {response}")
                    
                    # Organize by category
                    if category not in responses:
                        responses[category] = {}
                    
                    # Create a key for the response (use part of the question as key)
                    key = question_text.lower().replace('?', '').replace(' ', '_')[:30]
                    responses[category][key] = {
                        "question": question_text,
                        "response": response
                    }
                
                return json.dumps(responses)

            # Reuse nutrition agent's own DB tools (query_nutrition_db, describe_nutrition_table_schema)
            #nutrition_tools = getattr(self.nutrition_agent, "tools", []) or []
            tools = [ask_clarifying_questions] 
            try:
                llm = ChatOpenAI(model=getattr(settings, 'CUSTOMER_AGENT_MODEL', None) or getattr(settings, 'DEFAULT_AI_MODEL', 'gpt-4o-mini'), openai_api_key=settings.OPENAI_API_KEY)
                agent = create_react_agent(model=llm, tools=tools, prompt=None)

                system = (
                    "ROLE:\n"
                    "You are a senior nutrition onboarding agent. Your task is to gather all necessary user inputs "
                    "to build a diet plan for the objective: '" + objective + "'.\n\n"
                    "TOOLS:\n"
                    "- ask_clarifying_questions: ask the user multiple questions at once (separated by newlines). The function will ask them one by one and return all responses.\n\n"
                    
                    "STRATEGY:\n"
                    "1) Use ask_clarifying_questions to provide ALL questions at once (separated by newlines). The function handles asking them individually and returns responses organized by category.\n"
                    "2) Parse the returned JSON responses and map them to the appropriate JSON output categories (personal_demographics, health_medical_profile, etc.).\n"
                    "3) Do NOT ask for values that should be computed (BMI, BMR, TDEE, body fat %). Compute them from available data.\n"
                    "4) Calculate waist-to-hip ratio: if both waist and hip measurements are provided, calculate waist_circumference_cm / hip_circumference_cm. If either is missing, set waist_to_hip_ratio to null.\n"
                    "5) Calculate BMR using Mifflin-St Jeor Equation: Men: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) + 5; Women: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) - 161\n"
                    "6) Calculate TDEE by multiplying BMR by activity factor: Sedentary (1.2), Lightly active (1.375), Moderately active (1.55), Very active (1.725), Extremely active (1.9)\n"
                    "7) Calculate body fat percentage using available data:\n"
                    "   - If waist and hip measurements available: Navy method (Men: BF% = 86.010 × log10(waist - neck) - 70.041 × log10(height) + 36.76; Women: BF% = 163.205 × log10(waist + hip - neck) - 97.684 × log10(height) - 78.387)\n"
                    "   - If only BMI available: Use BMI-based estimation (Men: BF% ≈ (1.20 × BMI) + (0.23 × age) - 16.2; Women: BF% ≈ (1.20 × BMI) + (0.23 × age) - 5.4)\n"
                    "   - If insufficient data: set to null\n"
                    "8) When enough information is collected, return ONLY a single JSON object following the OUTPUT FORMAT.\n\n"
                    "9) Below questions are some of the questions, you need to modify them based on the user objective and add new questions based on the user objective or remove from the below questions."
                    "REQUIRED INFORMATION (provide ALL these questions to ask_clarifying_questions at once, separated by newlines):\n"
                    "PERSONAL_DEMOGRAPHICS: What is your age?\n"
                    "PERSONAL_DEMOGRAPHICS: What is your gender?\n"
                    "PERSONAL_DEMOGRAPHICS: What is your height in centimeters?\n"
                    "PERSONAL_DEMOGRAPHICS: What is your current weight in kilograms?\n"
                    "PERSONAL_DEMOGRAPHICS: What is your waist circumference in centimeters? (optional)\n"
                    "PERSONAL_DEMOGRAPHICS: What is your hip circumference in centimeters? (optional)\n"
                    "PERSONAL_DEMOGRAPHICS: What is your neck circumference in centimeters? (optional)\n"
                    "HEALTH_MEDICAL_PROFILE: How would you describe your current health status?\n"
                    "HEALTH_MEDICAL_PROFILE: Do you have any past medical history or chronic conditions?\n"
                    "HEALTH_MEDICAL_PROFILE: Is there any family history of chronic illnesses?\n"
                    "HEALTH_MEDICAL_PROFILE: What medications and supplements are you currently taking?\n"
                    "HEALTH_MEDICAL_PROFILE: Do you have any food allergies or intolerances?\n"
                    "HEALTH_MEDICAL_PROFILE: Do you have recent lab reports or blood test results?\n"
                    "GOALS_OBJECTIVES: What is your primary nutrition goal?\n"
                    "GOALS_OBJECTIVES: What are your secondary health goals?\n"
                    "GOALS_OBJECTIVES: What is your expected timeframe for achieving these goals?\n"
                    "GOALS_OBJECTIVES: When do you want to start this nutrition plan? (e.g., immediately, next week, specific date)\n"
                    "GOALS_OBJECTIVES: What is your target completion date or duration for achieving your goals?\n"
                    "LIFESTYLE_ACTIVITY: What does your typical daily routine look like?\n"
                    "LIFESTYLE_ACTIVITY: How would you describe your physical activity level?\n"
                    "LIFESTYLE_ACTIVITY: What type of exercise do you do regularly?\n"
                    "LIFESTYLE_ACTIVITY: How often and for how long do you exercise?\n"
                    "LIFESTYLE_ACTIVITY: What type of work do you do?\n"
                    "DIETARY_HABITS_PREFERENCES: How many meals and snacks do you typically have per day?\n"
                    "DIETARY_HABITS_PREFERENCES: What are your typical foods and cooking methods?\n"
                    "DIETARY_HABITS_PREFERENCES: What is your dietary preference?\n"
                    "DIETARY_HABITS_PREFERENCES: What foods do you like and dislike?\n"
                    "DIETARY_HABITS_PREFERENCES: What is your food budget and accessibility situation?\n"
                    "DIETARY_HABITS_PREFERENCES: Do you cook at home or eat out frequently?\n"
                    "DIETARY_HABITS_PREFERENCES: Do you consume alcohol, smoke, or drink caffeine?\n"
                    "BODY_COMPOSITION_METABOLISM: How much water do you drink per day?\n"
                    "PSYCHOLOGICAL_BEHAVIORAL: How motivated are you to make dietary changes?\n"
                    "PSYCHOLOGICAL_BEHAVIORAL: Do you have any emotional eating patterns?\n"
                    "PSYCHOLOGICAL_BEHAVIORAL: Have you tried dieting before? What worked or didn't work?\n"
                    "PSYCHOLOGICAL_BEHAVIORAL: Do you have a support system for your health goals?\n"
                    "SPECIAL_CONSIDERATIONS: Do you have any religious or cultural dietary restrictions?\n"
                    "SPECIAL_CONSIDERATIONS: Do you travel frequently or eat out often?\n"
                    "SPECIAL_CONSIDERATIONS: Are there any seasonal or local food availability concerns?\n"
                    "SPECIAL_CONSIDERATIONS: Do you have any specific health concerns?\n\n"
                    "OUTPUT FORMAT (return ONLY JSON; no commentary): Capture all the units for the values in the JSON.\n"
                    "{\n"
                    "  \"personal_demographics\": { \"age\": number, \"gender\": string, \"height_cm\": number, \"weight_kg\": number, \"waist_circumference_cm\": number | null, \"hip_circumference_cm\": number | null, \"neck_circumference_cm\": number | null, \"waist_to_hip_ratio\": number | null, \"bmi\": number, \"bmr_kcal\": number, \"tdee_kcal\": number, \"body_fat_percentage\": number | null },\n"
                    "  \"health_medical_profile\": { ... },\n"
                    "  \"goals_objectives\": { \"goal_name: Derive this from the user input objective\": string, \"goal_description: Derive this from the user input objective\": string, \"primary_goal\": string | null, \"secondary_goals\": [string], \"start_date\": string, \"target_completion_date\": string, \"timeframe_duration\": string },\n"
                    "  \"lifestyle_activity\": { ... },\n"
                    "  \"dietary_habits_preferences\": { ... },\n"
                    "  \"body_composition_metabolism\": { ... },\n"
                    "  \"psychological_behavioral\": { ... },\n"
                    "  \"special_considerations\": { ... }\n"
                    "}"
                )

                user_instruction = (
                    "Collect missing information required to prepare a nutrition plan for the given objective.\n"
                    "Use ask_clarifying_questions to provide ALL questions at once (separated by newlines). The function will ask them one by one and return responses organized by category.\n"
                    "Parse the returned responses and map them to the appropriate JSON output categories.\n"
                    "Return ONLY a single JSON object with the category headings exactly as specified. Ensure \"goals_objectives\" includes \"goal_name\" and \"goal_description\" derived from user context and clarifications and dont ask question on this"
                )

                result = await agent.ainvoke(
                    {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                    {"return_intermediate_steps": True, "recursion_limit": 100, "configurable": {"thread_id": state.get("request_id")}}
                )

                # Try to extract JSON from the agent's final message
                final_msg = result.get("messages", [])[-1]
                final_content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
                parsed = None
                try:
                    m = re.search(r"\{[\s\S]*\}", final_content)
                    if m:
                        parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None
                if parsed:
                    # Try to extract goal_name and goal_description early
                    goal_name = None
                    goal_description = None
                    try:
                        goals_obj = parsed.get("goals_objectives") if isinstance(parsed, dict) else None
                        if isinstance(goals_obj, dict):
                            goal_name = goals_obj.get("goal_name") or goals_obj.get("primary_goal") or goals_obj.get("objective")
                            goal_description = goals_obj.get("goal_description") or goals_obj.get("notes")
                    except Exception:
                        pass
                    if goal_name:
                        collected["goal_name"] = str(goal_name)
                    if goal_description:
                        collected["goal_description"] = str(goal_description)
                    collected["survey_responses"]["structured"] = parsed
                else:
                    collected["survey_responses"]["raw"] = final_content
            except Exception as e:
                collected["survey_responses"]["error"] = str(e)
                state["error_message"] = f"Collection agent error: {e}"

        state["collected_context"] = collected
        # Only mark collect_done when we have at least some structured/parsed data or raw text, otherwise signal error
        survey = collected.get("survey_responses", {})
        state["collect_done"] = bool(survey.get("structured") or survey.get("raw"))
        if not state["collect_done"]:
            state["error_message"] = "Collection agent produced no usable output (likely tool limit)."
        return state

    async def prepare_nutrition_goal(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Use an agent with internet_search_tool and ask_clarifying_question to fetch ICMR-NIN RDAs
        and produce a structured JSON with daily nutrient needs and a daily meal plan.
        """
        objective = state.get("request_data", {}).get("original_prompt", "unspecified")
        user_id = state["user_id"]
        session_id = state.get("session_id")
        collected_context = state.get("collected_context", {})

        # Tools: ask clarifying questions (one at a time) and internet search
        tools = []
        if session_id and user_id:
            @tool
            async def ask_clarifying_question(question: str) -> str:
                """Ask the user a clarifying question and return their response."""
                return await ask_user_question(question, session_id, str(user_id))
            tools.append(ask_clarifying_question)

        @tool
        async def query_nutrient_catalog() -> str:
            """Query the nutrition_nutrient_catalog table to get valid nutrient IDs and names.
            
            Returns:
                JSON string with nutrient catalog data
            """
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                import json
                
                with get_raw_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        query = "SELECT id, key, display_name, unit, category FROM nutrition_nutrient_catalog ORDER BY id"
                        cursor.execute(query)
                        results = cursor.fetchall()
                        
                        nutrients = []
                        for row in results:
                            nutrients.append({
                                "id": row["id"],
                                "key": row["key"],
                                "display_name": row["display_name"],
                                "unit": row["unit"],
                                "category": row["category"]
                            })
                        
                        return json.dumps({"success": True, "nutrients": nutrients})
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        tools.append(query_nutrient_catalog)

        #tools.append(internet_search_tool)
        # Add URL reader to fetch PDF/HTML content from search results
        #tools.append(fetch_and_read_url)

        llm = ChatOpenAI(
            model=getattr(settings, 'CUSTOMER_AGENT_MODEL', None) or getattr(settings, 'DEFAULT_AI_MODEL', 'gpt-4o-mini'),
            openai_api_key=settings.OPENAI_API_KEY
        )
        agent = create_react_agent(model=llm, tools=tools, prompt=None)

        context_blob = json.dumps({
            "objective": objective,
            "collected_context": collected_context
        }, default=str)

        RDA_SOURCE = """1. Energy (Calories per Day)(varies with activity level – sedentary / moderate / active)
                    Infants (0–12 months): 500–700 kcal
                    Children 1–3 yrs: 900–1000 kcal
                    Children 4–8 yrs: 1200–1400 kcal
                    Boys 9–13 yrs: 1600–2000 kcal
                    Girls 9–13 yrs: 1400–1800 kcal
                    Boys 14–18 yrs: 2200–2800 kcal
                    Girls 14–18 yrs: 1800–2200 kcal
                    Men 19–30 yrs: 2400–3000 kcal
                    Women 19–30 yrs: 2000–2400 kcal
                    Men 31–50 yrs: 2200–3000 kcal
                    Women 31–50 yrs: 1800–2200 kcal
                    Adults 51+ yrs: Men ~2000–2600 kcal, Women ~1600–2000 kcal

            2. Macronutrients
                Protein: ~0.8–1.0 g per kg body weight (higher for athletes/pregnancy/elderly → up to 1.2–1.6 g/kg)
                Fat: 20–35% of total calories (focus on unsaturated fats, limit saturated/trans fats)
                Carbohydrates: 45–65% of total calories (prefer whole grains, fruits, vegetables)
                Fiber:
                Children: 14–25 g/day
                Adults: 25 g/day (women), 30–38 g/day (men)

            3. Micronutrients (Highlights by Age Group)
                Children (1–8 yrs)
                Calcium: 700–1000 mg
                Iron: 7–10 mg
                Vitamin D: 600 IU (15 mcg)
                Vitamin A: 300–400 mcg

                Adolescents (9–18 yrs)
                Calcium: 1300 mg (peak bone growth)
                Iron: 8–11 mg (boys), 15 mg (girls due to menstruation)
                Vitamin D: 600 IU
                Protein needs increase

                Adults (19–50 yrs)
                Calcium: 1000 mg
                Iron: 8 mg (men), 18 mg (women until menopause)
                Vitamin D: 600 IU
                Vitamin B12: 2.4 mcg
                Folate: 400 mcg

                Older Adults (51+ yrs)
                Calcium: 1200 mg
                Iron: 8 mg (men & women post-menopause)
                Vitamin D: 800 IU (higher due to bone health)
                B12: 2.4 mcg (absorption decreases with age)

                Pregnancy & Lactation
                Extra ~300–450 kcal/day
                Protein: +25 g/day
                Iron: 27 mg/day
                Folate: 600 mcg/day
                Calcium: 1000–1200 mg/day
                Vitamin D: 600 IU"""
                
        system = (
            "ROLE\n"
            "You are a registered dietician assistant. Build nutrition targets and a daily meal plan using ICMR–NIN (India) RDAs.\n\n"
            "TOOLS\n"
            "- query_nutrient_catalog: Query the database to get valid nutrient names and IDs\n"
            "- ask_clarifying_question: if critical demographic/activity assumptions are missing, ask ONE question at a time.\n\n"
            "REQUIREMENTS\n"
            f"- Use {RDA_SOURCE} as the authoritative RDA reference\n"
            "- FIRST: Call query_nutrient_catalog to get the exact nutrient names from the database\n"
            "- Use ONLY the nutrient names returned from the catalog in your daily_rda response\n"
            "- If multiple editions exist, choose the most recent. Include citation URLs.\n"
            "- Compute BMI/BMR/TDEE from available data. Do not ask for them.\n"
            "- Extract timing information (start_date, target_completion_date, timeframe_duration) from the collected context and include in the timing section of your response.\n"
            "- Convert relative dates to exact dates: 'immediately' = today's date, '6 months from now' = today + 6 months, etc.\n"
            "- Format dates as ISO strings (YYYY-MM-DD) for database storage.\n"
            "- Only ask the user when essential information is missing (one question at a time).\n\n"
            "OUTPUT FORMAT (return ONLY JSON; no commentary)\n"
            "{\n"
            "  \"assumptions\": {\n"
            "    \"objective\": string,\n"
            "    \"age\": number | null,\n"
            "    \"gender\": string | null,\n"
            "    \"height_cm\": number | null,\n"
            "    \"weight_kg\": number | null,\n"
            "    \"bmi\": number | null,\n"
            "    \"activity_level\": string | null\n"
            "  },\n"
            "  \"timing\": {\n"
            "    \"start_date\": \"YYYY-MM-DD\",\n"
            "    \"target_completion_date\": \"YYYY-MM-DD\",\n"
            "    \"timeframe_duration\": string\n"
            "  },\n"
            "  \"daily_rda\": {\n"
            "    \"calories\": number,\n"
            "    \"macronutrients\": { \"protein_g\": number, \"carbs_g\": number, \"fat_g\": number, \"fiber_g\": number },\n"
            "    \"vitamins\": { \"vitamin_a_mcg\": number, \"vitamin_b1_mg\": number, \"vitamin_b2_mg\": number, \"vitamin_b3_mg\": number, \"vitamin_b6_mg\": number, \"vitamin_b12_mcg\": number, \"vitamin_c_mg\": number, \"vitamin_d_mcg\": number, \"vitamin_e_mg\": number, \"vitamin_k_mcg\": number, \"folate_mcg\": number },\n"
            "    \"minerals\": { \"calcium_mg\": number, \"iron_mg\": number, \"magnesium_mg\": number, \"potassium_mg\": number, \"sodium_mg\": number, \"zinc_mg\": number, \"selenium_mcg\": number, \"phosphorus_mg\": number, \"copper_mg\": number, \"manganese_mg\": number }\n"
            "  },\n"
            "  \"daily_meal_plan\": {\n"
            "    \"breakfast\": {\n"
            "      \"options\": [ { \"name\": string, \"calories\": number, \"macros\": { \"protein_g\": number, \"carbs_g\": number, \"fat_g\": number, \"fiber_g\": number }, \"micronutrients\": { ... }, \"ingredients\": [string], \"preparation_time_min\": number, \"difficulty\": string, \"notes\": string } ],\n"
            "      \"recommended_option\": number,\n"
            "      \"total_calories_kcal\": number\n"
            "    },\n"
            "    \"lunch\": {\n"
            "      \"options\": [ { ... } ],\n"
            "      \"recommended_option\": number,\n"
            "      \"total_calories_kcal\": number\n"
            "    },\n"
            "    \"dinner\": {\n"
            "      \"options\": [ { ... } ],\n"
            "      \"recommended_option\": number,\n"
            "      \"total_calories_kcal\": number\n"
            "    },\n"
            "    \"snacks\": {\n"
            "      \"options\": [ { ... } ],\n"
            "      \"recommended_option\": number,\n"
            "      \"total_calories_kcal\": number\n"
            "    }\n"
            "  },\n"
            "  \"notes\": string\n"
            "}"
        )

        user_instruction = (
            "Context: " + context_blob + "\n" \
            "Task: FIRST call query_nutrient_catalog to get the exact nutrient names from the database, then use those names in your daily_rda response. "
            "Use the ICMR-NIN RDA reference provided to calculate appropriate values for each nutrient. "
            "If any essential demographic/activity assumption is missing, ask one clarifying question at a time. "
            "For the meal plan, provide multiple options for each meal (breakfast, lunch, dinner, snacks) based on the user's dietary preferences, cooking facilities, budget, and cultural preferences collected in the previous step. "
            "Each meal should have 2-3 different options with varying preparation time, difficulty, and ingredients. "
            "Dont ask more then 5 clarifying questions, if user is not providing the information then assume relevant information and proceed with the meal plan. "
            "Mark one option as recommended (index 0, 1, or 2) based on the user's profile. "
            "Return ONLY the JSON in the specified schema."
        )

        try:
            result = await agent.ainvoke(
                {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                {"return_intermediate_steps": True, "recursion_limit": 45, "configurable": {"thread_id": state.get("request_id")}}
            )

            final_msg = result.get("messages", [])[-1]
            final_content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
            parsed = None
            try:
                m = re.search(r"\{[\s\S]*\}", final_content)
                if m:
                    parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

            if parsed:
                state["proposed_goal"] = parsed
            else:
                state["proposed_goal"] = {
                    "assumptions": {},
                    "daily_rda": {},
                    "daily_meal_plan": {},
                    "timing": {},
                    "notes": "Agent did not return valid JSON"
                }
        except Exception as e:
            state["proposed_goal"] = {
                "assumptions": {},
                "daily_rda": {},
                "daily_meal_plan": {},
                "timing": {},
                "notes": f"Error preparing nutrition goal: {e}"
            }

        state["prepare_done"] = bool(state.get("proposed_goal", {}).get("daily_rda"))
        return state

    async def set_nutrition_goal(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Create the nutrition goal record in the database."""
        user_id = state["user_id"]
        session_id = state.get("session_id")
        proposed_goal = state.get("proposed_goal", {})
        collected_context = state.get("collected_context", {})

        # Tools: ask clarifying questions and generic database update
        tools = []
        if session_id and user_id:
            @tool
            async def ask_clarifying_question(question: str) -> str:
                """Ask the user a clarifying question and return their response."""
                return await ask_user_question(question, session_id, str(user_id))
            tools.append(ask_clarifying_question)

        @tool
        async def query_nutrient_catalog() -> str:
            """Query the nutrition_nutrient_catalog table to get valid nutrient IDs and names.
            
            Returns:
                JSON string with nutrient catalog data
            """
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                import json
                
                with get_raw_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        query = "SELECT id, key, display_name, unit, category FROM nutrition_nutrient_catalog ORDER BY id"
                        cursor.execute(query)
                        results = cursor.fetchall()
                        
                        nutrients = []
                        for row in results:
                            nutrients.append({
                                "id": row["id"],
                                "key": row["key"],
                                "display_name": row["display_name"],
                                "unit": row["unit"],
                                "category": row["category"]
                            })
                        
                        return json.dumps({"success": True, "nutrients": nutrients})
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})

        @tool
        async def create_nutrition_goal(goals_data: str) -> str:
            """Create nutrition goal record in the database.
            
            Args:
                goals_data: JSON string containing nutrition_goals record
                
            Returns:
                JSON string with operation results
            """
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                import json
                from datetime import datetime
                
                def serialize_datetime(obj):
                    """Custom JSON serializer for datetime objects"""
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
                
                results = {"success": True, "goal_id": None, "errors": []}
                
                with get_raw_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Insert nutrition_goals record
                        goals_dict = json.loads(goals_data)
                        
                        # Handle datetime fields
                        for key, value in goals_dict.items():
                            if isinstance(value, str) and key in ['effective_at', 'expires_at', 'created_at', 'updated_at']:
                                try:
                                    goals_dict[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                except (ValueError, AttributeError):
                                    pass
                        
                        columns = list(goals_dict.keys())
                        values = list(goals_dict.values())
                        placeholders = ', '.join(['%s'] * len(values))
                        query = f"INSERT INTO nutrition_goals ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
                        cursor.execute(query, values)
                        goal_result = cursor.fetchone()
                        results["goal_id"] = goal_result["id"] if goal_result else None
                        
                        if not results["goal_id"]:
                            results["errors"].append("Failed to create nutrition goal")
                            results["success"] = False
                        
                        return json.dumps(results, default=serialize_datetime)
                
            except Exception as e:
                return json.dumps({"success": False, "goal_id": None, "errors": [str(e)]})
        
        tools.append(create_nutrition_goal)

        llm = ChatOpenAI(
            model=getattr(settings, 'CUSTOMER_AGENT_MODEL', None) or getattr(settings, 'DEFAULT_AI_MODEL', 'gpt-4o-mini'),
            openai_api_key=settings.OPENAI_API_KEY
        )
        agent = create_react_agent(model=llm, tools=tools, prompt=None)

        context_blob = json.dumps({
            "user_id": user_id,
            "proposed_goal": proposed_goal,
            "collected_context": collected_context
        }, default=str)

        system = (
            "ROLE\n"
            f"You are a database specialist for nutrition goals. Parse the proposed goal data and store it in the appropriate database tables for the user{user_id}.\n\n"
            "AVAILABLE TABLES:\n"
            "- nutrition_goals: Store user's active nutrition goal\n"
            "- nutrition_goal_targets: Store specific nutrient targets for the goal\n"
            "- user_nutrient_focus: Store user's primary/secondary nutrient priorities\n"
            "- nutrition_meal_plans: Store generated meal plans for the goal\n"
            "- nutrition_nutrient_catalog: System nutrient catalog (read-only)\n\n"
            "TABLE SCHEMAS:\n"
            "nutrition_goals: { user_id, goal_name, goal_description, status, effective_at, expires_at, created_at, updated_at}\n"
            "nutrition_goal_targets: { goal_id, nutrient_id, timeframe, target_type, target_min, target_max, priority, is_active, created_at, updated_at}\n"
            "user_nutrient_focus: { user_id, nutrient_id, priority, is_active, created_at, updated_at}\n"
            "nutrition_meal_plans: { goal_id, breakfast, lunch, dinner, snacks, recommended_options, total_calories_kcal, created_at, updated_at}\n\n"
            "OPERATIONS:\n"
            "- query_nutrient_catalog: Query the nutrition_nutrient_catalog table to get valid nutrient IDs\n"
            "- batch_insert_nutrition_data: Use this function ONCE to insert all data in batch\n"
            "- ask_clarifying_question: Ask user ONLY if absolutely critical information is missing\n\n"
            "IMPORTANT: \n"
            "- Do NOT ask multiple clarifying questions. If nutrient IDs are not found in the catalog, use reasonable defaults or skip those nutrients. Proceed with the data you have.\n"
            "- When matching nutrients, use the 'key' field from the catalog (e.g., 'calories', 'protein_g', 'carbs_g', 'vitamin_a_mcg') to match with the nutrient names in the proposed goal.\n"
            "- The proposed goal uses database keys like 'calories', 'carbs_g', 'vitamin_b1_mg', etc. Match these exactly with the catalog keys.\n"
            "- Do NOT ask questions about meal plan nutrients - meal plans store nutritional values directly without needing nutrient ID mapping.\n\n"
            "DATETIME HANDLING:\n"
            "- Extract start_date and target_completion_date from the proposed_goal.timing section (already in YYYY-MM-DD format)\n"
            "- Convert dates to ISO format strings like '2024-01-01T00:00:00' for database storage\n"
            "- For effective_at: use the start_date from proposed_goal.timing\n"
            "- For expires_at: use the target_completion_date from proposed_goal.timing\n"
            "- The tool will automatically convert these to proper datetime objects for the database\n\n"
            "PROCESS:\n"
            "1) FIRST: Call query_nutrient_catalog to get the actual nutrient IDs from the database\n"
            "2) Parse the proposed_goal JSON to extract nutrient values and meal plan\n"
            "3) Map each nutrient from daily_rda to the correct nutrient_id from the catalog query results\n"
            "4) Prepare nutrition_goals record with user_id, goal_name, goal_description, status='active', effective_at and expires_at based on the user's start_date and target_completion_date from proposed_goal.timing\n"
            "5) Prepare ALL nutrition_goal_targets records as an array - for each nutrient in daily_rda, create a record with the correct nutrient_id from the catalog, target_type='daily', target_min=value, target_max=value, priority='primary' for key nutrients (calories, protein, carbs, fat) and 'secondary' for others\n"
            "6) Prepare ALL user_nutrient_focus records as an array - for primary nutrients only, create records with user_id, correct nutrient_id, priority='primary'\n"
            "7) Prepare nutrition_meal_plans record - extract the entire daily_meal_plan structure and store as JSON strings:\n"
            "   - breakfast: JSON string of the breakfast object from daily_meal_plan\n"
            "   - lunch: JSON string of the lunch object from daily_meal_plan\n"
            "   - dinner: JSON string of the dinner object from daily_meal_plan\n"
            "   - snacks: JSON string of the snacks object from daily_meal_plan\n"
            "   - recommended_options: JSON string with recommended meal options\n"
            "   - total_calories_kcal: sum of all meal calories\n"
            "   NOTE: Convert the entire meal plan objects to JSON strings before storing\n"
            "8) Call batch_insert_nutrition_data ONCE with all four JSON strings (goals_data, targets_data, focus_data, meal_plans_data)\n"
            "9) Return the result from the batch function\n\n"
            "IMPORTANT: You must call batch_insert_nutrition_data exactly ONCE with all the data. Do not make multiple calls.\n\n"
            "OUTPUT FORMAT (return ONLY JSON):\n"
            "{\n"
            "  \"success\": boolean,\n"
            "  \"goal_id\": number,\n"
            "  \"targets_created\": number,\n"
            "  \"focus_records_created\": number,\n"
            "  \"meal_plans_created\": number,\n"
            "  \"message\": string,\n"
            "  \"errors\": [string]\n"
            "}"
        )

        user_instruction = (
            "Context: " + context_blob + "\n" \
            "Task: Parse the proposed goal data and store it in the nutrition goals database tables using batch_insert_nutrition_data. "
            "FIRST call query_nutrient_catalog to get the actual nutrient IDs from the database, then map the nutrients from daily_rda to the correct IDs. "
            "Prepare all data first, then call the batch function ONCE with all four JSON strings (goals_data, targets_data, focus_data, meal_plans_data). "
            "Extract all meal options from the daily_meal_plan and create meal plan records for each option. "
            "If any critical information is missing, ask one clarifying question at a time. "
            "Return ONLY the JSON summary from the batch function."
        )

        try:
            result = await agent.ainvoke(
                {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                {"return_intermediate_steps": True, "recursion_limit": 50, "configurable": {"thread_id": state.get("request_id")}}
            )

            final_msg = result.get("messages", [])[-1]
            final_content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
            parsed = None
            try:
                m = re.search(r"\{[\s\S]*\}", final_content)
                if m:
                    parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

            if parsed:
                state["set_goal_result"] = parsed
            else:
                state["set_goal_result"] = {
                    "success": False,
                    "goal_id": None,
                    "targets_created": 0,
                    "focus_records_created": 0,
                    "message": "Agent did not return valid JSON",
                    "errors": ["Invalid response format"]
                }
        except Exception as e:
            state["set_goal_result"] = {
                "success": False,
                "goal_id": None,
                "targets_created": 0,
                "focus_records_created": 0,
                "message": f"Error setting nutrition goal: {e}",
                "errors": [str(e)]
            }

        state["goal_created"] = bool(state.get("set_goal_result", {}).get("success"))
        return state

    async def handle_error(self, state: NutritionalGoalState) -> NutritionalGoalState:
        try:
            # Ensure we surface a structured error result and do not proceed further
            err = state.get("error_message") or "Unknown error"
            if not state.get("set_goal_result"):
                state["set_goal_result"] = {
                    "success": False,
                    "goal_id": None,
                    "targets_created": 0,
                    "focus_records_created": 0,
                    "message": err,
                    "errors": [err],
                }
            state["goal_created"] = False
            return state
        except Exception as e:
            state["set_goal_result"] = {
                "success": False,
                "goal_id": None,
                "targets_created": 0,
                "focus_records_created": 0,
                "message": f"Error handling previous error: {e}",
                "errors": [str(e)],
            }
            state["goal_created"] = False
            return state


async def run_nutritional_goal_workflow(user_id: int, session_id: Optional[int], request_data: Dict[str, Any]) -> Dict[str, Any]:
    wf = NutritionalGoalWorkflow()
    init: NutritionalGoalState = {
        "request_id": str(uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "request_data": request_data,
        "collected_context": {},
        "proposed_goal": {},
        "set_goal_result": {},
        "collect_done": False,
        "prepare_done": False,
        "set_done": False,
        "error_message": None,
    }
    out = await wf.run(init)
    has_error = bool(out.get("error_message"))
    return {
        "success": not has_error,
        "response_message": {
            "success": not has_error,
            "data": {
                "collected_context": out.get("collected_context", {}),
                "proposed_goal": out.get("proposed_goal", {}),
                "set_goal_result": out.get("set_goal_result", {}),
            },
            "message": out.get("error_message") or "Nutritional goal workflow executed"
        }
    }

    async def set_nutrition_targets(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Create nutrition targets and focus records in the database."""
        # Implementation for targets and focus records
        state["targets_created"] = True
        return state

    async def set_nutrition_meal_plans(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Create nutrition meal plans in the database."""
        # Implementation for meal plans
        state["meal_plans_created"] = True
        return state


