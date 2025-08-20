import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import logging
logging.basicConfig(level=logging.ERROR)

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from typing import TypedDict, Dict, Any, List, Optional
from datetime import datetime
import asyncio

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.tools import tool

from app.core.config import settings
from app.schemas.chat_session import ChatMessageCreate
from app.agentsv2.response_utils import format_agent_response, format_error_response


# Local imports
from app.agentsv2.medical_doctor_panels import MedicalDoctorPanel


# All user-response coordination is centralized in chat sessions module


class MedicalDoctorState(TypedDict):
    user_id: str
    session_id: Optional[int]
    patient_case: str
    budget_limit: Optional[float]
    questions: List[str]
    answers: Dict[str, str]
    asked_questions: List[str]
    question_round: int
    max_question_rounds: int
    max_questions_per_round: int
    panel_decision: Optional[Dict[str, Any]]
    followup_decision: Optional[Dict[str, Any]]
    conversation_log: List[Dict[str, Any]]
    error: str
    processing_complete: bool
    response_data: Optional[Dict[str, Any]]


async def ask_user_question(question: str, session_id: Optional[int], user_id: str) -> str:
    """Ask a clarifying question to the user and wait for their response (with DB + WS updates)."""
    if not session_id or not user_id:
        return f"I need more context to ask this question: {question}"

    try:
        # Persist and notify via centralized chat session helper (single writer)
        try:
            from app.api.v1.endpoints.chat_sessions import ask_user_question_and_wait
            # Delegate storing the question and waiting for reply to chat sessions module
            reply = await ask_user_question_and_wait(session_id, user_id, question, timeout_sec=300.0)
            return reply
        except Exception:
            pass
    finally:
        pass


# Removed legacy local pending-response helpers; centralized in chat_sessions module


async def run_initial_panel(state: MedicalDoctorState) -> MedicalDoctorState:
    try:
        panel = MedicalDoctorPanel(
            api_key=settings.OPENAI_API_KEY,
            budget_limit=state.get("budget_limit"),
            question_rounds_limit=max(0, int(state.get("max_question_rounds", 2))),
            questions_per_round_limit=max(1, int(state.get("max_questions_per_round", 5))),
        )

        decision = panel.process_patient_case(state["patient_case"], state.get("budget_limit"))

        state["panel_decision"] = decision
        raw_questions = decision.get("questions", []) if isinstance(decision, dict) else []
        # Remove duplicates and already-asked questions
        asked = set(state.get("asked_questions", []))
        state["questions"] = [q for q in raw_questions if q not in asked]
        state["question_round"] = 0

        # Append step to conversation log
        state["conversation_log"].append({
            "type": "initial_decision",
            "decision": decision,
            "timestamp": datetime.now().isoformat()
        })

        state["error"] = ""
    except Exception as e:
        state["error"] = f"Error running initial panel: {str(e)}"
    return state


def _what_next(state: MedicalDoctorState) -> str:
    if state.get("error"):
        return "handle_error"
    decision = state.get("panel_decision") or {}
    action = (decision.get("action") or "").lower() if isinstance(decision, dict) else ""
    if action == "ask_questions" and state.get("questions"):
        return "ask_questions"
    return "synthesize_response"


async def ask_questions(state: MedicalDoctorState) -> MedicalDoctorState:
    try:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        asked_questions = state.get("asked_questions", [])
        answers: Dict[str, str] = {}

        pending_questions = [q for q in state.get("questions", []) if q not in asked_questions]
        max_per_round = max(1, int(state.get("max_questions_per_round", 8)))
        current_round_questions = pending_questions[:max_per_round]

        for q in current_round_questions:
            ans = await ask_user_question(q, session_id, user_id)
            answers[q] = ans or ""
            asked_questions.append(q)

        # Merge into cumulative answers
        cumulative_answers = state.get("answers", {})
        cumulative_answers.update(answers)
        state["answers"] = cumulative_answers
        state["asked_questions"] = asked_questions
        state["question_round"] = int(state.get("question_round", 0)) + 1

        # Update remaining questions to ensure we exhaust the current list
        remaining_after_round = [q for q in state.get("questions", []) if q not in asked_questions]
        state["questions"] = remaining_after_round

        # Log Q&A
        state["conversation_log"].append({
            "type": "questions_asked",
            "questions": current_round_questions,
            "answers": answers,
            "timestamp": datetime.now().isoformat()
        })
        state["error"] = ""
    except Exception as e:
        state["error"] = f"Error asking questions: {str(e)}"
    return state


