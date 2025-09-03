
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.ERROR)

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Union, Dict, Any, List, Optional
from app.agentsv2.tools.ocr_tools import OCRToolkit
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Optional
import base64
from datetime import datetime
from app.utils.timezone import now_local
import shutil
import json

# LangSmith tracing imports
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager

# PydanticOutputParser import
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate


class DocumentAnalysisResult(BaseModel):
    """Result of document type analysis"""
    document_type: str = Field(description="The primary type of document identified")
    confidence: float = Field(description="Confidence score for the classification (0.0 to 1.0)")
    sub_category: Optional[str] = Field(description="Sub-category if applicable (e.g., 'blood test' for lab report)")
    key_indicators: list[str] = Field(description="List of key terms or indicators that led to this classification")
    description: str = Field(description="Brief description of what the document contains")
    extracted_text: Optional[str] = Field(default="", description="Extracted text content from the document (for text-based documents)")

class FileState(TypedDict):
    file_path: str  # Current file path (will be updated to stored path)
    original_file_path: str  # Original file path before storage
    file_name: str  # Add file_name to state
    file_type: str
    error: str
    analysis_only: bool
    processing_result: str
    image_base64: Optional[str]
    analysis_result: DocumentAnalysisResult
    ocr_result: str
    lab_agent_result: Union[str, dict]  # Optional, result from lab agent if applicable
    clinical_agent_result: Union[str, dict]  # Optional, result from clinical agent if applicable
    pharmacy_agent_result: Union[str, dict]  # Optional, result from pharmacy agent if applicable
    vitals_agent_result: Union[str, dict]  # Optional, result from vitals agent if applicable
    nutrition_agent_result: Union[str, dict]  # Optional, result from nutrition agent if applicable
    user_id: str  # Add user_id to state
    processing_success: bool  # Whether processing was successful
    processing_message: str  # User-friendly processing message
    processing_statistics: Dict[str, Any]  # Detailed statistics from lab processing
    individual_record_results: List[Dict[str, Any]]  # Individual record processing results
    error_details: Dict[str, Any]  # Detailed error information
    



def store_file_locally(file_path: str) -> str:
    """
    Store the file in the local disk under /backend/data/unprocessed with date and time appended.
    
    Args:
        file_path (str): Path to the original file
        
    Returns:
        str: Path to the stored file
    """
    try:
        # Create the unprocessed directory if it doesn't exist
        unprocessed_dir = './data/unprocessed'
        os.makedirs(unprocessed_dir, exist_ok=True)
        
        # Get file extension and name
        original_path = Path(file_path)
        file_extension = original_path.suffix
        file_name = original_path.stem
        
        # Create timestamp
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        
        # Create new filename with timestamp
        new_filename = f"{file_name}_{timestamp}{file_extension}"
        new_file_path = os.path.join(unprocessed_dir, new_filename)
        
        # If source is an S3 URI, download to temp first
        try:
            from app.services.s3_service import is_s3_uri, download_to_temp
            if is_s3_uri(file_path):
                temp_download = download_to_temp(file_path)
                shutil.copy2(temp_download, new_file_path)
            else:
                shutil.copy2(file_path, new_file_path)
        except Exception:
            # Fallback to regular copy if S3 helpers fail
            shutil.copy2(file_path, new_file_path)
        
        print(f"📁 [DEBUG] File stored locally: {new_file_path}")
        return new_file_path
        
    except Exception as e:
        print(f"❌ [DEBUG] Error storing file locally: {str(e)}")
        return file_path  # Return original path if storage fails


def detect_file_type(state: FileState) -> FileState:
    """Detect the file type based on file extension."""
    try:
        file_path = state["file_path"]
        
        # Check if file exists locally unless it's an S3 URI
        try:
            from app.services.s3_service import is_s3_uri
            is_remote = is_s3_uri(file_path)
        except Exception:
            is_remote = False
        
        if not is_remote and not os.path.exists(file_path):
            state["error"] = f"File not found: {file_path}"
            return state
        
        # Get file extension
        path_obj = Path(file_path)
        file_extension = path_obj.suffix.lower()
        

        print(f"file_extension-------: {file_path}, {file_extension}")
        # Determine file type based on supported extensions
        if file_extension in ['.pdf']:
            file_type = "PDF Document"
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            file_type = "Image File"
        else:
            # Unsupported file type
            file_type = f"Unsupported File Type ({file_extension})"
        
        state["file_type"] = file_type
        state["error"] = ""
        
    except Exception as e:
        state["error"] = f"Error detecting file type: {str(e)}"
        state["file_type"] = "Unknown"
    
    return state


