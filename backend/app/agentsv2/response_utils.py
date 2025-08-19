"""
Shared response formatting utilities for all agents.
Ensures consistent response structure and visualization handling.
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import uuid


def format_agent_response(
    success: bool,
    task_types: List[str],
    results: Dict[str, Any],
    execution_log: List[Dict[str, Any]],
    message: Optional[str] = None,
    title: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format standardized agent response with visualization support.
    
    Args:
        success: Whether the operation was successful
        task_types: List of task types executed
        results: Agent-specific results data
        execution_log: Execution log entries
        message: Optional user-friendly message
        title: Optional chat title
        error: Error message if success=False
    
    Returns:
        Standardized response dictionary with visualizations extracted
    """
    response = {
        "success": success,
        "task_types": task_types,
        "results": results,
        "execution_log": execution_log
    }
    
    if message:
        response["message"] = message
    
    if title:
        response["title"] = title
    
    if error:
        response["error"] = error
    
    # Only extract visualizations from results if not already provided
    if "visualizations" not in response:
        visualizations = extract_visualizations_from_results(results)
        if visualizations:
            response["visualizations"] = visualizations
    
    return response


def _normalize_visualization(viz: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a visualization object to ensure all required fields are present."""
    filename = viz.get("filename", "")
    return {
        "id": f"viz_{uuid.uuid4().hex[:8]}",
        "type": "chart",
        "title": viz.get("title", "Analysis Chart"),
        "description": viz.get("description", "Generated visualization"),
        "filename": filename,
        "relative_url": f"/files/plots/{filename}" if filename else "",
        "key_findings": viz.get("key_findings", "")
    }

def _extract_visualizations_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract visualizations from text that contains embedded JSON arrays."""
    import re
    import json
    
    visualizations = []
    
    try:
        # Look for "Visualizations Created:" followed by JSON array
        pattern = r'Visualizations Created:\s*\[\s*(.*?)\s*\]'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            json_content = '[' + match.group(1) + ']'
            # Clean up the JSON content
            json_content = re.sub(r'\n\s*', ' ', json_content)  # Remove newlines and extra spaces
            json_content = re.sub(r',\s*}', '}', json_content)  # Remove trailing commas
            json_content = re.sub(r',\s*\]', ']', json_content)  # Remove trailing commas before ]
            
            try:
                viz_array = json.loads(json_content)
                if isinstance(viz_array, list):
                    visualizations.extend(viz_array)
                    print(f"🔍 [DEBUG] Extracted {len(viz_array)} visualizations from text JSON array")
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse visualization JSON array: {str(e)}")
                
        # Also look for individual visualization objects in the text
        viz_pattern = r'\{\s*"filename":\s*"([^"]+)".*?"title":\s*"([^"]+)".*?\}'
        viz_matches = re.finditer(viz_pattern, text, re.DOTALL)
        
        for match in viz_matches:
            filename = match.group(1)
            title = match.group(2)
            # Try to extract the full JSON object
            full_match = re.search(r'\{[^}]*"filename":\s*"' + re.escape(filename) + r'"[^}]*\}', text, re.DOTALL)
            if full_match:
                try:
                    viz_obj = json.loads(full_match.group(0))
                    if viz_obj not in visualizations:  # Avoid duplicates
                        visualizations.append(viz_obj)
                        print(f"🔍 [DEBUG] Extracted individual visualization: {title}")
                except json.JSONDecodeError:
                    pass
                    
    except Exception as e:
        print(f"🔍 [DEBUG] Error extracting visualizations from text: {str(e)}")
    
    return visualizations

def extract_visualizations_from_results(results: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Extract visualization data from agent results.
    
    With the customer workflow agent prompt fix, visualizations should now be extracted 
    properly by the LangChain agent and stored in agent_results["visualizations"].
    This function provides fallback extraction for edge cases.
    
    Args:
        results: Agent results dictionary
        
    Returns:
        List of visualization dictionaries or None
    """
    visualizations = []
    
    # Primary: Look for visualizations directly in results (lab agent puts them here)
    if "visualizations" in results:
        direct_visualizations = results["visualizations"]
        if isinstance(direct_visualizations, list):
            for viz in direct_visualizations:
                if isinstance(viz, dict):
                    visualizations.append(_normalize_visualization(viz))
            print(f"🔍 [DEBUG] Found {len(direct_visualizations)} visualizations in results")
    
    # Secondary: Look for visualizations in agent_results (customer workflow structure)
    if not visualizations and "agent_results" in results:
        agent_results = results["agent_results"]
        if isinstance(agent_results, dict) and "visualizations" in agent_results:
            agent_visualizations = agent_results["visualizations"]
            if isinstance(agent_visualizations, list):
                for viz in agent_visualizations:
                    if isinstance(viz, dict):
                        visualizations.append(_normalize_visualization(viz))
                print(f"🔍 [DEBUG] Found {len(agent_visualizations)} visualizations in agent_results")
    
    # Fallback: Look in nested structures where lab workflow stores visualizations
    if not visualizations:
        # Check results.analysis.visualizations_created (lab workflow structure)
        analysis = results.get("results", {}).get("analysis", {})
        if isinstance(analysis, dict) and "visualizations_created" in analysis:
            viz_created = analysis["visualizations_created"]
            if isinstance(viz_created, list):
                # Process and normalize visualization objects
                for viz in viz_created:
                    if isinstance(viz, dict):
                        visualizations.append(_normalize_visualization(viz))
                print(f"🔍 [DEBUG] Found {len(viz_created)} visualizations in results.analysis.visualizations_created")
        
        # Also check direct results.analysis path (nutrition workflow structure)
        elif isinstance(results.get("analysis"), dict) and "visualizations_created" in results.get("analysis", {}):
            viz_created = results["analysis"]["visualizations_created"]
            if isinstance(viz_created, list):
                for viz in viz_created:
                    if isinstance(viz, dict):
                        visualizations.append(_normalize_visualization(viz))
                print(f"🔍 [DEBUG] Found {len(viz_created)} visualizations in results.analysis.visualizations_created (direct path)")
        
        # Additional fallback: Extract from text analysis if it's a string
        elif isinstance(analysis, str) and "visualizations created" in analysis.lower():
            text_visualizations = _extract_visualizations_from_text(analysis)
            for viz in text_visualizations:
                if isinstance(viz, dict):
                    visualizations.append(_normalize_visualization(viz))
            if text_visualizations:
                print(f"🔍 [DEBUG] Found {len(text_visualizations)} visualizations extracted from analysis text")
        
        # Check agent_results for any that were missed
        agent_results = results.get("agent_results", {})
        if agent_results and not visualizations:
            for agent_key, agent_data in agent_results.items():
                if isinstance(agent_data, dict) and "visualizations" in agent_data:
                    nested_viz = agent_data["visualizations"]
                    if isinstance(nested_viz, list):
                        for viz in nested_viz:
                            if isinstance(viz, dict):
                                visualizations.append(_normalize_visualization(viz))
                        print(f"🔍 [DEBUG] Found {len(nested_viz)} fallback visualizations in {agent_key}")
    
    print(f"🔍 [DEBUG] Total visualizations extracted: {len(visualizations)}")
    return visualizations if visualizations else None


def generate_plot_title(filename: str) -> str:
    """Generate a user-friendly title from plot filename"""
    if not filename:
        return "Analysis Chart"
    
    # Remove extension and replace underscores/hyphens with spaces
    title = Path(filename).stem.replace('_', ' ').replace('-', ' ')
    
    # Capitalize words and handle common abbreviations
    words = title.split()
    capitalized_words = []
    
    for word in words:
        # Handle common medical/lab abbreviations
        if word.upper() in ['LFT', 'ALT', 'AST', 'GGT', 'ALP']:
            capitalized_words.append(word.upper())
        elif word.lower() in ['trend', 'analysis', 'chart', 'plot']:
            capitalized_words.append(word.capitalize())
        else:
            capitalized_words.append(word.capitalize())
    
    return ' '.join(capitalized_words)


def format_error_response(
    error_message: str,
    execution_log: List[Dict[str, Any]],
    task_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Format a standardized error response.
    
    Args:
        error_message: Error description
        execution_log: Execution log entries
        task_types: Optional list of attempted task types
    
    Returns:
        Standardized error response dictionary
    """
    return format_agent_response(
        success=False,
        task_types=task_types or [],
        results={},
        execution_log=execution_log,
        error=error_message
    )