from typing import List
from sqlalchemy.orm import Session
from app import crud
from app.utils.openai_client import get_chat_completion
from app.models.chat_session import ChatMessage
from app.schemas.chat_session import ChatMessageCreate

class ChatService:
    def __init__(self, db: Session):
        self.db = db

    async def process_message(self, message: str) -> str:
        """Process a chat message and return a response"""
        # Mock response for testing
        return f"Received: {message}"

async def process_chat_message(
    db: Session,
    user_id: int,
    session_id: int,
    content: str
) -> tuple[ChatMessage, ChatMessage]:
    """
    Process a chat message and get AI response.
    
    Args:
        db: Database session
        user_id: ID of the user sending the message
        session_id: ID of the chat session
        content: Message content
        
    Returns:
        Tuple of (user_message, ai_message)
    """
    # Create user message
    user_message = crud.chat_message.create_with_session(
        db,
        obj_in=ChatMessageCreate(
            content=content,
            role="user"
        ),
        session_id=session_id
    )
    
    # Get session history
    session_messages = crud.chat_message.get_session_messages(db, session_id=session_id)
    
    # Format messages for OpenAI
    messages = [
        {
            "role": msg.role,
            "content": msg.content
        }
        for msg in session_messages  # Include all messages
    ]
    
    # Add system message for context
    messages.insert(0, {
        "role": "system",
        "content": (
            "You are a helpful AI health assistant. Provide accurate, helpful, "
            "and empathetic responses to health-related questions. If you're unsure "
            "about something, say so and recommend consulting a healthcare professional."
        )
    })
    
    # Get AI response
    ai_response = await get_chat_completion(messages)
    
    # Create AI message
    ai_message = crud.chat_message.create_with_session(
        db,
        obj_in=ChatMessageCreate(
            content=ai_response,
            role="assistant"
        ),
        session_id=session_id
    )
    
    return user_message, ai_message 