def decide_processing_path(state: FileState) -> str:
    """Decide which processing path to take based on file type."""
    file_type = state["file_type"]
    
    if "PDF Document" in file_type:
        return "handle_pdf"
    elif "Image File" in file_type:
        return "handle_image"
    else:
        return "handle_unsupported"


async def handle_pdf(state: FileState) -> FileState:
    """Handle PDF file processing."""

    print(f"handle_pdf-------: {state['file_path']}")
    try:
        file_path = state["file_path"]
       
        ocr_toolkit = OCRToolkit()
       
        from pathlib import Path
        # Extract text from PDF - examples of pages parameter usage:
        # ocr_text = ocr_toolkit._extract_text_from_pdf(Path(file_path))  # Extract all pages (default)
        # ocr_text = ocr_toolkit._extract_text_from_pdf(Path(file_path), "first")  # Extract first page only
        # ocr_text = ocr_toolkit._extract_text_from_pdf(Path(file_path), "last")   # Extract last page only
        # ocr_text = ocr_toolkit._extract_text_from_pdf(Path(file_path), [1, 2, 3])  # Extract pages 1, 2, and 3
        ocr_text = ocr_toolkit._extract_text_from_pdf_s3_uri(file_path)
        analysis_result = analyze_document_type(ocr_text)
        analysis_result.extracted_text = ocr_text
        if analysis_result.document_type != "Other":
            state["processing_result"] = f"PDF file processed: {file_path}"
            state["analysis_result"] = analysis_result
            state["ocr_result"] = ocr_text
        else:
            state["processing_result"] = f"PDF file processed: {file_path}"
            state["analysis_result"] = analysis_result
            state["ocr_result"] = ocr_text
    except Exception as e:
        print(f"[DEBUG] Exception in handle_pdf: {e}")
        state["error"] = f"Error processing PDF: {str(e)}"
    return state


async def handle_image(state: FileState) -> FileState:
    """Handle image file processing."""
    try:
        file_path = state["file_path"]
        
        # Analyze image using GPT-4V
        analysis_result = analyze_image_with_gpt4v(file_path, state.get("image_base64"))
        
        # Store the analysis result
        state["analysis_result"] = analysis_result
        
        # Store extracted text in OCR result if available
        if analysis_result.extracted_text:
            state["ocr_result"] = analysis_result.extracted_text
        else:
            state["ocr_result"] = f"Image analyzed: {file_path}"
            
        state["processing_result"] = f"Image file processed: {file_path}"
        
    except Exception as e:
        state["error"] = f"Error processing image: {str(e)}"
    
    return state


def handle_unsupported(state: FileState) -> FileState:
    """Handle unsupported file types."""
    state["processing_result"] = f"Unsupported file type: {state['file_type']}"
    state["error"] = f"Cannot process unsupported file type: {state['file_type']}"
    return state


def check_processing_success(state: FileState) -> str:
    """Check if the processing was successful and route accordingly."""
    # Check if there's an error
    if state.get("error") and state["error"]:
        return "handle_unsupported"
    
    # Check if analysis result exists and is valid
    analysis_result = state.get("analysis_result")
    if analysis_result:
        # If document type is "Other" or confidence is very low, route to unsupported
        if (analysis_result.document_type == "Other" or 
            analysis_result.confidence < 0.3):
            return "handle_unsupported"
    
    # If we have OCR result and no errors, processing was successful
    if state.get("ocr_result"):
        return "handle_result"
    
    print("defaulted to unsupported")# Default to unsupported if we can't determine success
    return "handle_unsupported"


