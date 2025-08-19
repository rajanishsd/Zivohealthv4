import json
import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy.orm import Session

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

from app.models.health_data import OpenTelemetryTrace
from app.db.session import SessionLocal
from app.core.redis import redis_client

class ZivoHealthTelemetry:
    """Enhanced telemetry system for ZivoHealth agents with Redis persistence"""
    
    def __init__(self):
        self.tracer_provider = None
        self.tracer = None
        self.setup_telemetry()
        
    def setup_telemetry(self):
        """Initialize OpenTelemetry with Redis span storage"""
        
        # Create resource
        resource = Resource.create({
            "service.name": "zivohealth-agents",
            "service.version": "1.0.0",
            "deployment.environment": "development"
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)
        
        # Set up Redis span processor instead of PostgreSQL
        redis_processor = RedisSpanProcessor()
        self.tracer_provider.add_span_processor(redis_processor)
        
        # Set up OTLP exporter (optional - for external observability platforms)
        # otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
        # self.tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
        
        # Skip automatic instrumentations to avoid conflicts
        # Manual telemetry will be used via trace_agent_operation() calls
        
    def get_tracer(self):
        """Get the configured tracer"""
        return self.tracer
    
    @contextmanager
    def trace_agent_operation(
        self, 
        agent_name: str, 
        operation_name: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None,
        **attributes
    ):
        """Context manager for tracing agent operations"""
        
        with self.tracer.start_as_current_span(
            f"{agent_name}.{operation_name}",
            attributes={
                "agent.name": agent_name,
                "agent.operation": operation_name,
                "user.id": str(user_id) if user_id else None,
                "session.id": str(session_id) if session_id else None,
                "request.id": request_id,
                **attributes
            }
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def log_agent_interaction(
        self,
        source_agent: str,
        target_agent: str,
        message_type: str,
        message_content: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None
    ):
        """Log inter-agent communication"""
        
        with self.tracer.start_as_current_span(
            f"agent_interaction.{source_agent}_to_{target_agent}",
            attributes={
                "interaction.source_agent": source_agent,
                "interaction.target_agent": target_agent,
                "interaction.message_type": message_type,
                "interaction.message_size": len(json.dumps(message_content)),
                "user.id": str(user_id) if user_id else None,
                "session.id": str(session_id) if session_id else None,
                "request.id": request_id
            }
        ) as span:
            span.add_event(
                "agent_message_sent",
                {
                    "message_content": json.dumps(message_content)[:1000],  # Truncate large messages
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    def log_document_processing_step(
        self,
        step_name: str,
        document_id: int,
        step_data: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None
    ):
        """Log document processing workflow steps"""
        
        with self.tracer.start_as_current_span(
            f"document_processing.{step_name}",
            attributes={
                "document.id": str(document_id),
                "document.processing_step": step_name,
                "user.id": str(user_id) if user_id else None,
                "session.id": str(session_id) if session_id else None,
                "request.id": request_id
            }
        ) as span:
            span.add_event(
                "processing_step_completed",
                {
                    "step_data": json.dumps(step_data)[:2000],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

class RedisSpanProcessor:
    """Custom span processor that stores traces to Redis for fast access and analysis"""
    
    def __init__(self):
        self.redis_client = None
        self._initialize_redis()
        
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis_client
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            print(f"Failed to initialize Redis for telemetry: {e}")
            self.redis_client = None
    
    def on_start(self, span, parent_context=None):
        """Called when a span starts"""
        pass
    
    def on_end(self, span):
        """Called when a span ends - store to Redis"""
        if not self.redis_client:
            return
            
        try:
            self._store_span_to_redis(span)
        except Exception as e:
            print(f"Failed to store span to Redis: {e}")
    
    def _store_span_to_redis(self, span):
        """Store span data to Redis with efficient data structures"""
        if not self.redis_client:
            return
            
        try:
            # Extract span context
            span_context = span.get_span_context()
            trace_id = f"{span_context.trace_id:032x}"
            span_id = f"{span_context.span_id:016x}"
            
            # Calculate timing
            start_time = datetime.fromtimestamp(span.start_time / 1e9)
            end_time = datetime.fromtimestamp(span.end_time / 1e9) if span.end_time else None
            duration_ms = (span.end_time - span.start_time) / 1e6 if span.end_time else None
            
            # Extract attributes
            attributes = dict(span.attributes) if span.attributes else {}
            
            # Extract events
            events = []
            if span.events:
                for event in span.events:
                    events.append({
                        "name": event.name,
                        "timestamp": datetime.fromtimestamp(event.timestamp / 1e9).isoformat(),
                        "attributes": dict(event.attributes) if event.attributes else {}
                    })
            
            # Create span data
            span_data = {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
                "span_name": span.name,
                "span_kind": span.kind.name if span.kind else "INTERNAL",
                "status_code": span.status.status_code.name if span.status else "UNSET",
                "status_message": span.status.description if span.status else None,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat() if end_time else None,
                "duration_ms": duration_ms,
                "service_name": attributes.get("service.name", "zivohealth-agents"),
                "operation_name": attributes.get("agent.operation"),
                "attributes": attributes,
                "events": events,
                "user_id": attributes.get("user.id"),
                "session_id": attributes.get("session.id"),
                "request_id": attributes.get("request.id"),
                "document_id": attributes.get("document.id"),
                "agent_name": attributes.get("agent.name"),
                "agent_type": attributes.get("agent.type"),
                "workflow_step": attributes.get("agent.operation"),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Store in Redis with multiple data structures for efficient querying
            pipe = self.redis_client.pipeline()
            
            # 1. Store individual span (expires in 7 days)
            span_key = f"telemetry:span:{span_id}"
            pipe.setex(span_key, 604800, json.dumps(span_data))  # 7 days TTL
            
            # 2. Add to trace (sorted set by start time)
            trace_key = f"telemetry:trace:{trace_id}"
            pipe.zadd(trace_key, {span_id: span.start_time})
            pipe.expire(trace_key, 604800)  # 7 days TTL
            
            # 3. Add to agent operations index
            if attributes.get("agent.name"):
                agent_key = f"telemetry:agent:{attributes['agent.name']}"
                pipe.zadd(agent_key, {span_id: span.start_time})
                pipe.expire(agent_key, 604800)
            
            # 4. Add to user sessions index
            if attributes.get("user.id") and attributes.get("session.id"):
                session_key = f"telemetry:session:{attributes['user.id']}:{attributes['session.id']}"
                pipe.zadd(session_key, {span_id: span.start_time})
                pipe.expire(session_key, 604800)
            
            # 5. Add to recent spans (for dashboard)
            recent_key = "telemetry:recent_spans"
            pipe.zadd(recent_key, {span_id: span.start_time})
            pipe.zremrangebyrank(recent_key, 0, -1001)  # Keep only last 1000 spans
            
            # 6. Update metrics counters
            today = datetime.utcnow().strftime("%Y-%m-%d")
            hour = datetime.utcnow().strftime("%Y-%m-%d:%H")
            
            pipe.incr(f"telemetry:metrics:spans:daily:{today}")
            pipe.expire(f"telemetry:metrics:spans:daily:{today}", 2592000)  # 30 days
            
            pipe.incr(f"telemetry:metrics:spans:hourly:{hour}")
            pipe.expire(f"telemetry:metrics:spans:hourly:{hour}", 604800)  # 7 days
            
            if attributes.get("agent.name"):
                pipe.incr(f"telemetry:metrics:agent:{attributes['agent.name']}:daily:{today}")
                pipe.expire(f"telemetry:metrics:agent:{attributes['agent.name']}:daily:{today}", 2592000)
            
            # Execute pipeline
            pipe.execute()
            
        except Exception as e:
            print(f"Error storing span to Redis: {e}")
    
    def shutdown(self):
        """Cleanup processor"""
        if self.redis_client:
            self.redis_client.close()
    
    def force_flush(self, timeout_millis=30000):
        """Force flush - Redis writes are immediate"""
        return True

# Global telemetry instance
# telemetry = ZivoHealthTelemetry()  # Temporarily disabled

def get_telemetry():
    """Get the global telemetry instance - temporarily disabled"""
    return None

# Convenience functions for agents - temporarily disabled
def trace_agent_operation(agent_name: str, operation_name: str, **kwargs):
    """Decorator/context manager for tracing agent operations - disabled"""
    from contextlib import nullcontext
    return nullcontext()

def log_agent_interaction(source_agent: str, target_agent: str, message_type: str, message_content: Dict[str, Any], **kwargs):
    """Log inter-agent communication - disabled"""
    pass

def log_document_processing_step(step_name: str, document_id: int, step_data: Dict[str, Any], **kwargs):
    """Log document processing steps - disabled"""
    pass 