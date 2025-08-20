from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime, timedelta
import traceback
import asyncio
import threading
import json

from app import crud, models, schemas
from app.api import deps
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from app.core.config import settings
from app.models.chat_session import ChatMessage as ChatMessageModel, ChatSession as ChatSessionModel
from app.schemas.chat_session import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionWithMessages,
    ChatMessageCreate, ChatMessageResponse,
    Prescription, PrescriptionCreate, PrescriptionWithSession,
    SyncChatRequest, SyncChatResponse, EnhancedChatMessageResponse,
    StreamingChatResponse, ChatStatusMessage, StreamingChunk,
    EnhancedChatMessage, QuickReply, InteractiveComponent,
    ChatSession, ChatMessage
)

router = APIRouter()


# WebSocket Connection Manager for real-time chat status
class ChatConnectionManager:
    """Manages WebSocket connections for real-time chat status updates"""
    
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}  # session_id -> [websockets]
    
    async def connect(self, websocket: WebSocket, session_id: int):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        print(f"🔌 [ChatConnectionManager] WebSocket connected for session {session_id}")
    
    def disconnect(self, websocket: WebSocket, session_id: int):
        if session_id in self.active_connections:
            try:
                self.active_connections[session_id].remove(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
                print(f"🔌 [ChatConnectionManager] WebSocket disconnected for session {session_id}")
            except ValueError:
                pass  # WebSocket already removed
    
    async def send_status_update(self, session_id: int, status_message: ChatStatusMessage):
        """Send status update to all connected clients for a session - NO DATABASE SAVING"""
        
        # Simply send WebSocket status update - don't save to database
        if session_id in self.active_connections:
            message = status_message.model_dump_json()
            disconnected = []
            
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message)
                    print(f"📡 [Status] Sent status update: {status_message.status} to session {session_id}")
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection, session_id)
        else:
            print(f"⚠️ [Status] No active connections for session {session_id}")
    
    async def notify_message_added(self, session_id: int, new_message: ChatMessage, total_count: int):
        """Convenience method to notify about a new message being added"""
        import json
        
        # Create message data as JSON string
        message_data = {
            "message_type": "new_message",
            "new_message": {
                "id": new_message.id,
                "role": new_message.role,
                "content": new_message.content,
                "timestamp": new_message.created_at.isoformat() if new_message.created_at else None,
                "filePath": new_message.file_path,
                "fileType": new_message.file_type,
                "fileName": None  # This field doesn't exist in the schema
            },
            "message_count": total_count,
            "last_message_id": new_message.id
        }
        
        # Send as ChatStatusMessage with special status
        status_message = ChatStatusMessage(
            session_id=session_id,
            status="message_added",
            message=json.dumps(message_data),
            progress=1.0,
            agent_name="System"
        )
        
        await self.send_status_update(session_id, status_message)


# Global connection manager instance
connection_manager = ChatConnectionManager()

# Cache for storing processed messages for streaming
message_cache: dict[str, dict[str, Any]] = {}

# Centralized pending-response coordination for agent questions
pending_response_events: dict[str, asyncio.Event] = {}
pending_responses: dict[str, str] = {}
_pending_lock = threading.Lock()
async def _wait_for_ws_connection(session_id: int, timeout_seconds: float = 20.0):
    """Wait briefly for a /status WebSocket connection to be active for this session."""
    try:
        checks = int(timeout_seconds * 10)
        for _ in range(checks):
            if connection_manager.active_connections.get(session_id):
                return
            await asyncio.sleep(0.1)
    except Exception:
        pass


