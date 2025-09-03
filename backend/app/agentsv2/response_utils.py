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
    
    # If caller provided results.visualizations, normalize and surface at top-level
    if isinstance(results.get("visualizations"), list):
        normalized_viz: List[Dict[str, Any]] = []
        for viz in results["visualizations"]:
            if isinstance(viz, dict):
                normalized_viz.append(_normalize_visualization(viz))
        if normalized_viz:
            response["visualizations"] = normalized_viz
    
    return response


def _normalize_visualization(viz: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a visualization object to ensure all required fields are present.
    - Preserve provided fields like filename, path, file_path, s3_uri
    - Do not rename keys in saved_plot_files structure per user preference
    """
    filename = viz.get("filename", "")
    # Carry through best-effort direct path reference if present (S3 or local)
    # Accept plot_path from agents as a direct path source as well
    direct_path = viz.get("file_path") or viz.get("path") or viz.get("s3_uri") or viz.get("local_path") or viz.get("plot_path")
    normalized = {
        "id": f"viz_{uuid.uuid4().hex[:8]}",
        "type": viz.get("type", "chart"),
        "title": viz.get("title", "Analysis Chart"),
        "description": viz.get("description", "Generated visualization"),
        "filename": filename,
        "key_findings": viz.get("key_findings", ""),
    }
    # Include pass-through fields for downstream presign enrichment in API
    if direct_path:
        normalized["file_path"] = direct_path
    if "s3_uri" in viz:
        normalized["s3_uri"] = viz.get("s3_uri")
    if "local_path" in viz and "file_path" not in normalized:
        normalized["local_path"] = viz.get("local_path")
    # Preserve plot_path if provided and file_path absent
    if "plot_path" in viz and "file_path" not in normalized:
        normalized["plot_path"] = viz.get("plot_path")
    return normalized

    # No fallback extraction; caller must provide results.visualizations
    return response


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