async def handle_result(state: FileState) -> FileState:
    """Handle the final result from both PDF and image processing."""
    try:
        file_path = state["file_path"]
        analysis_result = state.get("analysis_result")
        
        # Helper function to prepare agent parameters following the simple rule
        def prepare_agent_params(extracted_text: str, original_file_path: str, stored_file_path: str) -> dict:
            """
            Simple rule: if extracted_text exists, use it and don't pass image_path.
            Always pass source_file_path for storage/record-keeping.
            Use original_file_path for image processing as we no longer re-store the file.
            """
            return {
                "extracted_text": extracted_text if extracted_text else None,
                "image_path": original_file_path if not extracted_text else None,
                "source_file_path": original_file_path  # Always pass original path
            }
        
        # Create a comprehensive result summary
        if analysis_result:
            state["processing_result"] = f"Successfully processed {analysis_result.document_type}: {file_path}"
            

            if state["analysis_only"] == False:
            # Prepare common agent parameters
                # Use original file path for both processing and storage
                agent_params = prepare_agent_params(analysis_result.extracted_text, state["file_path"], state["file_path"])
                
                
                # Route to appropriate agent based on document type
                if analysis_result.document_type == "Lab Report":
                    # Use LabAgentLangGraph for lab reports
                    from app.agentsv2.lab_agent import LabAgentLangGraph
                    lab_agent = LabAgentLangGraph()

                    #store the extracted text in a file
                    with open(f"extracted_text_{state['user_id']}.txt", "w") as f:
                        f.write(analysis_result.extracted_text)
                        
                    # Compose a prompt for the lab agent using extracted text and any relevant info
                    prompt = f"Extract and update lab test data for this user id {state['user_id']}.\nExtracted text:\n{analysis_result.extracted_text}\n Confidence Score: {analysis_result.confidence}\n File Name: {state['file_name']}"
                    
                    # Use async run method for LabAgentLangGraph - only pass relevant parameters
                    lab_agent_result = await lab_agent.run(
                        prompt, 
                        user_id=state['user_id'], 
                        extracted_text=agent_params["extracted_text"],
                        image_path=agent_params["image_path"],
                        source_file_path=agent_params["source_file_path"]
                    )
                    print(f"lab_agent_result: {lab_agent_result}")
                    
                    # Enhanced handling of structured lab agent results
                    if isinstance(lab_agent_result, dict):
                        state["lab_agent_result"] = lab_agent_result
                        
                        # Extract key metrics for easy access
                        if lab_agent_result.get("success"):
                            state["processing_success"] = True
                            
                            # Extract update statistics if available
                            results = lab_agent_result.get("results", {})
                            update_results = results.get("update_results", {})
                            
                            if update_results and update_results.get("action") == "batch":
                                # Extract comprehensive statistics
                                stats = update_results.get("statistics", {})
                                individual_results = update_results.get("results", [])
                                summary = update_results.get("summary", "")
                                
                                # Store detailed processing information
                                state["processing_statistics"] = {
                                    "total_records_processed": stats.get("total_processed", 0),
                                    "records_inserted": stats.get("inserted", 0),
                                    "records_updated": stats.get("updated", 0),
                                    "duplicate_records": stats.get("duplicates", 0),
                                    "failed_records": stats.get("failed", 0),
                                    "total_affected_rows": stats.get("total_affected_rows", 0),
                                    "total_fields_updated": stats.get("total_fields_updated", 0),
                                    "total_fields_inserted": stats.get("total_fields_inserted", 0),
                                    "summary": summary
                                }
                                
                                # Store individual record details for reporting
                                state["individual_record_results"] = individual_results
                                
                                # Create user-friendly message
                                if stats.get("total_processed", 0) > 0:
                                    state["processing_message"] = f"Successfully processed {stats['total_processed']} lab record(s) from document '{state['file_name']}': {summary}"
                                else:
                                    state["processing_message"] = f"Document '{state['file_name']}' processed but no lab records were extracted."
                            else:
                                # Handle non-batch results (single record or other operations)
                                state["processing_message"] = f"Document '{state['file_name']}' processed successfully."
                        else:
                            # Handle failed processing
                            state["processing_success"] = False
                            error_msg = lab_agent_result.get("error", "Unknown error occurred")
                            state["processing_message"] = f"Failed to process document '{state['file_name']}': {error_msg}"
                            state["error_details"] = lab_agent_result.get("error_details", {})
                            
                    else:
                        # Fallback for non-dict results (backward compatibility)
                        try:
                            parsed = json.loads(lab_agent_result) if isinstance(lab_agent_result, str) else lab_agent_result
                            state["lab_agent_result"] = parsed
                            state["processing_message"] = f"Document '{state['file_name']}' processed with basic result parsing."
                        except Exception as e:
                            state["lab_agent_result"] = {
                                "message": str(lab_agent_result), 
                                "success": "error" not in str(lab_agent_result).lower()
                            }
                            state["processing_message"] = f"Document '{state['file_name']}' processed with limited result parsing."

                elif analysis_result.document_type in ["Clinical Notes", "Prescription"]:
                    # Use PrescriptionClinicalAgentLangGraph for clinical notes and prescriptions
                    from app.agentsv2.prescription_clinical_agent import PrescriptionClinicalAgentLangGraph
                    clinical_agent = PrescriptionClinicalAgentLangGraph()
                    
                    # Compose a prompt for the clinical agent
                    prompt = f"Extract and update {'clinical notes' if analysis_result.document_type == 'Clinical Notes' else 'prescription'} data for user id {state['user_id']}.\nExtracted text:\n{analysis_result.extracted_text}\n Confidence Score: {analysis_result.confidence}\n File Name: {state['file_name']}"
                    
                    # Use async process_request method for PrescriptionClinicalAgentLangGraph
                    clinical_agent_result = await clinical_agent.process_request(
                        prompt, 
                        user_id=state['user_id'], 
                        extracted_text=agent_params["extracted_text"],
                        image_path=agent_params["image_path"],
                        source_file_path=agent_params["source_file_path"]
                    )
                    print(f"clinical_agent_result: {clinical_agent_result}")
                    
                    # Store the result
                    state["clinical_agent_result"] = clinical_agent_result
                    if isinstance(clinical_agent_result, dict) and clinical_agent_result.get("success"):
                        state["processing_success"] = True
                        state["processing_message"] = f"Successfully processed {analysis_result.document_type.lower()} from document '{state['file_name']}'"
                    else:
                        state["processing_success"] = False
                        error_msg = clinical_agent_result.get("error", "Unknown error occurred") if isinstance(clinical_agent_result, dict) else "Processing failed"
                        state["processing_message"] = f"Failed to process {analysis_result.document_type.lower()} from document '{state['file_name']}': {error_msg}"

                elif analysis_result.document_type == "Pharmacy Bill":
                    # Use PharmacyAgentLangGraph for pharmacy bills
                    from app.agentsv2.pharmacy_agent import PharmacyAgentLangGraph
                    pharmacy_agent = PharmacyAgentLangGraph()
                    
                    # Compose a prompt for the pharmacy agent
                    prompt = f"Extract and update pharmacy bill data for user id {state['user_id']}.\nExtracted text:\n{analysis_result.extracted_text}\n Confidence Score: {analysis_result.confidence}\n File Name: {state['file_name']}"
                    
                    # Use async process_request method for PharmacyAgentLangGraph
                    pharmacy_agent_result = await pharmacy_agent.process_request(
                        prompt, 
                        user_id=state['user_id'],
                        extracted_text=agent_params["extracted_text"],
                        image_path=agent_params["image_path"],
                        source_file_path=agent_params["source_file_path"]
                    )
                    print(f"pharmacy_agent_result: {pharmacy_agent_result}")
                    
                    # Store the result
                    state["pharmacy_agent_result"] = pharmacy_agent_result
                    if isinstance(pharmacy_agent_result, dict) and pharmacy_agent_result.get("success"):
                        state["processing_success"] = True
                        state["processing_message"] = f"Successfully processed pharmacy bill from document '{state['file_name']}'"
                    else:
                        state["processing_success"] = False
                        error_msg = pharmacy_agent_result.get("error", "Unknown error occurred") if isinstance(pharmacy_agent_result, dict) else "Processing failed"
                        state["processing_message"] = f"Failed to process pharmacy bill from document '{state['file_name']}': {error_msg}"

                elif analysis_result.document_type == "Vitals Details":
                    # Use VitalsAgentLangGraph for vitals
                    from app.agentsv2.vitals_agent import VitalsAgentLangGraph
                    vitals_agent = VitalsAgentLangGraph()
                    
                    # Compose a prompt for the vitals agent
                    prompt = f"Extract and update vitals data for user id {state['user_id']}.\nExtracted text:\n{analysis_result.extracted_text}\n Confidence Score: {analysis_result.confidence}\n File Name: {state['file_name']}"
                    
                    # Use async run method for VitalsAgentLangGraph
                    vitals_agent_result = await vitals_agent.run(
                        prompt, 
                        user_id=state['user_id'], 
                        extracted_text=agent_params["extracted_text"],
                        image_path=agent_params["image_path"],
                        source_file_path=agent_params["source_file_path"]
                    )
                    print(f"vitals_agent_result: {vitals_agent_result}")
                    
                    # Store the result
                    state["vitals_agent_result"] = vitals_agent_result
                    if isinstance(vitals_agent_result, dict) and vitals_agent_result.get("success"):
                        state["processing_success"] = True
                        state["processing_message"] = f"Successfully processed vitals from document '{state['file_name']}'"
                    else:
                        state["processing_success"] = False
                        error_msg = vitals_agent_result.get("error", "Unknown error occurred") if isinstance(vitals_agent_result, dict) else "Processing failed"
                        state["processing_message"] = f"Failed to process vitals from document '{state['file_name']}': {error_msg}"

                elif analysis_result.document_type == "Nutrition":
                    # Use NutritionAgentLangGraph for nutrition documents
                    from app.agentsv2.nutrition_agent import NutritionAgentLangGraph
                    nutrition_agent = NutritionAgentLangGraph()
                    
                    # Compose a prompt for the nutrition agent
                    prompt = f"Extract and update nutrition data for user id {state['user_id']}.\nExtracted text:\n{analysis_result.extracted_text}\n Confidence Score: {analysis_result.confidence}\n File Name: {state['file_name']}"
                    
                    # Use async run method for NutritionAgentLangGraph
                    nutrition_agent_result = await nutrition_agent.run(
                        prompt, 
                        user_id=state['user_id'], 
                        extracted_text=agent_params["extracted_text"],
                        image_path=agent_params["image_path"],
                        source_file_path=agent_params["source_file_path"]
                    )
                    print(f"nutrition_agent_result: {nutrition_agent_result}")
                    
                    # Store the result
                    state["nutrition_agent_result"] = nutrition_agent_result
                    if isinstance(nutrition_agent_result, dict) and nutrition_agent_result.get("success"):
                        state["processing_success"] = True
                        state["processing_message"] = f"Successfully processed nutrition data from document '{state['file_name']}'"
                    else:
                        state["processing_success"] = False
                        error_msg = nutrition_agent_result.get("error", "Unknown error occurred") if isinstance(nutrition_agent_result, dict) else "Processing failed"
                        state["processing_message"] = f"Failed to process nutrition data from document '{state['file_name']}': {error_msg}"

                else:
                    # Handle other document types (Medical Imaging, Body Images, Other)
                    state["processing_message"] = f"Document '{state['file_name']}' classified as '{analysis_result.document_type}' - no specific agent processing required"
                    
        else:
            state["processing_result"] = f"No analysis result: {file_path}"
        
        print(f"document type: {analysis_result.document_type}")  
        print(f"confidence: {analysis_result.confidence}")
        print(f"sub_category: {analysis_result.sub_category}")
        print(f"key_indicators: {analysis_result.key_indicators}")
        print(f"description: {analysis_result.description}")
        #print(f"extracted_text: {analysis_result.extracted_text}")
        
        return state
        
    except Exception as e:
        state["error"] = f"Error handling result: {str(e)}"
        return state


