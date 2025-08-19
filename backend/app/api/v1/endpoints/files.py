"""
File serving endpoints for chat system.
Handles serving plot images and other static files.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()


@router.get("/plots/{filename}")
async def get_plot_file(filename: str):
    """
    Serve plot files from the data/plots directory.
    
    Args:
        filename: Name of the plot file to serve
        
    Returns:
        FileResponse with the plot image
        
    Raises:
        HTTPException: If file not found or invalid filename
    """
    # Security: Only allow certain file extensions
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg'}
    file_path = Path(filename)
    
    if file_path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Security: Prevent directory traversal attacks
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Construct full path
    plots_dir = Path("data/plots")
    full_path = plots_dir / filename
    
    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Plot file not found")
    
    # Return file response with appropriate media type
    media_type = "image/png"
    if filename.lower().endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif filename.lower().endswith('.svg'):
        media_type = "image/svg+xml"
    
    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        filename=filename
    )