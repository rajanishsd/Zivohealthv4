from typing import List
from langchain.tools import Tool
import os


class ImageToolkit:
    def get_tools(self) -> List[Tool]:
        return [self.get_image_analysis_tool()]
    
    def get_image_analysis_tool(self) -> Tool:
        def analyze_image(file_path: str) -> str:
            try:
                return f"Medical image analysis for {os.path.basename(file_path)}. Please consult healthcare provider for interpretation."
            except Exception as e:
                return f"Image analysis error: {str(e)}"
        
        return Tool(
            name="Medical_Image_Analysis",
            func=analyze_image,
            description="Analyze medical images"
        )


def create_image_tools() -> List[Tool]:
    toolkit = ImageToolkit()
    return toolkit.get_tools() 