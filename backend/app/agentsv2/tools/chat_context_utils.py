from __future__ import annotations

from typing import Dict, Any, List, Optional


async def ask_question_with_post_context(
    session_id: int,
    user_id: str,
    question_text: str,
    timeout_sec: float = 300.0,
    max_context_chars: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ask a question to the user and return their response along with chat messages
    posted after the question was asked (post-question context).

    Returns a dict with keys: question, response, post_question_context (list), context_plus_response (str).
    """
    from psycopg2.extras import RealDictCursor
    from app.core.database_utils import get_raw_db_connection

    # Record message boundary just before asking the question
    last_message_id = 0
    try:
        with get_raw_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT COALESCE(MAX(id), 0) AS max_id FROM chat_messages WHERE session_id = %s",
                    [session_id],
                )
                row = cursor.fetchone() or {"max_id": 0}
                last_message_id = int(row.get("max_id") or 0)
    except Exception:
        last_message_id = 0

    # Ask the question via centralized helper (prefer workflow helper, fallback to API endpoint)
    reply: str = ""
    try:
        from app.agentsv2.customer_workflow import ask_user_question
        reply = await ask_user_question(question_text, session_id, str(user_id))
    except Exception:
        try:
            from app.api.v1.endpoints.chat_sessions import ask_user_question_and_wait
            reply = await ask_user_question_and_wait(session_id, str(user_id), question_text, timeout_sec=timeout_sec)
        except Exception as e:
            reply = f"Error asking question: {e}"

    # Fetch messages added after the question (exclude the question itself)
    post_context: List[Dict[str, Any]] = []
    try:
        with get_raw_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, role, content, created_at
                    FROM chat_messages
                    WHERE session_id = %s AND id > %s
                    ORDER BY id ASC
                    """,
                    [session_id, last_message_id],
                )
                rows = cursor.fetchall() or []
                # Identify the assistant question message id (if present) to exclude and only keep messages after it
                assistant_question_ids = [
                    int(r["id"]) for r in rows
                    if (str(r.get("role")) == "assistant" and str(r.get("content", "")).strip() == str(question_text).strip())
                ]
                min_after_id = max([last_message_id] + assistant_question_ids)
                filtered = [r for r in rows if int(r["id"]) > min_after_id]
                # Exclude the user's own reply from post-question context so only additional context remains
                reply_str = (str(reply).strip() if reply is not None else "")
                removed_reply_once = False
                for r in filtered:
                    r_role = str(r.get("role"))
                    r_content = str(r.get("content", "")).strip()
                    if not removed_reply_once and r_role == "user" and r_content == reply_str:
                        removed_reply_once = True
                        continue
                    content_to_store = r_content if max_context_chars is None else r_content[:max_context_chars]
                    post_context.append({
                        "id": int(r.get("id")),
                        "role": r_role,
                        "content": content_to_store,
                        "created_at": (r.get("created_at").isoformat() if r.get("created_at") else None),
                    })
    except Exception:
        post_context = []

    # Build combined context text + user response
    try:
        ctx_lines = [f"{m['role']}: {m['content']}" for m in post_context]
        combined_context = "\n".join(ctx_lines).strip()
    except Exception:
        combined_context = ""

    return {
        "question": question_text,
        "response": str(reply) if reply is not None else "",
        "post_question_context": post_context,
        "context_plus_response": (combined_context + ("\nUser: " + str(reply) if reply else "")).strip(),
    }