async def persist_assistant_message_and_notify(session_id: int, message_in: ChatMessageCreate) -> ChatMessage:
    """Persist an assistant message and notify connected clients, waiting briefly for WS attachment."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        # Ensure role is assistant for clarity
        message_in.role = message_in.role or "assistant"
        if message_in.role != "assistant":
            message_in.role = "assistant"

        message = crud.chat_message.create_with_session(db=db, obj_in=message_in, session_id=session_id)
        db.commit()

        # Wait for WS connection if needed (longer to catch UI attachment)
        await _wait_for_ws_connection(session_id, 20.0)

        # Notify clients
        try:
            from app.schemas.chat_session import ChatMessage as ChatMessageSchema
            from app.models.chat_session import ChatMessage as ChatMessageModel

            message_schema = ChatMessageSchema(
                id=message.id,
                session_id=session_id,
                user_id=message.user_id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                file_path=message.file_path,
                file_type=message.file_type,
                visualizations=message.visualizations
            )

            total_count = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).count()
            await connection_manager.notify_message_added(session_id, message_schema, total_count)
        except Exception:
            pass

        return message
    finally:
        db.close()


def _create_pending_response_key(session_id: int) -> str:
    import time
    ts = int(time.time() * 1000000)
    return f"user_response_{session_id}_{ts}"


def chat_session_get_pending_response_keys() -> list[str]:
    with _pending_lock:
        return list(pending_response_events.keys())


def chat_session_set_user_response(response_key: str, response: str):
    with _pending_lock:
        if response_key in pending_responses:
            pending_responses[response_key] = response
            if response_key in pending_response_events:
                pending_response_events[response_key].set()


async def ask_user_question_and_wait(session_id: int, user_id: str, question: str, timeout_sec: float = 300.0) -> str:
    """Persist an assistant question, notify clients, and wait for a user reply.

    This is the single entry-point other modules should use to ask users questions.
    """
    # Register a pending response event
    response_key = _create_pending_response_key(session_id)
    with _pending_lock:
        pending_response_events[response_key] = asyncio.Event()
        pending_responses[response_key] = ""

    try:
        # Persist and notify the assistant question
        await persist_assistant_message_and_notify(
            session_id,
            ChatMessageCreate(
                role="assistant",
                content=question,
                tokens_used=0,
                response_time_ms=0,
            ),
        )

        # Wait for user reply bound via handle_agent_question_response
        try:
            await asyncio.wait_for(pending_response_events[response_key].wait(), timeout=timeout_sec)
            with _pending_lock:
                reply = pending_responses.get(response_key, "")
            return reply or "No response received"
        except asyncio.TimeoutError:
            return "User did not respond within the timeout period"
    finally:
        with _pending_lock:
            pending_response_events.pop(response_key, None)
            pending_responses.pop(response_key, None)



def handle_agent_question_response(session_id: int, user_message: str) -> bool:
    """
    Check if the user message is a response to a pending agent question.
    If so, set the response and return True. Otherwise return False.
    """
    try:
        # First, check centralized pending store
        with _pending_lock:
            session_keys = [k for k in pending_response_events.keys() if f"user_response_{session_id}_" in k]
        if session_keys:
            # Use FIFO so replies map to the earliest unanswered question
            session_keys.sort(key=lambda k: int(k.split('_')[-1]))
            response_key = session_keys[0]
            print(f"🔄 [handle_agent_question_response] Setting centralized response (FIFO) for key {response_key}")
            chat_session_set_user_response(response_key, user_message)
            return True

        # Backward compatibility: also check legacy workflow-managed stores
        cw_get = cw_set = md_get = md_set = None
        try:
            from app.agentsv2.customer_workflow import get_pending_response_keys as cw_get, set_user_response as cw_set
        except Exception:
            pass
        try:
            from app.agentsv2.medical_doctor_workflow import get_pending_response_keys as md_get, set_user_response as md_set
        except Exception:
            pass

        key_setter_pairs: list[tuple[str, Any]] = []
        if cw_get and cw_set:
            try:
                for key in cw_get():
                    key_setter_pairs.append((key, cw_set))
            except Exception:
                pass
        if md_get and md_set:
            try:
                for key in md_get():
                    key_setter_pairs.append((key, md_set))
            except Exception:
                pass

        session_pairs = [(k, setter) for (k, setter) in key_setter_pairs if f"user_response_{session_id}_" in k]
        if session_pairs:
            # Use FIFO for legacy stores as well
            session_pairs.sort(key=lambda pair: int(pair[0].split('_')[-1]))
            response_key, setter_fn = session_pairs[0]
            print(f"🔄 [handle_agent_question_response] Setting legacy response (FIFO) for key {response_key}")
            setter_fn(response_key, user_message)
            return True

        print(f"ℹ️  [handle_agent_question_response] No pending questions for session {session_id}")
        return False
    except Exception as e:
        print(f"❌ [handle_agent_question_response] Error: {e}")
        import traceback
        print(f"❌ [handle_agent_question_response] Traceback: {traceback.format_exc()}")
        return False


@router.get("/", response_model=List[ChatSession])
def get_user_chat_sessions(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve chat sessions for the current user.
    """
    sessions = crud.chat_session.get_user_sessions(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return sessions


@router.post("/", response_model=ChatSession)
def create_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    session_in: ChatSessionCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new chat session.
    """
    # Apply enhanced mode configuration from backend settings
    if settings.ENHANCED_CHAT_MODE_OVERRIDE is not None:
        # Global override setting takes precedence
        session_in.enhanced_mode_enabled = settings.ENHANCED_CHAT_MODE_OVERRIDE
    elif not hasattr(session_in, 'enhanced_mode_enabled') or session_in.enhanced_mode_enabled is None:
        # Use default setting if not specified
        session_in.enhanced_mode_enabled = settings.ENHANCED_CHAT_MODE_DEFAULT
    
    session = crud.chat_session.create_with_user(
        db=db, obj_in=session_in, user_id=current_user.id
    )
    return session


@router.post("/new", response_model=ChatSession)
def create_new_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new chat session with default title "New Chat".
    Convenient endpoint for frontend "New Chat" button.
    """
    session_in = ChatSessionCreate()  # Uses default title "New Chat"
    
    # Apply enhanced mode configuration from backend settings
    if settings.ENHANCED_CHAT_MODE_OVERRIDE is not None:
        # Global override setting takes precedence
        session_in.enhanced_mode_enabled = settings.ENHANCED_CHAT_MODE_OVERRIDE
    else:
        # Use default setting
        session_in.enhanced_mode_enabled = settings.ENHANCED_CHAT_MODE_DEFAULT
    
    session = crud.chat_session.create_with_user(
        db=db, obj_in=session_in, user_id=current_user.id
    )
    return session


@router.get("/statistics")
def get_chat_session_statistics(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get aggregate statistics about chat sessions for authenticated users.
    """
    try:
        # Use the CRUD operations to get session data safely
        sessions = crud.chat_session.get_user_sessions(db=db, user_id=current_user.id, skip=0, limit=100)
        
        # Calculate statistics from the fetched sessions
        total_sessions = len(sessions)
        active_sessions = 0
        total_messages = 0
        
        # Get message count for each session and check activity
        yesterday = datetime.now() - timedelta(hours=24)
        
        formatted_sessions = []
        for session in sessions[:20]:  # Limit to 20 for display
            # Count messages for this session
            session_messages = crud.chat_message.get_session_messages(db=db, session_id=session.id, skip=0, limit=1000)
            total_messages += len(session_messages)
            
            # Check if session is active (had activity in last 24 hours)
            if session.last_message_at and session.last_message_at.replace(tzinfo=None) >= yesterday:
                active_sessions += 1
                session_status = "active"
            else:
                session_status = "completed"
            
            formatted_sessions.append({
                "session_id": str(session.id),
                "user_id": str(session.user_id),
                "start_time": session.created_at.isoformat() if session.created_at else "",
                "end_time": session.last_message_at.isoformat() if session.last_message_at else "",
                "total_messages": session.message_count or len(session_messages),
                "agents_involved": ["CustomerAgent", "DoctorAgent"],
                "session_status": session_status
            })
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "active_agents": 2,  # CustomerAgent and DoctorAgent
            "active_sessions": active_sessions,
            "sessions": formatted_sessions
        }
        
    except Exception as e:
        print(f"Error in statistics endpoint: {e}")
        # Return empty stats on error
        return {
            "total_sessions": 0,
            "total_messages": 0,
            "active_agents": 2,
            "active_sessions": 0,
            "sessions": []
        }


@router.get("/{session_id}", response_model=ChatSessionWithMessages)
def get_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a chat session with its messages and prescriptions.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return session


@router.put("/{session_id}", response_model=ChatSession)
def update_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    session_in: ChatSessionUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    session = crud.chat_session.update(db=db, db_obj=session, obj_in=session_in)
    return session


@router.delete("/{session_id}")
def delete_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a chat session (soft delete).
    """
    success = crud.chat_session.soft_delete(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return {"message": "Session deleted successfully"}


# Direct message endpoint (no AI generation)
@router.post("/{session_id}/direct-message")
async def add_direct_message_to_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    message_in: ChatMessageCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Add a message to a chat session without generating AI response.
    Used for doctor responses and system messages.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Store the message directly
    message = crud.chat_message.create_with_session(
        db=db, obj_in=message_in, session_id=session_id
    )
    
    return {"message": "Message saved successfully", "id": message.id}

## [Deprecated] Non-stream messaging endpoint removed. Use /{session_id}/messages/stream.


## [Deprecated] Non-stream file upload endpoint removed. Use /{session_id}/messages/upload/stream.


@router.get("/{session_id}/messages", response_model=List[ChatMessage])
def get_session_messages(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    skip: int = 0,
    limit: int = 1000,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get messages for a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    messages = crud.chat_message.get_session_messages(
        db=db, session_id=session_id, skip=skip, limit=limit
    )
    return messages


# Prescription endpoints
@router.post("/{session_id}/prescriptions", response_model=Prescription)
def add_prescription_to_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    prescription_in: PrescriptionCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Add a prescription to a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    prescription = crud.prescription.create_with_session(
        db=db, obj_in=prescription_in, session_id=session_id
    )
    return prescription


@router.get("/{session_id}/prescriptions", response_model=List[Prescription])
def get_session_prescriptions(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get prescriptions for a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    prescriptions = crud.prescription.get_session_prescriptions(
        db=db, session_id=session_id
    )
    return prescriptions


# Get all user prescriptions
@router.get("/prescriptions/all", response_model=List[PrescriptionWithSession])
def get_all_user_prescriptions(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get all prescriptions for the current user across all sessions.
    """
    prescriptions = crud.prescription.get_user_prescriptions(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return prescriptions


# Get all user prescriptions with enhanced data for patient app
@router.get("/prescriptions/patient", response_model=List[dict])
def get_patient_prescriptions_enhanced(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get all prescriptions for the current user with enhanced data including doctor and session info.
    """
    from sqlalchemy.orm import joinedload
    from app.models.chat_session import Prescription
    from app.models.doctor import ConsultationRequest, Doctor
    
    # Get prescriptions with session data
    prescriptions = db.query(Prescription).join(ChatSessionModel).filter(
        ChatSessionModel.user_id == current_user.id
    ).options(joinedload(Prescription.session)).order_by(
        Prescription.prescribed_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for prescription in prescriptions:
        # Try to find associated consultation request and doctor
        consultation_request = db.query(ConsultationRequest).filter(
            ConsultationRequest.chat_session_id == prescription.session_id
        ).first()
        
        doctor_name = "Unknown Doctor"
        consultation_id = None
        
        if consultation_request:
            consultation_id = consultation_request.id
            doctor = db.query(Doctor).filter(Doctor.id == consultation_request.doctor_id).first()
            if doctor:
                doctor_name = doctor.full_name
        
        # If no consultation found, use prescribed_by from prescription
        if doctor_name == "Unknown Doctor":
            doctor_name = prescription.prescribed_by or "Unknown Doctor"
        
        prescription_data = {
            "id": str(prescription.id),
            "medication_name": prescription.medication_name,
            "dosage": prescription.dosage or "",
            "frequency": prescription.frequency or "",
            "instructions": prescription.instructions or "",
            "prescribed_by": prescription.prescribed_by,
            "prescribed_at": prescription.prescribed_at.isoformat(),
            "consultation_id": consultation_id or 0,
            "chat_session_id": None if not consultation_request else consultation_request.chat_session_id,
            "doctor_name": doctor_name,
            "session_title": prescription.session.title if prescription.session else "Chat Session"
        }
        result.append(prescription_data)
    
    print(f"📊 [Chat Sessions API] Returning {len(result)} prescriptions for patient")
    return result


# Sync endpoint for offline data
@router.post("/sync", response_model=SyncChatResponse)
def sync_chat_data(
    *,
    db: Session = Depends(deps.get_db),
    sync_data: SyncChatRequest,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Sync chat data from client to server (for offline scenarios).
    """
    try:
        synced_sessions = 0
        synced_messages = 0
        synced_prescriptions = 0
        
        # Sync sessions
        for session_data in sync_data.sessions:
            crud.chat_session.create_with_user(
                db=db, obj_in=session_data, user_id=current_user.id
            )
            synced_sessions += 1
        
        # Sync messages
        for message_data in sync_data.messages:
            crud.chat_message.create_with_session(
                db=db, obj_in=message_data, session_id=message_data.session_id
            )
            synced_messages += 1
        
        # Sync prescriptions
        for prescription_data in sync_data.prescriptions:
            crud.prescription.create_with_session(
                db=db, obj_in=prescription_data, session_id=prescription_data.session_id
            )
            synced_prescriptions += 1
        
        return SyncChatResponse(
            success=True,
            synced_sessions=synced_sessions,
            synced_messages=synced_messages,
            synced_prescriptions=synced_prescriptions,
            message="Data synced successfully"
        )
    except Exception as e:
        return SyncChatResponse(
            success=False,
            synced_sessions=0,
            synced_messages=0,
            synced_prescriptions=0,
            message=f"Sync failed: {str(e)}"
        )


# WebSocket endpoint for real-time chat status updates
@router.websocket("/{session_id}/status")
async def websocket_chat_status(
    websocket: WebSocket,
    session_id: int,
    # Note: WebSocket auth would need to be handled differently in production
):
    """WebSocket endpoint for real-time chat status updates"""
    print(f"🔌 [WebSocket] New connection attempt for session {session_id}")
    await connection_manager.connect(websocket, session_id)
    print(f"✅ [WebSocket] Successfully connected for session {session_id}")
    # Notify clients (including the just-connected one) so UIs can optionally reload history
    try:
        await connection_manager.send_status_update(session_id, ChatStatusMessage(
            session_id=session_id,
            status="connected",
            message=None,
            progress=0.0,
            agent_name="System"
        ))
    except Exception:
        pass
    try:
        while True:
            # Keep connection alive and listen for disconnect
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print(f"❌ [WebSocket] Client disconnected from session {session_id}")
        connection_manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"❌ [WebSocket] Error in session {session_id}: {e}")
        connection_manager.disconnect(websocket, session_id)


# Streaming chat message endpoint

# Streaming upload message endpoint
@router.post("/{session_id}/messages/upload/stream", response_model=StreamingChatResponse)
async def stream_message_with_file_to_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    content: str = Form(""),
    file: Optional[UploadFile] = File(None),
) -> Any:
    """
    Add a message with an optional file upload and stream the AI response.
    Returns immediately with StreamingChatResponse.
    """
    # Verify session exists
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Handle file saving similar to add_message_with_file_to_session
    file_info = None
    if file:
        allowed_types = ["jpg", "jpeg", "png", "pdf"]
        ext = file.filename.split(".")[-1].lower() if file.filename else ""
        if ext not in allowed_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File type {ext} not supported. Allowed types: {', '.join(allowed_types)}")
        upload_dir = "data/uploads/chat"
        os.makedirs(upload_dir, exist_ok=True)
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as buffer:
            content_bytes = await file.read()
            buffer.write(content_bytes)
        file_info = {
            "file_path": file_path,
            "file_type": ext,
            "original_name": file.filename,
            "size": len(content_bytes),
        }

    # Store user message (empty string allowed)
    msg_content = content if content.strip() else ""
    user_message = crud.chat_message.create_with_session(
        db=db,
        obj_in=ChatMessageCreate(
            role="user",
            content=msg_content,
            file_path=file_info["file_path"] if file_info else None,
            file_type=file_info["file_type"] if file_info else None,
            tokens_used=0,
            response_time_ms=0,
        ),
        session_id=session_id,
    )

    # Notify clients of new user message
    try:
        from app.schemas.chat_session import ChatMessage as ChatMessageSchema
        from app.models.chat_session import ChatMessage as ChatMessageModel
        user_schema = ChatMessageSchema(
            id=user_message.id,
            role=user_message.role,
            content=user_message.content,
            session_id=session_id,
            user_id=user_message.user_id,
            created_at=user_message.created_at,
            file_path=user_message.file_path,
            file_type=user_message.file_type,
        )
        total_count = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).count()
        await connection_manager.notify_message_added(session_id, user_schema, total_count)
    except Exception as e:
        print(f"⚠️ [StreamingUpload] Failed to send WebSocket notification: {e}")

    # Send initial status
    await connection_manager.send_status_update(
        session_id,
        ChatStatusMessage(
            session_id=session_id,
            status="processing",
            message="Processing your file...",
            progress=0.1,
        ),
    )

    # Create request id and launch background processing
    request_id = f"upload_stream_{current_user.id}_{session_id}_{uuid.uuid4().hex[:8]}"
    asyncio.create_task(
        process_streaming_response(
            db,
            session_id,
            msg_content,
            current_user.id,
            request_id,
            uploaded_file=file_info,
        )
    )

    return StreamingChatResponse(
        request_id=request_id,
        session_id=session_id,
        user_message=user_message,
        stream_url=f"/api/v1/chat-sessions/{session_id}/stream/{request_id}",
    )

# -------------------- existing --------------------
@router.post("/{session_id}/messages/stream", response_model=StreamingChatResponse)
async def stream_message_to_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    message_in: ChatMessageCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Add a message to a chat session and stream the AI response.
    Returns immediately with a stream URL for the response.
    """
    # Generate request ID for tracking
    request_id = f"stream_{current_user.id}_{session_id}_{uuid.uuid4().hex[:8]}"
    
    with trace_agent_operation(
        "ChatSessionAPI",
        "stream_message_to_session",
        user_id=current_user.id,
        session_id=session_id,
        request_id=request_id
    ):
        # Verify session exists
        session = crud.chat_session.get_session_with_messages(
            db=db, session_id=session_id, user_id=current_user.id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found",
            )

        # Check if this is a response to a pending agent question FIRST
        is_agent_response = handle_agent_question_response(session_id, message_in.content)
        
        if is_agent_response:
            # User responded to agent question - create a minimal user message but no further processing
            # The agent workflow will handle the actual response processing
            print(f"✅ [stream_message_to_session] User response handled for session {session_id}")
            
            # Create a simple user message for the agent response (without full processing)
            user_message_create = ChatMessageCreate(
                role="user",
                content=message_in.content,
                tokens_used=0,
                response_time_ms=0
            )

            user_message = crud.chat_message.create_with_session(
                db=db, obj_in=user_message_create, session_id=session_id
            )
            
            # Mark this request as a user response (no streaming needed)
            message_cache[request_id] = {
                "status": "user_response",
                "message": "User response processed"
            }
            
            return StreamingChatResponse(
                request_id=request_id,
                session_id=session_id,
                user_message=user_message,
                stream_url=f"/api/v1/chat-sessions/{session_id}/stream/{request_id}"
            )

        # For normal messages (not agent responses), store user message and send notification
        user_message_create = ChatMessageCreate(
            role="user",
            content=message_in.content,
            tokens_used=0,
            response_time_ms=0
        )

        user_message = crud.chat_message.create_with_session(
            db=db, obj_in=user_message_create, session_id=session_id
        )
        
        # Send WebSocket notification for the new user message
        try:
            from app.schemas.chat_session import ChatMessage as ChatMessageSchema
            from app.models.chat_session import ChatMessage as ChatMessageModel
            
            user_message_schema = ChatMessageSchema(
                id=user_message.id,
                role=user_message.role,
                content=user_message.content,
                session_id=session_id,
                user_id=user_message.user_id,
                created_at=user_message.created_at,
                file_path=user_message.file_path,
                file_type=user_message.file_type
            )
            
            # Get current message count
            total_count = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).count()
            
            # Send message update notification
            await connection_manager.notify_message_added(session_id, user_message_schema, total_count)
            print(f"📨 [Streaming] Sent WebSocket notification for user message in session {session_id}")
            
        except Exception as e:
            print(f"⚠️ [Streaming] Failed to send WebSocket notification for user message: {e}")
        
        # Send initial status update for normal processing
        await connection_manager.send_status_update(
            session_id,
            ChatStatusMessage(
                session_id=session_id,
                status="processing",
                message="Processing your message...",
                progress=0.1
            )
        )
        
        # Start background processing
        asyncio.create_task(
            process_streaming_response(
                db, session_id, message_in.content, current_user.id, request_id
            )
        )
        
        return StreamingChatResponse(
            request_id=request_id,
            session_id=session_id,
            user_message=user_message,
            stream_url=f"/api/v1/chat-sessions/{session_id}/stream/{request_id}"
        )


# Streaming response endpoint
@router.get("/{session_id}/stream/{request_id}")
async def get_streaming_response(
    session_id: int,
    request_id: str,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """Stream the AI response for a specific request"""
    
    async def generate_stream():
        """Generator for streaming response chunks"""
        try:
            # Wait for processing to complete and stream results
            timeout = 300  # 5 minute timeout
            start_time = asyncio.get_event_loop().time()
            
            while True:
                current_time = asyncio.get_event_loop().time()
                
                # Check if processing is complete by looking in message cache
                if request_id in message_cache:
                    cached_data = message_cache[request_id]
                    
                    if cached_data["status"] == "complete":
                        # Send the actual AI response content
                        content_chunk = StreamingChunk(
                            type="content",
                            content=cached_data["ai_response"],
                            progress=1.0
                        )
                        yield f"data: {content_chunk.model_dump_json()}\n\n"
                        
                        # Send completion signal
                        completion = StreamingChunk(type="complete", content="")
                        yield f"data: {completion.model_dump_json()}\n\n"
                        
                        # Clean up cache
                        del message_cache[request_id]
                        break
                        
                    elif cached_data["status"] == "user_response":
                        # This was a user response to agent question - no processing needed
                        # Just send completion signal immediately
                        completion = StreamingChunk(
                            type="complete", 
                            content="",
                            progress=1.0
                        )
                        yield f"data: {completion.model_dump_json()}\n\n"
                        
                        # Clean up cache
                        del message_cache[request_id]
                        break
                        
                    elif cached_data["status"] == "error":
                        # Send error from processing
                        error_chunk = StreamingChunk(
                            type="error",
                            content=cached_data.get("error_message", "Processing failed")
                        )
                        yield f"data: {error_chunk.model_dump_json()}\n\n"
                        
                        # Clean up cache
                        del message_cache[request_id]
                        break
                
                # Check for timeout
                if current_time - start_time > timeout:
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Request timeout'})}\n\n"
                    # Clean up cache on timeout
                    if request_id in message_cache:
                        del message_cache[request_id]
                    break
                
                # Wait before checking again
                await asyncio.sleep(0.5)
                
                # Send progress update while waiting
                progress = min(0.9, (current_time - start_time) / 60)  # Up to 90% progress while waiting
                progress_chunk = StreamingChunk(
                    type="progress",
                    content=f"Processing... {int(progress * 100)}%",
                    progress=progress
                )
                yield f"data: {progress_chunk.model_dump_json()}\n\n"
                    
        except Exception as e:
            error_chunk = StreamingChunk(
                type="error",
                content=f"Streaming error: {str(e)}"
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


async def process_streaming_response(
    db: Session,
    session_id: int,
    user_message: str,
    user_id: int,
    request_id: str,
    uploaded_file: Optional[dict] = None
):
    """Background task to process the AI response and send status updates"""
    try:
        # Send processing status
        await connection_manager.send_status_update(
            session_id,
            ChatStatusMessage(
                session_id=session_id,
                status="analyzing",
                message="Analyzing your message...",
                progress=0.3,
                agent_name="Enhanced Customer Agent"
            )
        )
        
        # Get existing messages for context
        existing_messages = crud.chat_message.get_session_messages(
            db=db, session_id=session_id, skip=0, limit=50
        )
        
        # Prepare conversation history for context
        messages = [{"role": msg.role, "content": msg.content} for msg in existing_messages]
        
        # Send agent processing status
        await connection_manager.send_status_update(
            session_id,
            ChatStatusMessage(
                session_id=session_id,
                status="processing",
                message="Generating response...",
                progress=0.7,
                agent_name="AI Assistant"
            )
        )
        
        # Choose between enhanced customer agent and new customer workflow
        if settings.USE_CUSTOMER_WORKFLOW:
            # Use new customer workflow
            from app.agentsv2.customer_workflow import process_customer_request_async
            
            agent_result = await process_customer_request_async(
                user_id=str(user_id),
                user_input=user_message,
                conversation_history=messages,
                uploaded_file=uploaded_file,
                session_id=session_id  # Pass session_id to the workflow
            )
        else:
            # Use enhanced customer agent for processing (legacy)
            from app.agents import get_process_customer_request
            
            process_customer_request = get_process_customer_request()
            agent_result = await process_customer_request(
                user_message=user_message,
                user_id=user_id,
                session_id=session_id,
                uploaded_file=uploaded_file
            )
        
        # Extract AI response from standardized response_data format or fallback to legacy format
        ai_response = ""
        ai_title = "Chat"
        visualizations = None
        
        if isinstance(agent_result, dict):
            # All agents now use standardized response format with "message" field
            if "message" in agent_result:
                ai_response = agent_result["message"]
                print(f"✅ [DEBUG] Using standardized message field")
            else:
                ai_response = "No response content found"
                print(f"⚠️ [DEBUG] No message field found in agent_result keys: {list(agent_result.keys())}")
            
            # Extract title from standardized location
            ai_title = agent_result.get("title", "Chat")
            
            # Extract visualizations from standardized location
            visualizations = agent_result.get("visualizations", [])
            print(f"🔍 [DEBUG] [Streaming] Found {len(visualizations)} visualizations in response")
        
        # Generate interactive components based on response content
        interactive_components = generate_interactive_components(ai_response)
        
        # Store AI response with interactive components and visualization metadata
        ai_message_create = ChatMessageCreate(
            role="assistant",
            content=ai_response,
            tokens_used=0,
            response_time_ms=0,
            visualizations=visualizations
        )
        
        ai_message = crud.chat_message.create_with_session(
            db=db, obj_in=ai_message_create, session_id=session_id
        )
        
        # Send WebSocket notification for the new AI message
        try:
            from app.schemas.chat_session import ChatMessage as ChatMessageSchema
            message_schema = ChatMessageSchema(
                id=ai_message.id,
                role=ai_message.role,
                content=ai_message.content,
                session_id=session_id,
                user_id=ai_message.user_id,
                created_at=ai_message.created_at,
                file_path=ai_message.file_path,
                file_type=ai_message.file_type,
                visualizations=ai_message.visualizations
            )
            
            # Get current message count
            total_count = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).count()
            
            # Note: WebSocket notification handled by status updates below
            print(f"📨 [Streaming] AI message stored in session {session_id} (notification via status updates)")
            
        except Exception as e:
            print(f"⚠️ [Streaming] Failed to store AI message: {e}")
        
        # Update session title if available
        if ai_title and len(ai_title) > 3:
            session = crud.chat_session.get(db=db, id=session_id)
            if session:
                session.title = ai_title
                db.commit()
        
        # Send completion status with the actual AI message content
        import json as _json
        # Enrich completion status with the new AI message so frontend can append without full reload
        message_data = {
            "message_type": "new_message",
            "new_message": {
                "id": ai_message.id,
                "role": ai_message.role,
                "content": ai_message.content,
                "timestamp": ai_message.created_at.isoformat() if ai_message.created_at else None,
                "filePath": ai_message.file_path,
                "fileType": ai_message.file_type,
                "fileName": None,
                "visualizations": ai_message.visualizations,
            }
        }
        await connection_manager.send_status_update(
            session_id,
            ChatStatusMessage(
                session_id=session_id,
                status="complete",
                message=_json.dumps(message_data),
                progress=1.0
            )
        )
        
        # Store the processed message for the streaming endpoint to retrieve
        message_cache[request_id] = {
            "ai_message": ai_message,
            "ai_response": ai_response,
            "status": "complete",
            "interactive_components": interactive_components
        }
        
        # Note: WebSocket notification already sent above via notify_message_added
        # No need for additional status update to avoid duplicate notifications
        
        print(f"✅ [Streaming] Completed processing for request {request_id} - Message cached and notified")
        
    except Exception as e:
        print(f"❌ [Streaming] Error processing request {request_id}: {e}")
        
        # Store error in cache for streaming endpoint
        message_cache[request_id] = {
            "status": "error",
            "error_message": str(e)
        }
        
        await connection_manager.send_status_update(
            session_id,
            ChatStatusMessage(
                session_id=session_id,
                status="error",
                message=f"Processing failed: {str(e)}",
                progress=0.0
            )
        )


def generate_interactive_components(ai_response: str) -> list[InteractiveComponent]:
    """Generate interactive components based on AI response content"""
    components = []
    
    # Simple pattern matching for generating quick replies
    if "question" in ai_response.lower() or "?" in ai_response:
        quick_replies = [
            QuickReply(text="Yes", value="yes"),
            QuickReply(text="No", value="no"),
            QuickReply(text="Tell me more", value="more_info")
        ]
        components.append(
            InteractiveComponent(
                type="quick_replies",
                data={"replies": [reply.model_dump() for reply in quick_replies]}
            )
        )
    
    # Health-specific quick replies
    if any(keyword in ai_response.lower() for keyword in ["symptom", "pain", "medication", "appointment"]):
        health_replies = [
            QuickReply(text="Schedule appointment", value="schedule_appointment"),
            QuickReply(text="View my records", value="view_records"),
            QuickReply(text="Ask another question", value="new_question")
        ]
        components.append(
            InteractiveComponent(
                type="quick_replies",
                data={"replies": [reply.model_dump() for reply in health_replies]}
            )
        )
    
    return components 