def analyze_image_with_gpt4v(file_path: str, image_base64: Optional[str] = None) -> DocumentAnalysisResult:
    """
    Analyze image using GPT-4V to identify document type and extract relevant information.
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        DocumentAnalysisResult: Structured result containing document type and details
    """
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Prefer provided base64; otherwise load from local file
        if image_base64:
            image_data = image_base64
        else:
            with open(file_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Create GPT-4V client
        vision_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            timeout=300
        )
        
        # Analysis prompt for medical document classification
        analysis_prompt = """Analyze this image and classify it into one of these medical document categories:

1. **Clinical Notes - Handwritten notes by doctors, outpatient records, consultation sheets. These often include the doctor’s name, patient’s name, and free-form notes. Even if lab values are mentioned, it is still a clinical note unless it is structured like a lab report.
    Characteristics:
    - Contains "OUT-PATIENT RECORD", doctor's name, and patient's name. or if it mentions "OPD"
    - Handwritten, scanned, or loosely formatted
    - Mentions of lab values like "ALT 245", "Platelets", etc., without structured lab format
    - May include medications, appointment times, or follow-up plans
    - also mentions the patient has taken the medication or has the lab test done
    - Does NOT include official lab headers or tabular formats

    ❗NOTE: Do not classify as a lab report **just because lab values are present**. Clinical notes often include lab data.
    - **TEXT EXTRACTION REQUIRED**: Extract all text content from clinical notes

2. **Lab Report** - Blood tests, urine tests, pathology reports, lab results
   - Examples: CBC results, metabolic panels, hormone tests, pathology reports
   - Key indicators: lab values, reference ranges, test names, medical terminology
   - **TEXT EXTRACTION REQUIRED**: Extract all text content from lab reports

3. **Prescription** - Medication prescriptions, dosage instructions, Rx forms
   - Examples: medication prescriptions, dosage schedules, pharmacy instructions
   - Key indicators: medication names, dosages, Rx symbols, pharmacy information
   - **TEXT EXTRACTION REQUIRED**: Extract all text content from prescriptions

4. **Pharmacy Bill** - Medication bills, pharmacy receipts, prescription costs
   - Examples: pharmacy bills, medication receipts, insurance claims
   - Key indicators: prices, pharmacy names, insurance information, medication lists
   - **TEXT EXTRACTION REQUIRED**: Extract all text content from pharmacy bills

5. **Medical Imaging** - MRI, CT scan, X-ray reports or images
   - Examples: X-ray images, MRI scans, CT scans, ultrasound images
   - Key indicators: imaging terminology, body part references, medical imaging
   - **NO TEXT EXTRACTION**: These are primarily visual medical images

6. **Body Images** - Photos of body parts, wounds, skin conditions
   - Examples: skin rashes, wounds, body part photos, medical photography
   - Key indicators: body parts, skin conditions, wounds, medical photography
   - **NO TEXT EXTRACTION**: These are primarily visual medical images

7. **Vitals Details** - Blood pressure, heart rate, temperature readings
   - Examples: vital signs, health metrics, monitoring data
   - Key indicators: BP, HR, temperature, pulse, oxygen levels
   - **TEXT EXTRACTION REQUIRED**: Extract all text content from vitals readings

8. **Nutrition** - Food and beverage photos, meal plans, dietary information
   - Examples: food photos, meal images, nutrition information
   - Key indicators: food items, meals, nutrition data, dietary information
   - **NO TEXT EXTRACTION**: These are primarily food/nutrition images

9. **Other** - Any document that doesn't fit the above categories
   - Examples: general documents, non-medical images, unclear content
   - **NO TEXT EXTRACTION**: Not a medical document requiring text extraction

**IMPORTANT**: For Lab Report, Prescription, Pharmacy Bill, and Vitals Details, extract ALL text content from the image. For other categories, focus only on classification.

Provide your analysis in this JSON format:
{
    "document_type": "Lab Report/Prescription/Pharmacy Bill/Medical Imaging/Body Images/Vitals Details/Nutrition/Other",
    "confidence": 0.8,
    "sub_category": "blood test/medication/x-ray/chest/breakfast/etc",
    "key_indicators": ["lab values", "medication names", "imaging terms"],
    "description": "Brief description of what the image contains",
    "extracted_text": "All text content extracted from the image (only for Lab Report, Prescription, Pharmacy Bill, Vitals Details)"
}"""

        # Analyze image
        messages = [
            SystemMessage(content="You are an expert at analyzing medical documents and images to classify them into appropriate categories."),
            HumanMessage(content=[
                {"type": "text", "text": analysis_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ])
        ]
        
        response = vision_llm.invoke(messages)
        
        if not response or not response.content:
            return DocumentAnalysisResult(
                document_type="Unknown",
                confidence=0.0,
                sub_category=None,
                key_indicators=[],
                description="Empty response from vision model"
            )
        
        # Parse response
        import json
        import re
        
        try:
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:-3].strip()
            elif content.startswith('```'):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            
            return DocumentAnalysisResult(
                document_type=result.get("document_type", "Other"),
                confidence=result.get("confidence", 0.5),
                sub_category=result.get("sub_category"),
                key_indicators=result.get("key_indicators", []),
                description=result.get("description", ""),
                extracted_text=result.get("extracted_text", "")
            )
            
        except json.JSONDecodeError:
            # Fallback - simple keyword extraction
            content_lower = response.content.lower()
            
            # Check for different document types based on keywords
            if any(word in content_lower for word in ["lab", "test", "result", "blood", "urine"]):
                return DocumentAnalysisResult(
                    document_type="Lab Report",
                    confidence=0.6,
                    sub_category="blood test",
                    key_indicators=["lab results", "test values"],
                    description="Lab report detected",
                    extracted_text=""
                )
            elif any(word in content_lower for word in ["prescription", "medication", "rx", "dosage"]):
                return DocumentAnalysisResult(
                    document_type="Prescription",
                    confidence=0.6,
                    sub_category="medication",
                    key_indicators=["prescription", "medication"],
                    description="Prescription detected",
                    extracted_text=""
                )
            elif any(word in content_lower for word in ["pharmacy", "bill", "cost", "price"]):
                return DocumentAnalysisResult(
                    document_type="Pharmacy Bill",
                    confidence=0.6,
                    sub_category="medication bill",
                    key_indicators=["pharmacy", "bill"],
                    description="Pharmacy bill detected",
                    extracted_text=""
                )
            elif any(word in content_lower for word in ["x-ray", "mri", "ct", "scan", "imaging"]):
                return DocumentAnalysisResult(
                    document_type="Medical Imaging",
                    confidence=0.6,
                    sub_category="medical scan",
                    key_indicators=["medical imaging"],
                    description="Medical imaging detected",
                    extracted_text=""
                )
            elif any(word in content_lower for word in ["food", "meal", "dish", "nutrition"]):
                return DocumentAnalysisResult(
                    document_type="Nutrition",
                    confidence=0.6,
                    sub_category="food",
                    key_indicators=["food", "nutrition"],
                    description="Nutrition/food image detected",
                    extracted_text=""
                )
            else:
                return DocumentAnalysisResult(
                    document_type="Other",
                    confidence=0.5,
                    sub_category=None,
                    key_indicators=[],
                    description="Other type of document",
                    extracted_text=""
                )
        
    except Exception as e:
        print(f"❌ [DEBUG] Image analysis failed: {str(e)}")
        return DocumentAnalysisResult(
            document_type="Unknown",
            confidence=0.0,
            sub_category=None,
            key_indicators=[],
            description=f"Error analyzing image: {str(e)}",
            extracted_text=""
        )