async def run_followup_panel(state: MedicalDoctorState) -> MedicalDoctorState:
    try:
        # Build updated case with Q&A and run a new debate round
        base_case = state.get("patient_case", "")
        questions = list(state.get("answers", {}).keys())
        answers = state.get("answers", {})

        follow_up_section = "\n\nFOLLOW-UP INFORMATION:\n" + ("=" * 50) + "\n"
        for q in questions:
            follow_up_section += f"Q: {q}\nA: {answers.get(q, '')}\n\n"
        updated_case = base_case + follow_up_section

        # Create a new panel with remaining-rounds as its allowed limit (single-source constraints in panel)
        total_rounds = max(0, int(state.get("max_question_rounds", 2)))
        used_rounds = int(state.get("question_round", 0))
        remaining_rounds = max(0, total_rounds - used_rounds)
        panel = MedicalDoctorPanel(
            api_key=settings.OPENAI_API_KEY,
            budget_limit=state.get("budget_limit"),
            question_rounds_limit=remaining_rounds,
            questions_per_round_limit=max(1, int(state.get("max_questions_per_round", 5))),
        )
        followup_decision = panel.conduct_chain_of_debate(updated_case)
        state["followup_decision"] = followup_decision

        # Log follow-up decision
        state["conversation_log"].append({
            "type": "followup_decision",
            "decision": followup_decision,
            "timestamp": datetime.now().isoformat()
        })

        # Update next-round questions (exclude already asked)
        asked = set(state.get("asked_questions", []))
        next_questions = followup_decision.get("questions", []) if isinstance(followup_decision, dict) else []
        state["questions"] = [q for q in next_questions if q not in asked]

        state["error"] = ""
    except Exception as e:
        state["error"] = f"Error running follow-up panel: {str(e)}"
    return state


def _should_followup(state: MedicalDoctorState) -> str:
    if state.get("error"):
        return "handle_error"
    decision = state.get("followup_decision") or {}
    action = (decision.get("action") or "").lower() if isinstance(decision, dict) else ""
    rounds = int(state.get("question_round", 0))
    max_rounds = max(0, int(state.get("max_question_rounds", 2)))
    has_more_questions = bool(state.get("questions"))
    if action == "ask_questions":
        if has_more_questions and rounds < max_rounds:
            return "ask_questions"
        # Panel still wants more, but we've hit the cap → run panel once more with 0 remaining to force a decision
        return "run_followup_panel"
    return "synthesize_response"


def _after_ask_questions(state: MedicalDoctorState) -> str:
    # If there are still pending questions from the current batch, keep asking
    if state.get("error"):
        return "handle_error"
    remaining_pending = [q for q in state.get("questions", []) if q not in state.get("asked_questions", [])]
    if remaining_pending:
        return "ask_questions"
    # No pending questions left from current batch → move to follow-up panel
    return "run_followup_panel"


