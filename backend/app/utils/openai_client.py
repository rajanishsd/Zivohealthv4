from typing import List, Dict, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.chatgpt_logger import log_chatgpt_interaction
import json
import re

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def get_chat_completion(messages: List[dict]) -> str:
    """
    Get a chat completion from OpenAI.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        The assistant's response text
    """
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_CLIENT_MODEL or settings.DEFAULT_AI_MODEL,
            messages=messages,
            max_completion_tokens=1000,
        )
        
        # Log the interaction
        log_chatgpt_interaction(
            agent_name="OpenAIClient",
            operation="get_chat_completion",
            request_data=messages,
            response_data=response.choices[0].message,
            model_name=settings.OPENAI_CLIENT_MODEL or settings.DEFAULT_AI_MODEL,
            additional_metadata={"max_tokens": 1000}
        )
        
        return response.choices[0].message.content
    except Exception as e:
        # Log the error in production
        print(f"Error getting chat completion: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again." 

async def get_chat_completion_with_title(messages: List[dict]) -> Dict[str, str]:
    """
    Get a chat completion from OpenAI with a summary title for the conversation.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        Dictionary with 'response' and 'title' keys
    """
    try:
        # Add instruction to the system message to include a title
        enhanced_messages = messages.copy()
        
        # Find the system message and enhance it, or add one if it doesn't exist
        system_message_index = None
        for i, msg in enumerate(enhanced_messages):
            if msg["role"] == "system":
                system_message_index = i
                break
        
        title_instruction = """

IMPORTANT: After providing your response, please also generate a brief, descriptive title (3-6 words) that summarizes the main topic of this conversation. Format your response exactly like this:

RESPONSE: [Your full response here]

TITLE: [Brief descriptive title here]

Example:
RESPONSE: Based on your symptoms, it sounds like you might be experiencing a tension headache...
TITLE: Tension Headache Help"""

        if system_message_index is not None:
            enhanced_messages[system_message_index]["content"] += title_instruction
        else:
            enhanced_messages.insert(0, {
                "role": "system", 
                "content": "You are a helpful AI health assistant. Provide accurate, helpful, and empathetic responses to health-related questions." + title_instruction
            })
        
        response = await client.chat.completions.create(
            model=settings.OPENAI_CLIENT_MODEL or settings.DEFAULT_AI_MODEL,
            messages=enhanced_messages,
            max_completion_tokens=1200,  # Slightly increased for title
        )
        
        # Log the interaction
        log_chatgpt_interaction(
            agent_name="OpenAIClient",
            operation="get_chat_completion_with_title",
            request_data=enhanced_messages,
            response_data=response.choices[0].message,
            model_name=settings.OPENAI_CLIENT_MODEL or settings.DEFAULT_AI_MODEL,
            additional_metadata={"max_tokens": 1200, "includes_title": True}
        )
        
        full_response = response.choices[0].message.content
        
        # Parse the response to extract the answer and title
        return parse_response_with_title(full_response)
        
    except Exception as e:
        # Log the error in production
        print(f"Error getting chat completion with title: {e}")
        return {
            "response": "I apologize, but I'm having trouble processing your request right now. Please try again.",
            "title": "Chat Error"
        }

def parse_response_with_title(full_response: str) -> Dict[str, str]:
    """
    Parse the OpenAI response to extract the main response and title.
    
    Args:
        full_response: The full response from OpenAI
        
    Returns:
        Dictionary with 'response' and 'title' keys
    """
    try:
        # Look for the RESPONSE: and TITLE: markers
        response_match = re.search(r'RESPONSE:\s*(.*?)\s*TITLE:', full_response, re.DOTALL | re.IGNORECASE)
        title_match = re.search(r'TITLE:\s*(.*?)(?:\n|$)', full_response, re.IGNORECASE)
        
        if response_match and title_match:
            response_text = response_match.group(1).strip()
            title_text = title_match.group(1).strip()
            
            # Clean up the title (remove quotes, extra whitespace)
            title_text = title_text.strip('"\'').strip()
            
            return {
                "response": response_text,
                "title": title_text
            }
        else:
            # Fallback: if the format isn't followed, use the full response and generate a simple title
            lines = full_response.strip().split('\n')
            first_meaningful_line = ""
            
            for line in lines:
                line = line.strip()
                if line and not line.lower().startswith(('hello', 'hi', 'sure', 'of course')):
                    first_meaningful_line = line
                    break
            
            # Generate a simple title from the first few words
            words = first_meaningful_line.split()[:4]
            simple_title = ' '.join(words) if words else "Health Consultation"
            
            return {
                "response": full_response,
                "title": simple_title
            }
            
    except Exception as e:
        print(f"Error parsing response with title: {e}")
        return {
            "response": full_response,
            "title": "Health Chat"
        }

