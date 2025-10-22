from typing import List, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Interactive Component Schemas for enhanced chat experience
class QuickReply(BaseModel):
    """Quick reply button for interactive messages"""
    text: str
    value: str


class InteractiveComponent(BaseModel):
    """Interactive component that can be embedded in messages"""
    type: str  # "quick_replies", "form", "buttons", etc.
    data: Dict[str, Any]  # Component-specific data


# Chat Session Schemas
class ChatSessionBase(BaseModel):
    title: str
    has_verification: bool = False
    has_prescriptions: bool = False
    enhanced_mode_enabled: bool = True  # Backend control for enhanced chat features


class ChatSessionCreate(ChatSessionBase):
    title: str = "New Chat"  # Default title for new sessions


class ChatSessionUpdate(ChatSessionBase):
    title: Optional[str] = None
    has_verification: Optional[bool] = None
    has_prescriptions: Optional[bool] = None
    is_active: Optional[bool] = None
    enhanced_mode_enabled: Optional[bool] = None  # Allow updating enhanced mode


class ChatSessionInDBBase(ChatSessionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    message_count: Optional[int] = 0
    is_active: Optional[bool] = True
    enhanced_mode_enabled: Optional[bool] = True  # Backend control for streaming/interactive features

    model_config = ConfigDict(from_attributes=True)


class ChatSession(ChatSessionInDBBase):
    pass


class ChatSessionWithMessages(ChatSessionInDBBase):
    messages: List["ChatMessage"] = []
    prescriptions: List["Prescription"] = []


# Chat Message Schemas
class ChatMessageBase(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    file_path: Optional[str] = None  # Path to uploaded file
    file_type: Optional[str] = None  # File extension (jpg, png, pdf)
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None
    visualizations: Optional[List[Dict[str, Any]]] = None  # Visualization metadata


class ChatMessageCreate(ChatMessageBase):
    role: Optional[str] = "user"  # Default to user role
    file_path: Optional[str] = None  # Path to uploaded file
    file_type: Optional[str] = None  # Type of uploaded file (jpg, png, pdf)


class ChatMessageUpdate(ChatMessageBase):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatMessageInDBBase(ChatMessageBase):
    id: int
    session_id: int
    user_id: int  # Added user_id field to include in API responses
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessage(ChatMessageInDBBase):
    pass


# Enhanced Chat Message with Interactive Components
class EnhancedChatMessage(ChatMessage):
    """Extended ChatMessage that includes interactive components for UI"""
    interactive_components: Optional[List[InteractiveComponent]] = None
    quick_replies: Optional[List[QuickReply]] = None


# Streaming Response Schemas
class StreamingChunk(BaseModel):
    """Individual chunk for streaming responses"""
    type: str  # "content", "status", "complete", "error"
    content: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


# Prescription Schemas
class PrescriptionBase(BaseModel):
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    instructions: Optional[str] = None
    duration: Optional[str] = None
    prescribed_by: str
    prescription_image_link: Optional[str] = None
    prescription_group_id: Optional[str] = None


class PrescriptionCreate(PrescriptionBase):
    consultation_request_id: Optional[int] = None
    user_id: Optional[int] = None


class PrescriptionUpdate(PrescriptionBase):
    medication_name: Optional[str] = None
    prescribed_by: Optional[str] = None


class PrescriptionInDBBase(PrescriptionBase):
    id: str  # Keep as string for UUID compatibility
    session_id: int
    consultation_request_id: Optional[int] = None
    user_id: Optional[int] = None
    prescribed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Prescription(PrescriptionInDBBase):
    pass


class PrescriptionWithSession(PrescriptionInDBBase):
    session: ChatSession


# Sync Chat Data Schemas
class SyncChatRequest(BaseModel):
    sessions: List[ChatSessionCreate]
    messages: List[ChatMessageCreate]
    prescriptions: List[PrescriptionCreate]


class SyncChatResponse(BaseModel):
    success: bool
    synced_sessions: int
    synced_messages: int
    synced_prescriptions: int
    message: str


# Chat Message Response Schema
class ChatMessageResponse(BaseModel):
    user_message: ChatMessage
    ai_message: Optional[ChatMessage] = None
    session: ChatSession


# Enhanced Chat Message Response with Interactive Components
class EnhancedChatMessageResponse(BaseModel):
    """Enhanced response that includes interactive components"""
    user_message: EnhancedChatMessage
    ai_message: Optional[EnhancedChatMessage] = None
    session: ChatSession


# Chat Response Schema (for compatibility)
class ChatResponse(BaseModel):
    message: ChatMessage
    session: ChatSession


# WebSocket Status Message Schema
class ChatStatusMessage(BaseModel):
    """Real-time status updates for chat processing"""
    session_id: int
    status: str  # "typing", "processing", "analyzing", "complete", "message_update"
    message: Optional[str] = None
    progress: Optional[float] = None  # 0.0 to 1.0
    agent_name: Optional[str] = None  # Which agent is currently active


# WebSocket Message Update Notification Schema
class ChatMessageUpdate(BaseModel):
    """Notification when new messages are added to chat"""
    session_id: int
    message_type: str  # "new_message", "message_batch"
    new_message: Optional[ChatMessage] = None
    message_count: Optional[int] = None  # Total messages in session
    last_message_id: Optional[int] = None


# Streaming Response Wrapper
class StreamingChatResponse(BaseModel):
    """Wrapper for streaming chat responses"""
    request_id: str
    session_id: int
    user_message: ChatMessage
    stream_url: str  # URL for streaming endpoint


# Update forward references
ChatSessionWithMessages.model_rebuild() 