def analyze_document_type(text: str) -> DocumentAnalysisResult:
    """
    Analyze text content to identify the type of document.
    
    Args:
        text (str): The extracted text content from the document
        
    Returns:
        DocumentAnalysisResult: Structured result containing document type and details
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1
    )
    
    # Create PydanticOutputParser for DocumentAnalysisResult
    parser = PydanticOutputParser(pydantic_object=DocumentAnalysisResult)
    
    # Create prompt template with parser format instructions
    prompt = PromptTemplate(
        template="""You are a medical document classification expert. Carefully analyze the provided text and identify the most appropriate document type.

Document Types to Classify:
1. Clinical Notes - Handwritten notes by doctors, outpatient records, consultation sheets. These often include the doctor’s name, patient’s name, and free-form notes. Even if lab values are mentioned, it is still a clinical note unless it is structured like a lab report.
    Characteristics:
    - Contains "OUT-PATIENT RECORD", doctor's name, and patient's name. or if it mentions "OPD"
    - Handwritten, scanned, or loosely formatted
    - Mentions of lab values like "ALT 245", "Platelets", etc., without structured lab format
    - May include medications, appointment times, or follow-up plans
    - also mentions the patient has taken the medication or has the lab test done
    - Does NOT include official lab headers or tabular formats

    ❗NOTE: Do not classify as a lab report **just because lab values are present**. Clinical notes often include lab data.

