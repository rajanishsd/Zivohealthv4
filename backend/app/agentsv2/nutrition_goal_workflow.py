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
    goal_created: bool
    targets_created: bool
    meal_plans_created: bool
    goal_id: Optional[int]
    error_message: Optional[str]
    # Confirmation flow fields
    plan_confirmed: bool
    revision_count: int
    user_revision_request: Optional[str]
    # Reminder setup fields
    reminders_confirmed: bool
    reminder_preferences: Dict[str, Any]


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
        g.add_node("confirm_nutrition_plan", self.confirm_nutrition_plan)
        g.add_node("collect_meal_reminder_preferences", self.collect_meal_reminder_preferences)
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
            {"ok": "confirm_nutrition_plan", "error": "handle_error"},
        )
        g.add_conditional_edges(
            "confirm_nutrition_plan",
            self.route_after_confirm,
            {"accept": "collect_meal_reminder_preferences", "revise": "prepare_nutrition_goal", "error": "handle_error"},
        )
        g.add_conditional_edges(
            "collect_meal_reminder_preferences",
            self.route_after_collect_reminders,
            {"ok": "set_nutrition_goal", "error": "handle_error"},
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

    def route_after_confirm(self, state: NutritionalGoalState) -> str:
        # Prefer revision over acceptance if both are present
        if state.get("user_revision_request") and 0 < (state.get("revision_count") or 0) <= 2:
            return "revise"
        if state.get("plan_confirmed"):
            return "accept"
        return "error"
    
    def route_after_collect_reminders(self, state: NutritionalGoalState) -> str:
        return "ok" if state.get("reminders_confirmed") else "error"
    
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
                from app.agentsv2.tools.chat_context_utils import ask_question_with_post_context
                
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
                    result = await ask_question_with_post_context(session_id, str(user_id), question_text, timeout_sec=300.0)
                    response = result.get("response", "")
                    
                    # Organize by category
                    if category not in responses:
                        responses[category] = {}
                    
                    # Create a key for the response (use part of the question as key)
                    key = question_text.lower().replace('?', '').replace(' ', '_')[:30]
                    responses[category][key] = {
                        "question": question_text,
                        "response": response,
                        "post_question_context": result.get("post_question_context", []),
                        "context_plus_response": result.get("context_plus_response", "")
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
                    "1) Call ask_clarifying_questions EXACTLY ONCE with ALL questions at once (separated by newlines). Do NOT call this tool multiple times.\n"
                    "2) The function will ask each question individually and return all responses organized by category.\n"
                    "3) Parse the returned JSON responses and map them to the appropriate JSON output categories (personal_demographics, health_medical_profile, etc.).\n"
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
                    "HEALTH_MEDICAL_PROFILE: Do you have any past medical history or chronic conditions?\n"
                    "HEALTH_MEDICAL_PROFILE: Is there any family history of chronic illnesses?\n"
                    "HEALTH_MEDICAL_PROFILE: What medications and supplements are you currently taking?\n"
                    "HEALTH_MEDICAL_PROFILE: Do you have any food allergies or intolerances?\n"
                    "GOALS_OBJECTIVES: What is your primary nutrition goal?(Don't ask this question if user has already provided the goal name)\n"
                    "GOALS_OBJECTIVES: What are your secondary health goals?\n"
                    "GOALS_OBJECTIVES: What is your expected timeframe for achieving these goals?\n"
                    "GOALS_OBJECTIVES: When do you want to start this nutrition plan? (e.g., immediately, next week, specific date)\n"
                    "GOALS_OBJECTIVES: What is your target completion date or duration for achieving your goals?( Don't ask this question if user has already provided the timeframe, calculate it from the start date and timeframe)\n"
                    "OUTPUT FORMAT (return ONLY JSON; no commentary): Capture all the units for the values in the JSON.\n"
                    "{\n"
                    "  \"personal_demographics\": { \"age\": number, \"gender\": string, \"height_cm\": number, \"weight_kg\": number, \"waist_circumference_cm\": number | null, \"hip_circumference_cm\": number | null, \"neck_circumference_cm\": number | null, \"waist_to_hip_ratio\": number | null, \"bmi\": number, \"bmr_kcal\": number, \"tdee_kcal\": number, \"body_fat_percentage\": number | null },\n"
                    "  \"health_medical_profile\": { ... },\n"
                    "  \"goals_objectives\": { \"goal_name: Derive this from the user input objective\": string, \"goal_description: Derive this from the user input objective\": string, \"primary_goal\": string | null, \"secondary_goals\": [string], \"start_date\": string, \"target_completion_date\": string, \"timeframe_duration\": string },\n"
                    "}"
                )

                user_instruction = (
                    "Collect missing information required to prepare a nutrition plan for the given objective.\n"
                    "Call ask_clarifying_questions EXACTLY ONCE with ALL questions at once (separated by newlines). Do NOT call this tool multiple times.\n"
                    "The function will ask each question individually and return all responses organized by category.\n"
                    "Parse the returned responses and map them to the appropriate JSON output categories.\n"
                    "Return ONLY a single JSON object with the category headings exactly as specified. Ensure \"goals_objectives\" includes \"goal_name\" and \"goal_description\" derived from user context and clarifications and dont ask question on this"
                )

                result = await agent.ainvoke(
                    {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                    {"return_intermediate_steps": True, "recursion_limit": 10, "configurable": {"thread_id": state.get("request_id")}}
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
        try:
            print(
                f"🛠️ [Prepare] revision_count={state.get('revision_count')} "
                f"user_revision_request={state.get('collected_context', {}).get('user_revision_request') or state.get('user_revision_request')}"
            )
        except Exception:
            pass
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
                from app.agentsv2.tools.chat_context_utils import ask_question_with_post_context
                result = await ask_question_with_post_context(session_id, str(user_id), question, timeout_sec=300.0)
                ctx = result.get("post_question_context") or []
                if ctx:
                    lines = [f"{m.get('role')}: {m.get('content')}" for m in ctx]
                    return (str(result.get("response", "")) + "\n\nContext since question:\n" + "\n".join(lines)).strip()
                return str(result.get("response", ""))
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

        # Include previous plan and revision request so the agent can modify instead of recreating
        previous_plan = state.get("proposed_goal") or {}
        context_blob = json.dumps({
            "objective": objective,
            "collected_context": collected_context,
            "previous_plan": previous_plan,
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
            "- Only ask the user when essential information is missing (one question at a time).\n"
            "- MUST APPLY USER REVISIONS (if present): If Context.collected_context.user_revision_request exists, treat it as non-negotiable constraints. Apply the exact requested targets to daily_rda (e.g., calories, protein_g, carbs_g, fat_g), overriding computed values. Use Context.previous_plan as the base; preserve unspecified values and meals, and modify only requested aspects. Align meal plan totals to approximately match the revised daily calories.\n\n"
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
            "If 'user_revision_request' is present in Context.collected_context, you MUST make those exact changes (e.g., calories, protein_g, carbs_g, fat_g) in daily_rda, overriding computed values. Use Context.previous_plan as the base and preserve unspecified parts. Do not deviate from requested targets. Do not ask for confirmation here; that happens in a separate step. "
            "Return ONLY the updated revised plan in JSON in the specified schema."
        )

        # Single plan generation here; confirmation handled in dedicated node
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

    

    async def confirm_nutrition_plan(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Use an agent to confirm the nutrition plan with the user and handle revisions intelligently."""
        user_id = state["user_id"]
        session_id = state.get("session_id")
        state["plan_confirmed"] = False
        state["revision_count"] = int(state.get("revision_count") or 0)

        # If no plan, error route
        plan = state.get("proposed_goal") or {}
        daily_rda = plan.get("daily_rda") or {}
        if not daily_rda:
            state["error_message"] = "No plan to confirm"
            return state

        # If we cannot ask the user, auto-accept
        if not (session_id and user_id):
            state["plan_confirmed"] = True
            return state

        # Create confirmation agent with tools
        @tool
        async def ask_clarifying_question(question: str) -> str:
            """Ask the user a clarifying question and return their response.

            WHEN TO USE:
            - FIRST action in this node: briefly summarize the plan and ask if the user wants to
              accept as-is or request specific changes.
            - Any time the user's reply is ambiguous and you need one short follow-up to decide
              between acceptance vs revision.

            DO NOT:
            - Do not ask multiple questions at once. Keep it to a single, concise question.
            - Do not call confirm_plan_acceptance() or request_plan_revision() in the same turn
              that you are still clarifying.
            """
            from app.agentsv2.tools.chat_context_utils import ask_question_with_post_context
            result = await ask_question_with_post_context(session_id, str(user_id), question, timeout_sec=300.0)
            ctx = result.get("post_question_context") or []
            if ctx:
                lines = [f"{m.get('role')}: {m.get('content')}" for m in ctx]
                return (str(result.get("response", "")) + "\n\nContext since question:\n" + "\n".join(lines)).strip()
            return str(result.get("response", ""))

        @tool
        async def confirm_plan_acceptance() -> str:
            """Mark the nutrition plan as accepted by the user.

            WHEN TO USE:
            - Only when the user's latest reply clearly indicates acceptance with words like
              "accept", "yes", "looks good", "ok/okay", or equivalent unambiguous approval.

            DO NOT:
            - Do not call this if the user mentioned any desired change (e.g., calories/macros/meal/timing).
            - Do not call this in the same turn after calling request_plan_revision().
            """
            
            state["plan_confirmed"] = True
            # Clear any prior revision intent so it doesn't leak into next runs
            try:
                state["user_revision_request"] = None
                cc = state.get("collected_context") or {}
                if "user_revision_request" in cc:
                    cc.pop("user_revision_request", None)
                    state["collected_context"] = cc
                # Optionally reset revision counter after acceptance
                state["revision_count"] = 0
            except Exception:
                pass
            return "Plan confirmed and accepted."

        @tool
        async def request_plan_revision(revision_details: str) -> str:
            """Request revisions to the nutrition plan with specific details.

            WHEN TO USE:
            - Use when the user asks to change anything (e.g., "reduce calories to 1800",
              "increase protein to 150g", swap/change meals, adjust duration or start date).
            - The revision_details MUST be a concise, actionable prompt enumerating the exact changes.

            EXAMPLES OF revision_details:
            - "calories=1800; protein_g=150; start_date=2025-09-15"
            - "keep calories; reduce sodium_mg to 1800; breakfast.recommended_option=2"

            DO NOT:
            - Do not call confirm_plan_acceptance() in the same turn. Let the graph route back to
              prepare for an updated plan, then confirmation happens later.
            """
            state["user_revision_request"] = revision_details
            state["revision_count"] = int(state.get("revision_count") or 0) + 1
            # Inject the revision into collected_context so prepare step can use it
            cc = state.get("collected_context") or {}
            cc["user_revision_request"] = revision_details
            state["collected_context"] = cc
            return f"Plan revision requested: {revision_details}"

        tools = [ask_clarifying_question, confirm_plan_acceptance, request_plan_revision]

        # Create the confirmation agent
        llm = ChatOpenAI(
            model=settings.CUSTOMER_AGENT_MODEL,
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY
        )
        
        agent = create_react_agent(llm, tools)

        # Prepare context for the agent
        try:
            calories = daily_rda.get("calories")
            macros = daily_rda.get("macronutrients", {}) or {}
            pg = macros.get("protein_g")
            cg = macros.get("carbs_g") 
            fg = macros.get("fat_g")
            
            # Create a more detailed summary for the agent
            plan_summary = {
                "calories": calories,
                "protein_g": pg,
                "carbs_g": cg,
                "fat_g": fg,
                "full_plan": plan  # includes vitamins, minerals, meal plan options, timing
            }
            
        except Exception:
            plan_summary = {"error": "Could not parse plan details", "full_plan": plan}

        revision_count = state.get("revision_count", 0)
        context_blob = json.dumps({
            "plan_summary": plan_summary,
            "revision_count": revision_count,
            "max_revisions": 2
        }, default=str)

        system = (
            "You are a nutrition plan confirmation assistant. Your role is to:\n"
            "1. Present the current plan to the user with ALL relevant details in a concise, readable form:\n"
            "   - Calories, macronutrients (protein_g, carbs_g, fat_g), fibers\n"
            "   - Vitamins and minerals (key ones only if too long)\n"
            "   - Meal plan: for each meal (breakfast, lunch, dinner, snacks), list 2-3 options with name and calories; indicate the recommended option index\n"
            "   - Timing: start_date, target_completion_date, timeframe_duration\n"
            "2. Ask if they want to accept the plan or make specific changes, such as:\n"
            "   - Nutrient composition (e.g., calories, macros, specific vitamins/minerals)\n"
            "   - Meals (swap recommended option, replace an option, add/remove items)\n"
            "   - Duration or start date (timing)\n"
            "3. If they request changes, capture a clear, actionable revision prompt that another agent can use to MODIFY the existing plan.\n"
            "4. Use the appropriate tool based on their response.\n\n"
            "MANDATORY FLOW:\n"
            "- Your FIRST and IMMEDIATE action MUST be to call ask_clarifying_question() with a single question that:\n"
            "  summarizes the plan along with start date, target completion date, timeframe duration and meal details and asks: 'Would you like to accept this plan as-is, or make changes? If changes, specify what to change (e.g., calories, macros, specific nutrients, meal options, timing).'.\n"
            "- Do NOT auto-accept without asking the user. Always ask first.\n"
            "- After receiving the reply: if user accepts the plan → call confirm_plan_acceptance(); if user requests changes or mentions changes → call request_plan_revision() with a concise revision prompt.\n"
            "- If user response is unclear → call ask_clarifying_question() again to clarify BEFORE calling request_plan_revision().\n"
            "- Keep responses short and friendly; do not overwhelm.\n"
            "- Always end by calling either confirm_plan_acceptance() or request_plan_revision(). Dont call both in the same turn.\n"
            "- Do NOT attempt to regenerate a new plan yourself. Only capture intent and details.\n"
        )

        user_instruction = (
            f"Context: {context_blob}\n\n"
            "Task: Present the current plan (use plan_summary.full_plan), then ask if they want to accept or change specific details (meals, nutrient composition, duration, start date/time).\n"
            "If they request changes, construct a single 'revision prompt' string that another agent can use to modify the plan.\n"
            "The revision prompt MUST be explicit and actionable.\n\n"
            "Revision prompt format (examples):\n"
            "- 'Update calories to 1800; set protein_g=150, carbs_g=170, fat_g=60; change start_date to 2025-09-15; duration 12 weeks.'\n"
            "- 'Keep calories; increase vitamin_c_mg to 120; reduce sodium_mg to 1800; breakfast: set recommended_option=2; replace lunch option 1 name with \"Paneer Bowl\" calories=520.'\n"
            "- 'No change to macros; adjust timing: start_date 2025-09-10, timeframe_duration 8 weeks; snacks: replace option 0 with \"Greek Yogurt\" calories=180.'\n\n"
            "When done, call request_plan_revision(revision_details)."
        )

        try:
            result = await agent.ainvoke(
                {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                {"return_intermediate_steps": True, "recursion_limit": 15, "configurable": {"thread_id": state.get("request_id")}}
            )
            
            # The agent should have set plan_confirmed or user_revision_request via tools
            return state
            
        except Exception as e:
            # On error, accept to avoid dead-ends
            state["plan_confirmed"] = True
            return state

    async def collect_meal_reminder_preferences(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Collect and confirm daily meal reminder preferences (JSON-only) after plan acceptance."""
        user_id = state["user_id"]
        session_id = state.get("session_id")
        state["reminders_confirmed"] = bool(state.get("reminders_confirmed"))
        if not (session_id and user_id):
            # No interactive session; set sensible defaults
            tz = getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kolkata")
            from datetime import date
            state["reminder_preferences"] = {
                "timezone": tz,
                "start_date": date.today().isoformat(),
                "reminders": [
                    {"meal": "breakfast", "time_local": "09:00", "frequency": "daily"},
                    {"meal": "lunch", "time_local": "13:00", "frequency": "daily"},
                    {"meal": "dinner", "time_local": "20:00", "frequency": "daily"},
                ],
                "source": "default",
            }
            state["reminders_confirmed"] = True
            return state

        @tool
        async def ask_for_reminders(prompt: str) -> str:
            """Ask the user to reply ONLY with JSON per schema for meal reminders."""
            from app.agentsv2.customer_workflow import ask_user_question
            return await ask_user_question(prompt, session_id, str(user_id))

        @tool
        async def save_reminder_preferences(reminders_json: str) -> str:
            """Validate and save reminder preferences JSON into state. Returns 'ok' or error string."""
            try:
                data = json.loads(reminders_json)
            except Exception as e:
                return f"invalid_json: {e}"

            # Normalize and validate
            tz = data.get("timezone") or getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kolkata")
            start_date = data.get("start_date")
            reminders = data.get("reminders")
            if not isinstance(reminders, list):
                return "invalid_schema: reminders must be a list"
            allowed_meals = {"breakfast", "lunch", "dinner"}
            seen = set()
            normalized = []
            def _normalize_time(s: str) -> str | None:
                """Accepts 'HH:MM', 'H:MM', 'HH', 'H', '10am', '10 pm', '10:30AM' and returns 24h 'HH:MM'."""
                if s is None:
                    return None
                raw = str(s).strip().lower().replace(".", "")
                # Extract am/pm
                meridian = None
                if raw.endswith("am"):
                    meridian = "am"
                    raw = raw[:-2].strip()
                elif raw.endswith("pm"):
                    meridian = "pm"
                    raw = raw[:-2].strip()
                # Split hour and minute
                if ":" in raw:
                    parts = raw.split(":", 1)
                    hh_str, mm_str = parts[0].strip(), parts[1].strip()
                else:
                    hh_str, mm_str = raw, "00"
                if not hh_str.isdigit() or not mm_str.isdigit():
                    return None
                hh, mm = int(hh_str), int(mm_str)
                if meridian:
                    if hh == 12:
                        hh = 0 if meridian == "am" else 12
                    elif 1 <= hh <= 11 and meridian == "pm":
                        hh += 12
                # Bounds
                if not (0 <= hh <= 23 and 0 <= mm <= 59):
                    return None
                return f"{hh:02d}:{mm:02d}"
            for r in reminders:
                if not isinstance(r, dict):
                    return "invalid_schema: reminder item must be object"
                meal = str(r.get("meal", "")).lower()
                time_local = r.get("time_local")
                freq = r.get("frequency") or "daily"
                if meal not in allowed_meals:
                    return f"invalid_meal: {meal}"
                if meal in seen:
                    return f"duplicate_meal: {meal}"
                normalized_time = _normalize_time(time_local)
                if not normalized_time:
                    return f"invalid_time: {time_local}"
                if freq not in ("daily", "every_2_days", "weekly"):
                    return f"invalid_frequency: {freq}"
                seen.add(meal)
                normalized.append({"meal": meal, "time_local": normalized_time, "frequency": freq})
            if seen != allowed_meals:
                missing = ",".join(sorted(allowed_meals - seen))
                return f"missing_meals: {missing}"

            # Default start_date to today if absent
            from datetime import date
            if not start_date:
                start_date = date.today().isoformat()

            state["reminder_preferences"] = {
                "timezone": tz,
                "start_date": start_date,
                "reminders": normalized,
                "source": "user",
            }
            state["reminders_confirmed"] = True
            return "ok"

        tools = [ask_for_reminders, save_reminder_preferences]
        llm = ChatOpenAI(
            model=getattr(settings, 'CUSTOMER_AGENT_MODEL', None) or getattr(settings, 'DEFAULT_AI_MODEL', 'gpt-4o-mini'),
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0.0,
        )
        agent = create_react_agent(model=llm, tools=tools, prompt=None)

        tz = state.get("user_timezone") or getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kolkata")
        from datetime import date
        today_iso = date.today().isoformat()
        system = (
            "You are a reminder-setup assistant. Ask the user (in natural language) to confirm or edit daily reminder times for breakfast, lunch, and dinner to log nutrition.\n"
            "- Suggest default local times: breakfast 09:00, lunch 13:00, dinner 20:00.\n"
            "- Default frequency: 'daily'. Allowed: 'daily', 'every_2_days', 'weekly'.\n"
            "- The USER will reply in free text. YOU must parse their reply and produce a JSON object matching the schema below. Do NOT ask the user to reply in JSON.\n\n"
            "Schema (your internal output):\n"
            "{\n"
            "  \"timezone\": \"IANA timezone string (e.g., Asia/Kolkata)\",\n"
            "  \"start_date\": \"YYYY-MM-DD\",\n"
            "  \"reminders\": [\n"
            "    {\"meal\": \"breakfast\", \"time_local\": \"HH:MM\", \"frequency\": \"daily|every_2_days|weekly\"},\n"
            "    {\"meal\": \"lunch\",     \"time_local\": \"HH:MM\", \"frequency\": \"daily|every_2_days|weekly\"},\n"
            "    {\"meal\": \"dinner\",    \"time_local\": \"HH:MM\", \"frequency\": \"daily|every_2_days|weekly\"}\n"
            "  ]\n"
            "}\n\n"
            "Flow:\n"
            "1) First, ask one concise clarification question via ask_for_reminders() that presents defaults and invites changes.\n"
            "2) After receiving the user's free-text reply, generate the JSON yourself.\n"
            "3) Validate it against the schema; if ambiguous or missing fields, ask ONE follow-up via ask_for_reminders(), then finalize.\n"
            "4) Finally, call save_reminder_preferences(reminders_json) with the JSON string."
        )

        user_instruction = (
            f"Context: timezone={tz}, today={today_iso}. Defaults: breakfast 09:00, lunch 13:00, dinner 20:00; frequency 'daily'.\n\n"
            "Task: 1) Use ask_for_reminders() to ask the user in plain language to confirm or modify the times and frequency for each meal.\n"
            "2) Parse their free-text reply and construct the JSON per schema.\n"
            "3) Call save_reminder_preferences(reminders_json) with the finalized JSON."
        )

        try:
            await agent.ainvoke(
                {"messages": [SystemMessage(content=system), HumanMessage(content=user_instruction)]},
                {"return_intermediate_steps": True, "recursion_limit": 10, "configurable": {"thread_id": state.get("request_id")}},
            )
        except Exception:
            # On failure, fall back to defaults but continue flow
            tz = getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kolkata")
            state["reminder_preferences"] = {
                "timezone": tz,
                "start_date": today_iso,
                "reminders": [
                    {"meal": "breakfast", "time_local": "09:00", "frequency": "daily"},
                    {"meal": "lunch", "time_local": "13:00", "frequency": "daily"},
                    {"meal": "dinner", "time_local": "20:00", "frequency": "daily"},
                ],
                "source": "default_error",
            }
            state["reminders_confirmed"] = True
        return state

    async def set_nutrition_goal(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Create the nutrition goal record in the database using data from prepare node."""
        from datetime import datetime
        user_id = state["user_id"]
        proposed_goal = state.get("proposed_goal", {}) or {}
        timing = proposed_goal.get("timing") or {}
        goal_name = state.get("collected_context", {}).get("goal_name") or "Nutrition Goal"
        goal_description = state.get("collected_context", {}).get("goal_description") or goal_name

        # Parse dates (YYYY-MM-DD expected)
        def to_iso(dt_str: str | None) -> str | None:
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(str(dt_str)).strftime("%Y-%m-%dT00:00:00")
            except Exception:
                return None

        effective_at = to_iso(timing.get("start_date"))
        expires_at = to_iso(timing.get("target_completion_date"))

        # Insert into nutrition_goals
        goal_id: Optional[int] = None
        try:
            from psycopg2.extras import RealDictCursor
            with get_raw_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Capture currently active goal ids to pause their reminders after deactivation
                    cursor.execute(
                        "SELECT id FROM nutrition_goals WHERE user_id = %s AND status = 'active'",
                        [user_id],
                    )
                    previously_active_goal_ids = [int(r["id"]) for r in cursor.fetchall()] if cursor.rowcount else []
                    # First, deactivate any existing active goals for this user
                    deactivate_query = (
                        "UPDATE nutrition_goals SET status = 'inactive', updated_at = NOW() "
                        "WHERE user_id = %s AND status = 'active'"
                    )
                    cursor.execute(deactivate_query, [user_id])
                    deactivated_count = cursor.rowcount
                    
                    # Then, create the new active goal
                    insert_query = (
                        "INSERT INTO nutrition_goals (user_id, goal_name, goal_description, status, effective_at, expires_at, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id"
                    )
                    cursor.execute(insert_query, [user_id, str(goal_name), str(goal_description), "active", effective_at, expires_at])
                    row = cursor.fetchone()
                    goal_id = row["id"] if row else None

                    # Mark existing reminder configs for the previously active goals as inactive
                    try:
                        if previously_active_goal_ids:
                            _gid_strs = [str(x) for x in previously_active_goal_ids]
                            cursor.execute(
                                """
                                UPDATE user_reminder_configs
                                SET active = false, updated_at = NOW()
                                WHERE user_id = %s AND context = 'nutrition_goal' AND context_id = ANY(%s)
                                """,
                                [str(user_id), _gid_strs],
                            )

                            # Fetch external_ids of those reminder configs to pause reminders service templates
                            cursor.execute(
                                """
                                SELECT external_id
                                FROM user_reminder_configs
                                WHERE user_id = %s AND context = 'nutrition_goal' AND context_id = ANY(%s)
                                """,
                                [str(user_id), _gid_strs],
                            )
                            rows_ext = cursor.fetchall() or []
                            external_ids_to_pause = [r["external_id"] for r in rows_ext if r.get("external_id")]
                        else:
                            external_ids_to_pause = []
                    except Exception:
                        external_ids_to_pause = []
        except Exception as e:
            state["set_goal_result"] = {"success": False, "goal_id": None, "errors": [str(e)], "message": "Failed to create nutrition goal"}
            state["goal_created"] = False
            return state

        state["goal_id"] = goal_id
        message = f"Goal created successfully"
        if deactivated_count > 0:
            message += f" (deactivated {deactivated_count} previous active goal{'s' if deactivated_count > 1 else ''})"
        
        state["set_goal_result"] = {
            "success": True, 
            "goal_id": goal_id, 
            "targets_created": 0, 
            "focus_records_created": 0, 
            "meal_plans_created": 0, 
            "deactivated_previous_goals": deactivated_count,
            "message": message
        }
        state["goal_created"] = True

        # Best-effort: pause reminders in Reminders service for previously active goals
        try:
            if 'external_ids_to_pause' in locals() and external_ids_to_pause:
                from app.reminders.client import push_list_reminders, push_update_reminder
                # List all reminders for the user and map by external_id
                items = push_list_reminders(str(user_id))
                ext_to_item = {i.get("external_id"): i for i in items if i.get("external_id")}
                for ext in external_ids_to_pause:
                    it = ext_to_item.get(ext)
                    if not it:
                        continue
                    reminder_id = it.get("id")
                    if reminder_id:
                        try:
                            # Set is_active=false to pause recurrence
                            push_update_reminder(reminder_id, {"is_active": False}, timeout=8)
                        except Exception:
                            pass
        except Exception:
            pass
        return state

    async def set_nutrition_targets(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Insert nutrition_goal_targets (and minimal user_nutrient_focus) mapped by catalog keys."""
        from psycopg2.extras import RealDictCursor
        from datetime import datetime
        goal_id = state.get("goal_id")
        proposed_goal = state.get("proposed_goal", {}) or {}
        daily_rda = proposed_goal.get("daily_rda") or {}
        if not goal_id or not daily_rda:
            state["targets_created"] = False
            return state

        # Build flat key->value map from daily_rda
        values_map: Dict[str, float] = {}
        if isinstance(daily_rda.get("calories"), (int, float)):
            values_map["calories"] = float(daily_rda["calories"]) 
        for grp in ("macronutrients", "vitamins", "minerals"):
            grp_obj = daily_rda.get(grp) or {}
            if isinstance(grp_obj, dict):
                for k, v in grp_obj.items():
                    if isinstance(v, (int, float)):
                        values_map[k] = float(v)

        # Load catalog mapping key->id
        key_to_id: Dict[str, int] = {}
        try:
            with get_raw_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT id, key FROM nutrition_nutrient_catalog")
                    for row in cursor.fetchall():
                        key_to_id[str(row["key"])]= int(row["id"]) 
        except Exception as e:
            state["set_goal_result"]= {**state.get("set_goal_result", {}), "success": False, "errors": [str(e)]}
            state["targets_created"] = False
            return state

        # Prepare targets rows
        targets_rows = []
        for key, val in values_map.items():
            nid = key_to_id.get(key)
            if not nid:
                continue
            targets_rows.append({
                "goal_id": goal_id,
                "nutrient_id": nid,
                "timeframe": "daily",
                "target_type": "daily",
                "target_min": val,
                "target_max": val,
                "priority": "primary" if key in ("calories", "protein_g", "carbs_g", "fat_g") else "secondary",
                "is_active": True,
            })

        # Insert targets
        created_count = 0
        try:
            if targets_rows:
                with get_raw_db_connection() as conn:
                    with conn.cursor() as cursor:
                        columns = list(targets_rows[0].keys())
                        placeholders = ", ".join(["%s"] * len(columns))
                        sql = f"INSERT INTO nutrition_goal_targets ({', '.join(columns)}, created_at, updated_at) VALUES ({placeholders}, NOW(), NOW())"
                        values = [tuple(row[c] for c in columns) for row in targets_rows]
                        cursor.executemany(sql, values)
                        created_count = len(values)
        except Exception as e:
            state["set_goal_result"] = {**state.get("set_goal_result", {}), "success": False, "errors": [str(e)]}
            state["targets_created"] = False
            return state

        # Optionally create focus for primary macros
        try:
            focus_rows = []
            for key in ("calories", "protein_g", "carbs_g", "fat_g"):
                nid = key_to_id.get(key)
                if not nid:
                    continue
                focus_rows.append({
                    "user_id": state["user_id"], 
                    "nutrient_id": nid, 
                    "goal_id": goal_id,
                    "priority": "primary", 
                    "is_active": True
                })
            if focus_rows:
                with get_raw_db_connection() as conn:
                    with conn.cursor() as cursor:
                        cols = list(focus_rows[0].keys())
                        ph = ", ".join(["%s"] * len(cols))
                        sql = f"INSERT INTO user_nutrient_focus ({', '.join(cols)}, created_at, updated_at) VALUES ({ph}, NOW(), NOW())"
                        vals = [tuple(r[c] for c in cols) for r in focus_rows]
                        cursor.executemany(sql, vals)
        except Exception as e:
            # Non-fatal
            state["set_goal_result"] = {**state.get("set_goal_result", {}), "errors": state.get("set_goal_result", {}).get("errors", []) + [str(e)]}

        # Update counts/flags
        sgr = state.get("set_goal_result", {})
        sgr["targets_created"] = created_count
        state["set_goal_result"] = sgr
        state["targets_created"] = True

        # Schedule daily reminders for meals via Reminders API if preferences are confirmed
        try:
            prefs = state.get("reminder_preferences") or {}
            if state.get("reminders_confirmed") and isinstance(prefs, dict) and prefs.get("reminders"):
                import os
                import requests
                from datetime import datetime as _dt
                from datetime import time as _time
                from datetime import date as _date
                try:
                    from zoneinfo import ZoneInfo as _ZoneInfo
                except Exception:
                    _ZoneInfo = None

                tz_name = prefs.get("timezone") or getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kolkata")
                tz = None
                try:
                    tz = _ZoneInfo(tz_name) if _ZoneInfo else None
                except Exception:
                    tz = None

                start_date_str = prefs.get("start_date")
                try:
                    start_date = _date.fromisoformat(str(start_date_str)) if start_date_str else _date.today()
                except Exception:
                    start_date = _date.today()

                reminders = prefs.get("reminders") or []

                # Map frequency to interval days
                def _interval_days(freq: str) -> int:
                    return 1 if freq == "daily" else (2 if freq == "every_2_days" else 7)

                # Use shared reminders client
                from app.reminders.client import push_create_reminder

                # Prepare result list for UI
                created_external_ids = []
                # Persist config rows for each reminder key
                def _save_config_row(meal_key: str, external_id_val: str):
                    try:
                        from psycopg2.extras import RealDictCursor as _RDC
                        with get_raw_db_connection() as _conn:
                            with _conn.cursor(cursor_factory=_RDC) as _cur:
                                sql = (
                                    "INSERT INTO user_reminder_configs (user_id, context, context_id, reminder_type, key, external_id, group_id, config_json, active, created_at, updated_at) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, true, now(), now()) "
                                    "ON CONFLICT (external_id) DO UPDATE SET config_json = EXCLUDED.config_json, updated_at = now(), active = true"
                                )
                                _cur.execute(sql, [
                                    str(state["user_id"]),
                                    "nutrition_goal",
                                    str(goal_id),
                                    "nutrition_log",
                                    meal_key,
                                    external_id_val,
                                    group_id,
                                    json.dumps(prefs),
                                ])
                    except Exception:
                        pass

                for r in reminders:
                    meal = str(r.get("meal", "")).lower()
                    time_local = str(r.get("time_local", "09:00"))
                    freq = str(r.get("frequency", "daily"))
                    # Build start datetime in local tz
                    try:
                        hh, mm = time_local.split(":")
                        tobj = _time(hour=int(hh), minute=int(mm))
                    except Exception:
                        tobj = _time(hour=9, minute=0)
                    dt_local = _dt.combine(start_date, tobj)
                    if tz is not None:
                        dt_local = dt_local.replace(tzinfo=tz)
                    # Ensure first occurrence is in the future; if time already passed today, roll forward by interval
                    try:
                        if tz is not None:
                            now_local = _dt.now(tz)
                        else:
                            now_local = _dt.now()
                        interval = _interval_days(freq)
                        if dt_local <= now_local:
                            from datetime import timedelta as _td
                            dt_local = dt_local + _td(days=interval)
                    except Exception:
                        pass

                    title = f"Log your {meal}"
                    message = f"Please log your {meal} intake."
                    group_id = f"v1:{state['user_id']}:nutrition_goal:{goal_id}"
                    external_id = f"v1:{state['user_id']}:nutrition_log:nutrition_goal:{goal_id}:{meal}"
                    payload = {
                        "type": "nutrition_log",
                        "meal": meal,
                        "goal_id": goal_id,
                        "context": {
                            "domain": "nutrition",
                            "entity": "goal",
                            "entity_id": goal_id,
                            "key": meal,
                            "group_id": group_id,
                            "version": 1
                        }
                    }
                    recurrence_pattern = {"type": "daily", "interval": _interval_days(freq)}

                    body = {
                        "user_id": str(state["user_id"]),
                        "reminder_type": "nutrition_log",
                        "title": title,
                        "message": message,
                        "payload": payload,
                        "reminder_time": dt_local.isoformat(),
                        "recurrence_pattern": recurrence_pattern,
                        "start_date": dt_local.isoformat(),
                        "timezone": tz_name,
                        "external_id": external_id,
                    }

                    try:
                        resp = push_create_reminder(body, timeout=10)
                        print(f"resp in set_nutrition_targets: {resp}")
                        if resp.status_code in (200, 201):
                            created_external_ids.append({
                                "meal": meal,
                                "external_id": external_id,
                                "reminder_type": "nutrition_log",
                                "group_id": group_id
                            })
                            _save_config_row(meal, external_id)
                        else:
                            # Record failure with response details
                            try:
                                err_detail = resp.text[:500]
                            except Exception:
                                err_detail = str(resp.status_code)
                            state["set_goal_result"] = {
                                **state.get("set_goal_result", {}),
                                "errors": state.get("set_goal_result", {}).get("errors", []) + [
                                    f"reminders: failed to create {meal} ({resp.status_code}): {err_detail}"
                                ],
                            }
                    except Exception as e:
                        # Continue on individual failures but record the error
                        state["set_goal_result"] = {
                            **state.get("set_goal_result", {}),
                            "errors": state.get("set_goal_result", {}).get("errors", []) + [
                                f"reminders: exception creating {meal}: {e}"
                            ],
                        }

                # Attach to result for UI display
                if created_external_ids:
                    sgr = state.get("set_goal_result", {})
                    sgr["reminders"] = created_external_ids
                    state["set_goal_result"] = sgr
        except Exception as e:
            # Non-fatal: attach error but do not block targets
            state["set_goal_result"] = {**state.get("set_goal_result", {}), "errors": state.get("set_goal_result", {}).get("errors", []) + [f"reminders: {e}"]}
        return state

    async def set_nutrition_meal_plans(self, state: NutritionalGoalState) -> NutritionalGoalState:
        """Insert single nutrition_meal_plans record with JSON strings for meals."""
        from psycopg2.extras import RealDictCursor
        import json as _json
        goal_id = state.get("goal_id")
        proposed_goal = state.get("proposed_goal", {}) or {}
        dmp = proposed_goal.get("daily_meal_plan") or {}
        if not goal_id or not isinstance(dmp, dict):
            state["meal_plans_created"] = False
            return state

        def js(x: Any) -> Optional[str]:
            try:
                return _json.dumps(x) if x is not None else None
            except Exception:
                return None

        breakfast = js(dmp.get("breakfast"))
        lunch = js(dmp.get("lunch"))
        dinner = js(dmp.get("dinner"))
        snacks = js(dmp.get("snacks"))

        # recommended options map
        rec = {}
        for meal in ("breakfast", "lunch", "dinner", "snacks"):
            mo = dmp.get(meal) or {}
            if isinstance(mo, dict) and "recommended_option" in mo:
                rec[meal] = mo.get("recommended_option")
        recommended_options = js(rec)

        # total calories sum
        total_cals = 0
        for meal in ("breakfast", "lunch", "dinner", "snacks"):
            mo = dmp.get(meal) or {}
            try:
                total_cals += int(float(mo.get("total_calories_kcal", 0)))
            except Exception:
                pass

        try:
            with get_raw_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    sql = (
                        "INSERT INTO nutrition_meal_plans (goal_id, breakfast, lunch, dinner, snacks, recommended_options, total_calories_kcal, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())"
                    )
                    cursor.execute(sql, [goal_id, breakfast, lunch, dinner, snacks, recommended_options, total_cals])
        except Exception as e:
            state["set_goal_result"] = {**state.get("set_goal_result", {}), "success": False, "errors": [str(e)]}
            state["meal_plans_created"] = False
            return state

        sgr = state.get("set_goal_result", {})
        sgr["meal_plans_created"] = 1
        state["set_goal_result"] = sgr
        state["meal_plans_created"] = True
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
        "goal_created": False,
        "targets_created": False,
        "meal_plans_created": False,
        "goal_id": None,
        "error_message": None,
        "plan_confirmed": False,
        "revision_count": 0,
        "user_revision_request": None,
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


