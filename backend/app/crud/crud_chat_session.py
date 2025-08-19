from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import uuid
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.chat_session import ChatSession, ChatMessage, Prescription
from app.schemas.chat_session import (
    ChatSessionCreate, ChatSessionUpdate, 
    ChatMessageCreate, ChatMessageUpdate,
    PrescriptionCreate, PrescriptionUpdate
)


class CRUDChatSession(CRUDBase[ChatSession, ChatSessionCreate, ChatSessionUpdate]):
    def create_with_user(
        self, db: Session, *, obj_in: ChatSessionCreate, user_id: int
    ) -> ChatSession:
        obj_in_data = obj_in.model_dump()
        obj_in_data["user_id"] = user_id
        # Set default values for optional fields
        obj_in_data.setdefault("has_verification", False)
        obj_in_data.setdefault("has_prescriptions", False)
        obj_in_data.setdefault("is_active", True)
        obj_in_data.setdefault("message_count", 0)
        
        # Set timestamps explicitly (database defaults will handle this, but being explicit)
        now = datetime.now()
        obj_in_data.setdefault("created_at", now)
        obj_in_data.setdefault("updated_at", now)
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_user_sessions(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[ChatSession]:
        return (
            db.query(self.model)
            .filter(ChatSession.user_id == user_id)
            .filter(ChatSession.is_active == True)
            .order_by(desc(ChatSession.last_message_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_session_with_messages(
        self, db: Session, *, session_id: int, user_id: int
    ) -> Optional[ChatSession]:
        return (
            db.query(self.model)
            .filter(ChatSession.id == session_id)
            .filter(ChatSession.user_id == user_id)
            .filter(ChatSession.is_active == True)
            .first()
        )

    def update_session_stats(
        self, db: Session, *, session_id: int, message_count: int = None, 
        has_verification: bool = None, has_prescriptions: bool = None
    ) -> Optional[ChatSession]:
        db_obj = db.query(self.model).filter(ChatSession.id == session_id).first()
        if db_obj:
            if message_count is not None:
                db_obj.message_count = message_count
            if has_verification is not None:
                db_obj.has_verification = has_verification
            if has_prescriptions is not None:
                db_obj.has_prescriptions = has_prescriptions
            db_obj.last_message_at = func.now()
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def soft_delete(self, db: Session, *, session_id: int, user_id: int) -> bool:
        db_obj = (
            db.query(self.model)
            .filter(ChatSession.id == session_id)
            .filter(ChatSession.user_id == user_id)
            .first()
        )
        if db_obj:
            db_obj.is_active = False
            db.commit()
            return True
        return False


class CRUDChatMessage(CRUDBase[ChatMessage, ChatMessageCreate, ChatMessageUpdate]):
    def create_with_session(
        self, db: Session, *, obj_in: ChatMessageCreate, session_id: int
    ) -> ChatMessage:
        obj_in_data = obj_in.model_dump()
        obj_in_data["session_id"] = session_id
        
        # Get the user_id from the session
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        obj_in_data["user_id"] = session.user_id
        
        # Always set created_at explicitly
        obj_in_data["created_at"] = datetime.now()
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        # Update session message count and last message time
        session.message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
        session.last_message_at = datetime.now()
        db.commit()
        
        return db_obj

    async def create_with_session_notify(
        self, db: Session, *, obj_in: ChatMessageCreate, session_id: int, notify_websocket: bool = True
    ) -> ChatMessage:
        """Create message with session and optionally send WebSocket notification"""
        # Create the message normally
        db_obj = self.create_with_session(db, obj_in=obj_in, session_id=session_id)
        
        # Send WebSocket notification if requested
        if notify_websocket:
            try:
                from app.api.v1.endpoints.chat_sessions import connection_manager
                from app.schemas.chat_session import ChatMessage as ChatMessageSchema
                
                # Convert database model to schema for WebSocket
                message_schema = ChatMessageSchema(
                    id=db_obj.id,
                    session_id=session_id,
                    user_id=db_obj.user_id,
                    role=db_obj.role,
                    content=db_obj.content,
                    created_at=db_obj.created_at,
                    file_path=db_obj.file_path,
                    file_type=db_obj.file_type
                )
                
                # Get current message count
                total_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
                
                # Send notification
                await connection_manager.notify_message_added(session_id, message_schema, total_count)
                print(f"📨 [CRUD] Sent WebSocket notification for new message in session {session_id}")
                
            except Exception as e:
                print(f"⚠️ [CRUD] Failed to send WebSocket notification: {e}")
                # Don't fail the message creation if WebSocket notification fails
        
        return db_obj

    def get_session_messages(
        self, db: Session, *, session_id: int, skip: int = 0, limit: int = 1000
    ) -> List[ChatMessage]:
        return (
            db.query(self.model)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )


class CRUDPrescription(CRUDBase[Prescription, PrescriptionCreate, PrescriptionUpdate]):
    def create_with_session(
        self, db: Session, *, obj_in: PrescriptionCreate, session_id: int
    ) -> Prescription:
        obj_in_data = obj_in.model_dump()
        obj_in_data["session_id"] = session_id
        # Generate UUID for prescription ID since it's still a string field
        obj_in_data["id"] = str(uuid.uuid4())
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        # Update session prescriptions flag
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.has_prescriptions = True
            db.commit()
        
        return db_obj

    def get_session_prescriptions(
        self, db: Session, *, session_id: int
    ) -> List[Prescription]:
        return (
            db.query(self.model)
            .filter(Prescription.session_id == session_id)
            .order_by(desc(Prescription.prescribed_at))
            .all()
        )

    def get_user_prescriptions(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Prescription]:
        return (
            db.query(self.model)
            .join(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .filter(ChatSession.is_active == True)
            .order_by(desc(Prescription.prescribed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


# Create instances
chat_session = CRUDChatSession(ChatSession)
chat_message = CRUDChatMessage(ChatMessage)
prescription = CRUDPrescription(Prescription) 