2. Prescription - Formal prescription documents listing medications and dosages with the intent to be sent to a pharmacy.

3. Lab Report - Structured documents from pathology/lab departments. Typically include:
    - Headers like “LAB REPORT” or lab names
    - Table format with reference ranges
    - Technician signature or stamp
    - Test categories like “BIOCHEMISTRY”, “HEMATOLOGY”

4. Pharmacy Bill - Medication bills or invoices from pharmacies.

5. Medical Imaging - Descriptions or reports of CT, MRI, X-ray findings.

6. Body Images - Photos of body parts, skin, wounds, scans without interpretation.

7. Vitals Details - Heart rate, blood pressure, temperature readings, typically machine-logged.

8. Nutrition - Food photos, meal plans, or text describing diets.

9. Other - Anything that doesn’t fit above.

IMPORTANT:
If the document includes lab test values (e.g., AST, ALT, CBC) but:
- is handwritten or free-form
- contains "OUT-PATIENT RECORD"
- includes doctor’s name, patient name, and appointment time
- lists treatment/medications (e.g., Peg Interferon, Entecavir)
then it should be classified as a **Clinical Note**, not a Lab Report.

DO NOT classify documents as lab reports unless:
- the document header clearly identifies it as a lab result/report
- it is structured in tabular format
- it includes reference ranges and interpretation
- there is no clinical planning or medications mentioned