def synthesize_response(state: MedicalDoctorState) -> MedicalDoctorState:
    try:
        results: Dict[str, Any] = {
            "initial_decision": state.get("panel_decision"),
            "followup_decision": state.get("followup_decision"),
            "questions": state.get("questions", []),
            "answers": state.get("answers", {}),
            "conversation_log": state.get("conversation_log", [])
        }

        # Prefer follow-up decision message if present, else initial
        final_message = ""
        if isinstance(state.get("followup_decision"), dict):
            final_message = state["followup_decision"].get("details") or ""
        if not final_message and isinstance(state.get("panel_decision"), dict):
            final_message = state["panel_decision"].get("details") or ""
        if not final_message:
            final_message = "Medical analysis completed. Review the decisions and next steps above."

        state["response_data"] = format_agent_response(
            success=True,
            task_types=["medical_doctor"],
            results=results,
            execution_log=[],
            message=final_message,
            title="Medical Consultation",
            error=None
        )
        state["processing_complete"] = True
        state["error"] = ""
    except Exception as e:
        state["error"] = f"Error synthesizing response: {str(e)}"
    return state


def handle_error(state: MedicalDoctorState) -> MedicalDoctorState:
    error = state.get("error", "Unknown error")
    state["response_data"] = format_error_response(
        error_message=error,
        execution_log=state.get("conversation_log", []),
        task_types=["medical_doctor"]
    )
    state["processing_complete"] = True
    return state


async def create_medical_doctor_workflow():
    workflow = StateGraph(MedicalDoctorState)

    workflow.add_node("run_initial_panel", run_initial_panel)
    workflow.add_node("ask_questions", ask_questions)
    workflow.add_node("run_followup_panel", run_followup_panel)
    workflow.add_node("synthesize_response", synthesize_response)
    workflow.add_node("handle_error", handle_error)

    workflow.add_edge(START, "run_initial_panel")

    workflow.add_conditional_edges(
        "run_initial_panel",
        _what_next,
        {
            "ask_questions": "ask_questions",
            "synthesize_response": "synthesize_response",
            "handle_error": "handle_error",
        },
    )

    # After asking questions, continue asking until all pending questions are exhausted
    workflow.add_conditional_edges(
        "ask_questions",
        _after_ask_questions,
        {
            "ask_questions": "ask_questions",
            "run_followup_panel": "run_followup_panel",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "run_followup_panel",
        _should_followup,
        {
            "ask_questions": "ask_questions",
            "synthesize_response": "synthesize_response",
            "handle_error": "handle_error",
        },
    )

    workflow.add_edge("synthesize_response", END)
    workflow.add_edge("handle_error", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


async def process_medical_request_async(
    user_id: str,
    patient_case: str,
    session_id: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    budget_limit: Optional[float] = None,
) -> Dict[str, Any]:
    initial_state: MedicalDoctorState = {
        "user_id": user_id,
        "session_id": session_id,
        "patient_case": patient_case,
        "budget_limit": budget_limit,
        "questions": [],
        "answers": {},
        "asked_questions": [],
        "question_round": 0,
        "max_question_rounds": 2,
        "max_questions_per_round": 5,
        "panel_decision": None,
        "followup_decision": None,
        "conversation_log": [],
        "error": "",
        "processing_complete": False,
        "response_data": None,
    }

    app = await create_medical_doctor_workflow()
    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": f"medical-doctor-{user_id}"}},
    )

    # Return standardized response_data when available
    if result.get("response_data"):
        return result["response_data"]

    # Fallback minimal structure
    return {
        "success": not bool(result.get("error")),
        "results": {
            "initial_decision": result.get("panel_decision"),
            "followup_decision": result.get("followup_decision"),
            "questions": result.get("questions", []),
            "answers": result.get("answers", {}),
        },
        "message": "Medical consultation completed.",
        "title": "Medical Consultation",
        "error": result.get("error"),
    }


def process_medical_request(
    user_id: str,
    patient_case: str,
    session_id: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    budget_limit: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, process_medical_request_async(user_id, patient_case, session_id, conversation_history, budget_limit))
            return future.result()
    except RuntimeError:
        return asyncio.run(process_medical_request_async(user_id, patient_case, session_id, conversation_history, budget_limit))


