"""
Telemetry Query Utilities for Redis-based OpenTelemetry Storage
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.redis import redis_client

class TelemetryQuery:
    """Query interface for Redis-stored telemetry data"""
    
    def __init__(self):
        self.redis = redis_client
    
    def get_recent_spans(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent spans"""
        try:
            # Get recent span IDs (sorted by timestamp)
            span_ids = self.redis.zrevrange("telemetry:recent_spans", 0, limit-1)
            
            spans = []
            for span_id in span_ids:
                span_data = self.redis.get(f"telemetry:span:{span_id}")
                if span_data:
                    spans.append(json.loads(span_data))
            
            return spans
        except Exception as e:
            print(f"Error getting recent spans: {e}")
            return []
    
    def get_agent_spans(self, agent_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get spans for a specific agent"""
        try:
            # Get span IDs for this agent
            span_ids = self.redis.zrevrange(f"telemetry:agent:{agent_name}", 0, limit-1)
            
            spans = []
            for span_id in span_ids:
                span_data = self.redis.get(f"telemetry:span:{span_id}")
                if span_data:
                    spans.append(json.loads(span_data))
            
            return spans
        except Exception as e:
            print(f"Error getting agent spans: {e}")
            return []
    
    def get_trace_spans(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a specific trace"""
        try:
            # Get span IDs for this trace
            span_ids = self.redis.zrange(f"telemetry:trace:{trace_id}", 0, -1)
            
            spans = []
            for span_id in span_ids:
                span_data = self.redis.get(f"telemetry:span:{span_id}")
                if span_data:
                    spans.append(json.loads(span_data))
            
            # Sort by start time
            spans.sort(key=lambda x: x.get('start_time', ''))
            return spans
        except Exception as e:
            print(f"Error getting trace spans: {e}")
            return []
    
    def get_session_spans(self, user_id: str, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get spans for a user session"""
        try:
            # Get span IDs for this session
            span_ids = self.redis.zrevrange(f"telemetry:session:{user_id}:{session_id}", 0, limit-1)
            
            spans = []
            for span_id in span_ids:
                span_data = self.redis.get(f"telemetry:span:{span_id}")
                if span_data:
                    spans.append(json.loads(span_data))
            
            return spans
        except Exception as e:
            print(f"Error getting session spans: {e}")
            return []
    
    def get_telemetry_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics"""
        try:
            stats = {}
            
            # Recent spans count
            stats['recent_spans_count'] = self.redis.zcard("telemetry:recent_spans")
            
            # Active agents
            agent_keys = self.redis.keys("telemetry:agent:*")
            stats['active_agents'] = len(agent_keys)
            
            agent_stats = {}
            for key in agent_keys:
                agent_name = key.split(":")[-1]
                span_count = self.redis.zcard(key)
                agent_stats[agent_name] = span_count
            stats['agent_spans'] = agent_stats
            
            # Active traces
            trace_keys = self.redis.keys("telemetry:trace:*")
            stats['active_traces'] = len(trace_keys)
            
            # Daily metrics
            today = datetime.utcnow().strftime("%Y-%m-%d")
            daily_spans = self.redis.get(f"telemetry:metrics:spans:daily:{today}")
            stats['todays_spans'] = int(daily_spans) if daily_spans else 0
            
            # Hourly metrics for last 24 hours
            hourly_stats = {}
            for i in range(24):
                hour_time = datetime.utcnow() - timedelta(hours=i)
                hour_key = hour_time.strftime("%Y-%m-%d:%H")
                hourly_count = self.redis.get(f"telemetry:metrics:spans:hourly:{hour_key}")
                hourly_stats[hour_key] = int(hourly_count) if hourly_count else 0
            stats['hourly_spans'] = hourly_stats
            
            return stats
        except Exception as e:
            print(f"Error getting telemetry stats: {e}")
            return {}
    
    def search_spans(self, 
                    agent_name: Optional[str] = None,
                    operation_name: Optional[str] = None,
                    user_id: Optional[str] = None,
                    session_id: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Search spans with filters"""
        try:
            # Start with recent spans as base
            all_spans = self.get_recent_spans(limit * 2)  # Get more to filter
            
            filtered_spans = []
            for span in all_spans:
                # Apply filters
                if agent_name and span.get('agent_name') != agent_name:
                    continue
                if operation_name and span.get('operation_name') != operation_name:
                    continue
                if user_id and span.get('user_id') != user_id:
                    continue
                if session_id and span.get('session_id') != session_id:
                    continue
                
                # Time filters
                if start_time or end_time:
                    span_time_str = span.get('start_time')
                    if span_time_str:
                        try:
                            span_time = datetime.fromisoformat(span_time_str.replace('Z', '+00:00'))
                            if start_time and span_time < start_time:
                                continue
                            if end_time and span_time > end_time:
                                continue
                        except:
                            continue
                
                filtered_spans.append(span)
                
                if len(filtered_spans) >= limit:
                    break
            
            return filtered_spans
        except Exception as e:
            print(f"Error searching spans: {e}")
            return []
    
    def get_span_by_id(self, span_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific span by ID"""
        try:
            span_data = self.redis.get(f"telemetry:span:{span_id}")
            if span_data:
                return json.loads(span_data)
            return None
        except Exception as e:
            print(f"Error getting span {span_id}: {e}")
            return None
    
    def cleanup_old_spans(self, days_to_keep: int = 7):
        """Clean up spans older than specified days"""
        try:
            cutoff_time = (datetime.utcnow() - timedelta(days=days_to_keep)).timestamp()
            
            # Clean up recent spans
            removed = self.redis.zremrangebyscore("telemetry:recent_spans", 0, cutoff_time)
            print(f"Cleaned up {removed} old spans from recent list")
            
            # Clean up agent indices
            agent_keys = self.redis.keys("telemetry:agent:*")
            for key in agent_keys:
                removed = self.redis.zremrangebyscore(key, 0, cutoff_time)
                if removed > 0:
                    print(f"Cleaned up {removed} old spans from {key}")
            
            # Clean up trace indices
            trace_keys = self.redis.keys("telemetry:trace:*")
            for key in trace_keys:
                removed = self.redis.zremrangebyscore(key, 0, cutoff_time)
                if removed > 0:
                    print(f"Cleaned up {removed} old spans from {key}")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

# Global instance
telemetry_query = TelemetryQuery()

def get_telemetry_query() -> TelemetryQuery:
    """Get the global telemetry query instance"""
    return telemetry_query 