Analyze the following text and classify the document type:

{input}

{format_instructions}""",
        input_variables=["input"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    print("staring document analysis")
    
    try:
        # Use the prompt | llm | parser chain
        output = (prompt | llm | parser).invoke({"input": text})
        print(f"✅ Successfully parsed with PydanticOutputParser: {output.document_type}")
        return output
        
    except Exception as e:
        print(f"❌ Error parsing with PydanticOutputParser: {str(e)}")
        # Fallback in case of parsing errors
        return DocumentAnalysisResult(
            document_type="Unknown",
            confidence=0.0,
            sub_category=None,
            key_indicators=[],
            description=f"Error parsing analysis: {str(e)}",
            extracted_text=""
        )


def create_file_type_workflow():
    """Create a LangGraph workflow for file type detection and processing."""
    
    # Set up LangSmith tracing
    tracer = LangChainTracer()
    callback_manager = CallbackManager([tracer])
    
    # Create the workflow
    workflow = StateGraph(FileState)
    
    # Add nodes
    workflow.add_node("detect_file_type", detect_file_type)
    workflow.add_node("handle_pdf", handle_pdf)
    workflow.add_node("handle_image", handle_image)
    workflow.add_node("handle_unsupported", handle_unsupported)
    workflow.add_node("handle_result", handle_result)
    
    # Set entry point by adding an edge from the START node
    workflow.add_edge(START, "detect_file_type")
    
    # Add conditional edges from detect_file_type to appropriate handlers
    workflow.add_conditional_edges(
        "detect_file_type",
        decide_processing_path,
        {
            "handle_pdf": "handle_pdf",
            "handle_image": "handle_image",
            "handle_unsupported": "handle_unsupported"
        }
    )
    
    # Add conditional edges from handlers to check success
    workflow.add_conditional_edges(
        "handle_pdf",
        check_processing_success,
        {
            "handle_unsupported": "handle_unsupported",
            "handle_result": "handle_result"
        }
    )
    
    workflow.add_conditional_edges(
        "handle_image",
        check_processing_success,
        {
            "handle_unsupported": "handle_unsupported",
            "handle_result": "handle_result"
        }
    )
    
    # Add edges from result and unsupported to END
    workflow.add_edge("handle_result", END)
    workflow.add_edge("handle_unsupported", END)
    
    return workflow.compile(checkpointer=MemorySaver())


async def process_file_async(user_id: str, file_name: str = None, file_type: str = None, image_path: str = None, image_base64: str = None, source_file_path: str = None, analysis_only: bool = False) -> dict:
    """
    Process a file and return its type (async version).
    
    Args:
        user_id (str): The user ID associated with the file
        file_path (str): Path to the file to analyze
        
    Returns:
        dict: Dictionary containing file_type and error information
    """
    # Create the workflow
    workflow = create_file_type_workflow()
    
    # Initialize the state with all required fields
    initial_state = FileState(
        user_id=user_id,
        analysis_only=analysis_only,
        file_path=source_file_path,
        file_name=file_name,
        file_type=file_type,
        image_base64=image_base64,
        error="",
        processing_result="",
        analysis_result=DocumentAnalysisResult(
            document_type="", 
            confidence=0.0, 
            sub_category="", 
            key_indicators=[], 
            description="", 
            extracted_text=""
        ),
        ocr_result="",
        lab_agent_result="",
        processing_success=False,
        processing_message="",
        processing_statistics={},
        individual_record_results=[],
        error_details={}
    )
    
    # Run the workflow with async invocation and LangSmith tracing
    result = await workflow.ainvoke(
        initial_state,
        config={
            "configurable": {"thread_id": "test-thread"},
            "callbacks": [LangChainTracer()]
        }
    )
    
    # Convert analysis_result to dict if it's a Pydantic model for JSON serialization
    analysis_result = result.get("analysis_result")
    if analysis_result and hasattr(analysis_result, 'model_dump'):
        analysis_result = analysis_result.model_dump()
    elif analysis_result and hasattr(analysis_result, 'dict'):
        analysis_result = analysis_result.dict()
    
    return {
        "file_type": result["file_type"],
        "error": result["error"],
        "processing_result": result["processing_result"],
        "analysis_result": analysis_result,
        "ocr_result": result.get("ocr_result", ""),
        "lab_agent_result": result.get("lab_agent_result", ""),
        "clinical_agent_result": result.get("clinical_agent_result", ""),
        "pharmacy_agent_result": result.get("pharmacy_agent_result", ""),
        "vitals_agent_result": result.get("vitals_agent_result", ""),
        "nutrition_agent_result": result.get("nutrition_agent_result", ""),
        "file_name": result.get("file_name", ""),
        "processing_success": result.get("processing_success", False),
        "processing_message": result.get("processing_message", ""),
        "processing_statistics": result.get("processing_statistics", {}),
        "individual_record_results": result.get("individual_record_results", []),
        "error_details": result.get("error_details", {})
    }



