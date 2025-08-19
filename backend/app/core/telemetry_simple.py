"""
Simplified Telemetry System for ZivoHealth Agents
Using Redis for storage without complex OpenTelemetry instrumentations
"""

import json
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
from app.core.redis import redis_client

class SimpleTelemetry:
    """Simplified telemetry system with Redis storage"""
    
    def __init__(self):
        self.redis = redis_client
        # Track current trace context for hierarchical relationships
        self._current_trace_context = {}
        
    @contextmanager
    def trace_agent_operation(
        self, 
        agent_name: str, 
        operation_name: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,  # NEW: Track parent span
        orchestrator: Optional[str] = None,    # NEW: Track orchestrating agent
        **attributes
    ):
        """Context manager for tracing agent operations with hierarchy support"""
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Determine hierarchy
        current_parent = parent_span_id or self._current_trace_context.get(f"{user_id}:{session_id}", {}).get("parent_span")
        current_orchestrator = orchestrator or self._current_trace_context.get(f"{user_id}:{session_id}", {}).get("orchestrator")
        
        # Set current context for child operations
        context_key = f"{user_id}:{session_id}"
        self._current_trace_context[context_key] = {
            "parent_span": span_id,
            "orchestrator": agent_name,
            "trace_id": trace_id
        }
        
        try:
            yield {"trace_id": trace_id, "span_id": span_id, "parent_span_id": current_parent}
        except Exception as e:
            # Log error span
            self._store_span(
                trace_id=trace_id,
                span_id=span_id,
                agent_name=agent_name,
                operation_name=operation_name,
                start_time=start_time,
                end_time=time.time(),
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                parent_span_id=current_parent,        # NEW
                orchestrator=current_orchestrator,     # NEW
                status="ERROR",
                error_message=str(e),
                **attributes
            )
            raise
        else:
            # Log successful span
            self._store_span(
                trace_id=trace_id,
                span_id=span_id,
                agent_name=agent_name,
                operation_name=operation_name,
                start_time=start_time,
                end_time=time.time(),
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                parent_span_id=current_parent,        # NEW
                orchestrator=current_orchestrator,     # NEW
                status="OK",
                **attributes
            )
        finally:
            # Clean up context if this was the orchestrator
            if context_key in self._current_trace_context:
                if self._current_trace_context[context_key]["orchestrator"] == agent_name:
                    del self._current_trace_context[context_key]
    
    def log_agent_interaction(
        self,
        source_agent: str,
        target_agent: str,
        message_type: str,
        message_content: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,   # NEW
        orchestrator: Optional[str] = None      # NEW
    ):
        """Log inter-agent communication with hierarchy support"""
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Get hierarchy context
        context_key = f"{user_id}:{session_id}"
        current_parent = parent_span_id or self._current_trace_context.get(context_key, {}).get("parent_span")
        current_orchestrator = orchestrator or self._current_trace_context.get(context_key, {}).get("orchestrator")
        
        # Filter out core fields from message_content to avoid conflicts
        core_fields = {
            'trace_id', 'span_id', 'agent_name', 'operation_name', 
            'start_time', 'end_time', 'user_id', 'session_id', 
            'request_id', 'status', 'error_message', 'message_type',
            'target_agent', 'message_size', 'parent_span_id', 'orchestrator'
        }
        
        filtered_content = {
            k: v for k, v in message_content.items() 
            if k not in core_fields
        }
        
        self._store_span(
            trace_id=trace_id,
            span_id=span_id,
            agent_name=source_agent,
            operation_name=f"interaction_to_{target_agent}",
            start_time=timestamp,
            end_time=timestamp,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            parent_span_id=current_parent,        # NEW
            orchestrator=current_orchestrator,     # NEW
            status="OK",
            message_type=message_type,
            target_agent=target_agent,
            message_size=len(json.dumps(message_content)),
            **filtered_content  # Pass filtered message content as additional metadata
        )
    
    def log_document_processing_step(
        self,
        step_name: str,
        document_id: int,
        step_data: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,   # NEW
        orchestrator: Optional[str] = None      # NEW
    ):
        """Log document processing workflow steps with hierarchy support"""
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Get hierarchy context
        context_key = f"{user_id}:{session_id}"
        current_parent = parent_span_id or self._current_trace_context.get(context_key, {}).get("parent_span")
        current_orchestrator = orchestrator or self._current_trace_context.get(context_key, {}).get("orchestrator")
        
        self._store_span(
            trace_id=trace_id,
            span_id=span_id,
            agent_name="DocumentProcessor",
            operation_name=step_name,
            start_time=timestamp,
            end_time=timestamp,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            parent_span_id=current_parent,        # NEW
            orchestrator=current_orchestrator,     # NEW
            status="OK",
            document_id=document_id,
            step_data=json.dumps(step_data)[:2000]  # Truncate large data
        )
    
    def _store_span(self, **span_data):
        """Store span data to Redis with hierarchy support"""
        if not self.redis:
            return
            
        try:
            # Separate core span fields from metadata
            core_fields = {
                'trace_id', 'span_id', 'agent_name', 'operation_name', 
                'start_time', 'end_time', 'user_id', 'session_id', 
                'request_id', 'status', 'error_message', 'parent_span_id', 'orchestrator'  # NEW fields
            }
            
            # Create metadata from additional fields
            metadata = {}
            core_data = {}
            
            for key, value in span_data.items():
                if key in core_fields:
                    core_data[key] = value
                else:
                    metadata[key] = value
            
            # Add timestamps and duration
            core_data['created_at'] = datetime.utcnow().isoformat()
            core_data['duration_ms'] = (core_data['end_time'] - core_data['start_time']) * 1000
            
            # Add metadata if it exists
            if metadata:
                core_data['metadata'] = metadata
            
            span_id = core_data['span_id']
            
            # Store individual span
            span_key = f"telemetry:span:{span_id}"
            self.redis.setex(span_key, 604800, json.dumps(core_data))  # 7 days TTL
            
            # Add to recent spans
            self.redis.zadd("telemetry:recent_spans", {span_id: core_data['start_time']})
            
            # Keep only last 1000 spans
            self.redis.zremrangebyrank("telemetry:recent_spans", 0, -1001)
            
            # Add to agent index if agent_name exists
            if core_data.get('agent_name'):
                agent_key = f"telemetry:agent:{core_data['agent_name']}"
                self.redis.zadd(agent_key, {span_id: core_data['start_time']})
                self.redis.expire(agent_key, 604800)  # 7 days TTL
            
            # Add to session index if user and session exist
            if core_data.get('user_id') and core_data.get('session_id'):
                session_key = f"telemetry:session:{core_data['user_id']}:{core_data['session_id']}"
                self.redis.zadd(session_key, {span_id: core_data['start_time']})
                self.redis.expire(session_key, 604800)  # 7 days TTL
            
            # NEW: Add to hierarchy index if parent exists
            if core_data.get('parent_span_id'):
                hierarchy_key = f"telemetry:hierarchy:{core_data['parent_span_id']}"
                self.redis.sadd(hierarchy_key, span_id)
                self.redis.expire(hierarchy_key, 604800)  # 7 days TTL
                
        except Exception as e:
            # Don't let telemetry failures affect the main application
            print(f"Telemetry storage failed: {e}")

# Global instance
simple_telemetry = SimpleTelemetry()

def trace_agent_operation(agent_name: str, operation_name: str, **kwargs):
    """Simplified trace decorator"""
    return simple_telemetry.trace_agent_operation(agent_name, operation_name, **kwargs)

def log_agent_interaction(source_agent: str, target_agent: str, message_type: str, message_content: Dict[str, Any], **kwargs):
    """Simplified agent interaction logging"""
    return simple_telemetry.log_agent_interaction(source_agent, target_agent, message_type, message_content, **kwargs)

def log_document_processing_step(step_name: str, document_id: int, step_data: Dict[str, Any], **kwargs):
    """Simplified document processing logging"""
    return simple_telemetry.log_document_processing_step(step_name, document_id, step_data, **kwargs) 