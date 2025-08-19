#!/usr/bin/env python3
"""
ChatGPT Interaction Logger

This module provides centralized logging for all ChatGPT/OpenAI API interactions,
storing both requests and responses in agent-specific folders for debugging and analysis.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from app.core.config import settings


class ChatGPTLogger:
    """Centralized logger for ChatGPT interactions"""
    
    def __init__(self, base_dir: str = "data/chatgpt_interactions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_agent_dir(self, agent_name: str) -> Path:
        """Get or create directory for specific agent"""
        agent_dir = self.base_dir / agent_name.lower().replace(" ", "_")
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir
    
    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """Sanitize text for use in filename"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Truncate and clean
        text = text.strip()[:max_length]
        return text if text else "unnamed"
    
    def _generate_interaction_id(self, user_id: Optional[int] = None, session_id: Optional[int] = None) -> str:
        """Generate unique interaction ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        if user_id and session_id:
            return f"u{user_id}_s{session_id}_{timestamp}_{unique_id}"
        elif user_id:
            return f"u{user_id}_{timestamp}_{unique_id}"
        else:
            return f"{timestamp}_{unique_id}"
    
    def log_interaction(
        self,
        agent_name: str,
        operation: str,
        request_data: Union[List[Dict], Dict[str, Any]],
        response_data: Any,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log ChatGPT interaction with request and response"""
        try:
            # Generate interaction ID
            interaction_id = self._generate_interaction_id(user_id, session_id)
            
            # Get agent directory
            agent_dir = self._get_agent_dir(agent_name)
            
            # Prepare metadata
            metadata = {
                "interaction_id": interaction_id,
                "agent_name": agent_name,
                "operation": operation,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "session_id": session_id,
                "request_id": request_id,
                "model_name": model_name or "unknown",
                "additional_metadata": additional_metadata or {}
            }
            
            # Extract content for filename
            content_preview = ""
            if isinstance(request_data, list) and request_data:
                for msg in request_data:
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        content_preview = self._sanitize_filename(msg.get("content", "")[:30])
                        break
                if not content_preview and request_data:
                    first_msg = request_data[0]
                    if isinstance(first_msg, dict):
                        content_preview = self._sanitize_filename(str(first_msg.get("content", ""))[:30])
            elif isinstance(request_data, dict):
                content_preview = self._sanitize_filename(str(request_data)[:30])
            
            if not content_preview:
                content_preview = operation
            
            # Create filenames
            base_filename = f"{operation}_{interaction_id}_{content_preview}"
            input_filename = agent_dir / f"request_{base_filename}.json"
            output_filename = agent_dir / f"response_{base_filename}.json"
            
            # Convert content to JSON format if possible
            def convert_to_json_safe(data):
                """Convert data to JSON-safe format"""
                if hasattr(data, 'content'):
                    content = data.content
                    # Try to parse content as JSON
                    try:
                        import json
                        parsed_content = json.loads(content)
                        return {
                            "content_type": "json",
                            "content": parsed_content,
                            "raw_content": content
                        }
                    except (json.JSONDecodeError, TypeError):
                        return {
                            "content_type": "text",
                            "content": content,
                            "raw_content": content
                        }
                elif isinstance(data, (dict, list)):
                    return {
                        "content_type": "structured",
                        "content": data,
                        "raw_content": str(data)
                    }
                else:
                    return {
                        "content_type": "text",
                        "content": str(data),
                        "raw_content": str(data)
                    }
            
            # Prepare input data
            input_data = {
                "metadata": metadata,
                "request": {
                    "messages": request_data if isinstance(request_data, list) else [request_data],
                    "model": model_name,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Prepare output data with JSON conversion
            response_content = convert_to_json_safe(response_data)
            output_data = {
                "metadata": metadata,
                "response": {
                    **response_content,
                    "full_response": response_data.dict() if hasattr(response_data, 'dict') else str(response_data),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Write input file
            with open(input_filename, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Write output file
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"📝 [ChatGPT Logger] Saved interaction: {agent_name}/{base_filename}")
            
            return interaction_id
            
        except Exception as e:
            print(f"❌ [ChatGPT Logger] Failed to log interaction: {e}")
            return f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# Global logger instance
_chatgpt_logger = None

def get_chatgpt_logger() -> ChatGPTLogger:
    """Get or create the global ChatGPT logger instance"""
    global _chatgpt_logger
    if _chatgpt_logger is None:
        _chatgpt_logger = ChatGPTLogger()
    return _chatgpt_logger


def log_chatgpt_interaction(
    agent_name: str,
    operation: str,
    request_data: Union[List[Dict], Dict[str, Any]],
    response_data: Any,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    request_id: Optional[str] = None,
    model_name: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to log ChatGPT interaction"""
    logger = get_chatgpt_logger()
    return logger.log_interaction(
        agent_name=agent_name,
        operation=operation,
        request_data=request_data,
        response_data=response_data,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        model_name=model_name,
        additional_metadata=additional_metadata
    )
