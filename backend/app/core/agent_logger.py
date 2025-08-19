"""
Agent Interaction Logger for ZivoHealth

Provides comprehensive logging and audit trails for all agent interactions,
including request flow, decision points, tool usage, and response generation.
Essential for medical compliance and debugging.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum
import threading


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(Enum):
    REQUEST_START = "REQUEST_START"
    REQUEST_END = "REQUEST_END"
    AGENT_CATEGORIZATION = "AGENT_CATEGORIZATION"
    AGENT_ROUTING = "AGENT_ROUTING"
    AGENT_PROCESSING = "AGENT_PROCESSING"
    AGENT_HANDOFF = "AGENT_HANDOFF"
    INTER_AGENT_MESSAGE = "INTER_AGENT_MESSAGE"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    API_CALL = "API_CALL"
    FILE_PROCESSING = "FILE_PROCESSING"
    DATABASE_OPERATION = "DATABASE_OPERATION"
    ERROR = "ERROR"
    USER_SESSION_START = "USER_SESSION_START"
    USER_SESSION_END = "USER_SESSION_END"


@dataclass
class AgentLogEntry:
    """Structured log entry for agent interactions"""
    session_id: str
    request_id: str
    timestamp: str
    event_type: EventType
    agent_name: str
    log_level: LogLevel
    message: str
    details: Dict[str, Any]
    user_id: Optional[int] = None
    file_info: Optional[Dict[str, Any]] = None
    tool_used: Optional[str] = None
    execution_time_ms: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    lineage_path: Optional[List[str]] = None
    user_session_id: Optional[str] = None
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    message_content: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    operation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {k: v.value if isinstance(v, Enum) else v for k, v in asdict(self).items()}


class AgentInteractionLogger:
    """Comprehensive logging system for agent interactions"""
    
    def __init__(self):
        self.setup_logger()
        self.current_session_id: Optional[str] = None
        self.current_request_id: Optional[str] = None
        self.request_start_time: Optional[datetime] = None
        self.interaction_log: List[AgentLogEntry] = []
        self._local_data = threading.local()
    
    def setup_logger(self):
        """Setup structured logging configuration"""
        self.logger = logging.getLogger("agent_interactions")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler for agent logs
        import os
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/agent_interactions.log")
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # JSON formatter for structured logs
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'agent_data'):
                    return json.dumps(record.agent_data)
                return super().format(record)
        
        formatter = JsonFormatter()
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
    
    def _get_current_context(self) -> Dict[str, Any]:
        """Get current request context"""
        return getattr(self._local_data, 'context', {})

    def _set_context(self, **kwargs):
        """Set request context"""
        if not hasattr(self._local_data, 'context'):
            self._local_data.context = {}
        self._local_data.context.update(kwargs)

    @contextmanager
    def session_context(self, user_id: Optional[int] = None):
        """Context manager for tracking a complete user session"""
        session_id = str(uuid.uuid4())
        self.current_session_id = session_id
        
        try:
            self.log_info(
                event_type=EventType.REQUEST_START,
                agent_name="SessionManager",
                message="Session started",
                details={"user_id": user_id, "session_id": session_id}
            )
            yield session_id
        finally:
            self.log_info(
                event_type=EventType.REQUEST_END,
                agent_name="SessionManager", 
                message="Session ended",
                details={"session_id": session_id, "total_interactions": len(self.interaction_log)}
            )
            self.current_session_id = None
    
    @contextmanager
    def request_context(self, user_message: str, file_info: Optional[Dict] = None, user_id: Optional[int] = None):
        """Context manager for tracking individual requests"""
        request_id = str(uuid.uuid4())
        self.current_request_id = request_id
        self.request_start_time = datetime.now()
        
        try:
            self.log_info(
                event_type=EventType.REQUEST_START,
                agent_name="RequestManager",
                message="Processing user request",
                details={
                    "user_message": user_message[:200] + "..." if len(user_message) > 200 else user_message,
                    "has_file": file_info is not None,
                    "file_type": file_info.get('type') if file_info else None,
                    "request_id": request_id
                },
                user_id=user_id,
                file_info=file_info
            )
            yield request_id
        finally:
            execution_time = (datetime.now() - self.request_start_time).total_seconds() * 1000
            self.log_info(
                event_type=EventType.REQUEST_END,
                agent_name="RequestManager",
                message="Request processing completed",
                details={"request_id": request_id},
                execution_time_ms=execution_time
            )
            self.current_request_id = None
            self.request_start_time = None
    
    def log_categorization(self, agent_name: str, user_message: str, categorization: Dict[str, Any]):
        """Log agent categorization decisions"""
        self.log_info(
            event_type=EventType.AGENT_CATEGORIZATION,
            agent_name=agent_name,
            message="Request categorized",
            details={
                "category": categorization.get('category'),
                "confidence": categorization.get('confidence'),
                "reasoning": categorization.get('reasoning'),
                "user_message_preview": user_message[:100] + "..." if len(user_message) > 100 else user_message
            }
        )
    
    def log_routing(self, agent_name: str, target_agent: str, routing_reason: str):
        """Log agent routing decisions"""
        self.log_info(
            event_type=EventType.AGENT_ROUTING,
            agent_name=agent_name,
            message="Request routed to specialized agent",
            details={
                "target_agent": target_agent,
                "routing_reason": routing_reason
            }
        )
    
    def log_agent_processing(self, agent_name: str, processing_type: str, details: Dict[str, Any]):
        """Log agent processing activities"""
        self.log_info(
            event_type=EventType.AGENT_PROCESSING,
            agent_name=agent_name,
            message=f"Agent processing: {processing_type}",
            details=details
        )
    
    def log_tool_execution(self, agent_name: str, tool_name: str, input_data: Any, result: Any, execution_time_ms: float):
        """Log tool execution with inputs and outputs"""
        self.log_info(
            event_type=EventType.TOOL_EXECUTION,
            agent_name=agent_name,
            message=f"Tool executed: {tool_name}",
            details={
                "input_preview": str(input_data)[:500] + "..." if len(str(input_data)) > 500 else str(input_data),
                "result_preview": str(result)[:500] + "..." if len(str(result)) > 500 else str(result),
                "success": True
            },
            tool_used=tool_name,
            execution_time_ms=execution_time_ms
        )
    
    def log_api_call(self, agent_name: str, api_name: str, request_data: Dict, response_data: Dict, execution_time_ms: float):
        """Log external API calls"""
        self.log_info(
            event_type=EventType.API_CALL,
            agent_name=agent_name,
            message=f"API call: {api_name}",
            details={
                "api_name": api_name,
                "request_size": len(str(request_data)),
                "response_size": len(str(response_data)),
                "success": True
            },
            execution_time_ms=execution_time_ms
        )
    
    def log_file_processing(self, agent_name: str, file_path: str, file_type: str, processing_result: str):
        """Log file processing activities"""
        self.log_info(
            event_type=EventType.FILE_PROCESSING,
            agent_name=agent_name,
            message="File processed",
            details={
                "file_path": file_path,
                "file_type": file_type,
                "processing_success": "error" not in processing_result.lower(),
                "result_preview": processing_result[:200] + "..." if len(processing_result) > 200 else processing_result
            }
        )
    
    def log_database_operation(self, agent_name: str, operation: str, table: str, data: Dict[str, Any]):
        """Log database operations"""
        self.log_info(
            event_type=EventType.DATABASE_OPERATION,
            agent_name=agent_name,
            message=f"Database {operation}",
            details={
                "operation": operation,
                "table": table,
                "data_keys": list(data.keys()) if data else []
            }
        )
    
    def log_error(self, agent_name: str, error: Exception, context: Dict[str, Any]):
        """Log errors with full context"""
        self.log_entry(
            event_type=EventType.ERROR,
            agent_name=agent_name,
            log_level=LogLevel.ERROR,
            message=f"Error in {agent_name}: {str(error)}",
            details=context,
            error_details={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "error_context": context
            }
        )
    
    def log_info(self, event_type: EventType, agent_name: str, message: str, details: Dict[str, Any], **kwargs):
        """Log info level messages"""
        self.log_entry(event_type, agent_name, LogLevel.INFO, message, details, **kwargs)
    
    def log_entry(self, event_type: EventType, agent_name: str, log_level: LogLevel, message: str, 
                  details: Dict[str, Any], **kwargs):
        """Create and log a structured log entry"""
        entry = AgentLogEntry(
            session_id=self.current_session_id or "no-session",
            request_id=self.current_request_id or "no-request",
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            agent_name=agent_name,
            log_level=log_level,
            message=message,
            details=details,
            **kwargs
        )
        
        # Add to in-memory log
        self.interaction_log.append(entry)
        
        # Log to file/console
        log_data = entry.to_dict()
        log_record = logging.LogRecord(
            name="agent_interactions",
            level=getattr(logging, log_level.value),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        log_record.agent_data = log_data
        self.logger.handle(log_record)
    
    def get_request_lineage(self, request_id: str) -> List[Dict[str, Any]]:
        """Get complete lineage for a specific request"""
        return [entry.to_dict() for entry in self.interaction_log if entry.request_id == request_id]
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary statistics for a session"""
        session_entries = [e for e in self.interaction_log if e.session_id == session_id]
        
        if not session_entries:
            return {"error": "Session not found"}
        
        return {
            "session_id": session_id,
            "total_requests": len(set(e.request_id for e in session_entries)),
            "total_interactions": len(session_entries),
            "agents_used": list(set(e.agent_name for e in session_entries)),
            "tools_used": list(set(e.tool_used for e in session_entries if e.tool_used)),
            "errors_count": len([e for e in session_entries if e.log_level == LogLevel.ERROR]),
            "start_time": min(e.timestamp for e in session_entries),
            "end_time": max(e.timestamp for e in session_entries)
        }

    def log_agent_handoff(self, source_agent: str, target_agent: str, 
                         message_content: str = None, metadata: Dict[str, Any] = None):
        """Log agent-to-agent handoff for lineage tracking"""
        context = self._get_current_context()
        lineage_path = context.get('lineage_path', [])
        lineage_path.append(f"{source_agent} → {target_agent}")
        self._set_context(lineage_path=lineage_path)
        
        self.log_info(
            event_type=EventType.AGENT_HANDOFF,
            agent_name=source_agent,
            message="Agent handoff",
            details={
                "handoff_chain": lineage_path,
                "message_summary": message_content[:100] if message_content else None
            },
            source_agent=source_agent,
            target_agent=target_agent,
            message_content=message_content,
            message_metadata=metadata,
            operation="agent_handoff"
        )

    def log_inter_agent_message(self, source_agent: str, target_agent: str, 
                               message_content: str, message_type: str = "request",
                               metadata: Dict[str, Any] = None):
        """Log messages passed between agents"""
        self.log_info(
            event_type=EventType.INTER_AGENT_MESSAGE,
            agent_name=source_agent,
            message="Inter-agent message",
            details={
                "message_type": message_type,
                "source": source_agent,
                "target": target_agent,
                "content_preview": message_content[:200] + "..." if len(message_content) > 200 else message_content
            },
            source_agent=source_agent,
            target_agent=target_agent,
            message_content=message_content,
            message_metadata={
                "message_type": message_type,
                "message_length": len(message_content),
                **(metadata or {})
            },
            operation="inter_agent_message"
        )


# Global logger instance
agent_logger = AgentInteractionLogger()


# Decorators for automatic logging
def log_agent_method(event_type: EventType):
    """Decorator to automatically log agent method calls"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            agent_name = self.__class__.__name__
            start_time = datetime.now()
            
            try:
                result = func(self, *args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                agent_logger.log_agent_processing(
                    agent_name=agent_name,
                    processing_type=func.__name__,
                    details={
                        "method": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                        "success": True
                    }
                )
                
                return result
            except Exception as e:
                agent_logger.log_error(
                    agent_name=agent_name,
                    error=e,
                    context={
                        "method": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    }
                )
                raise
        return wrapper
    return decorator 