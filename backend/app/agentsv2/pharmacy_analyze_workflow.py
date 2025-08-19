from pathlib import Path
import sys
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import json
import pandas as pd
import traceback
import ast
import re

from dotenv import load_dotenv
load_dotenv()

# E2B Sandbox imports
# Removed E2B dependency - using local execution

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from app.core.config import settings
from configurations.pharmacy_config import PHARMACY_TABLES, PRIMARY_PHARMACY_TABLE
import psycopg2
from psycopg2.extras import RealDictCursor

from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from typing import Annotated, Sequence
import operator

# LangSmith tracing imports
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager

# Import create_react_agent for simplified tool handling
from langgraph.prebuilt import create_react_agent
from app.agentsv2.tools.pharmacy_tools import pharmacy_medication_search_tool

@dataclass
class PharmacyAnalyzeWorkflowState:
    """State management for the pharmacy analyze workflow"""
    # Input data
    original_request: str = ""
    user_id: Optional[int] = None
    
    # Analysis planning
    analysis_type: str = ""
    analysis_plan: Dict[str, Any] = field(default_factory=dict)
    data_requirements: List[str] = field(default_factory=list)
    
    # Data context
    raw_data: Dict[str, pd.DataFrame] = field(default_factory=dict)
    data_summary: Dict[str, Any] = field(default_factory=dict)
    
    # Code generation and execution
    generated_code: str = ""
    execution_results: Dict[str, Any] = field(default_factory=dict)
    execution_output: str = ""
    execution_error: Optional[str] = None
    
    # Visualization
    plots: List[str] = field(default_factory=list)  # Base64 encoded images
    
    # Response formatting
    formatted_results: Dict[str, Any] = field(default_factory=dict)
    
    # Error handling
    has_error: bool = False
    error_context: Optional[Dict] = None
    
    # Execution log
    execution_log: List[Dict] = field(default_factory=list)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)

class PharmacyAnalyzeWorkflow:
    """
    LangGraph-based analyze workflow for pharmacy data analysis.
    
    Thread-safe and designed for shared instance usage.
    All state is managed through PharmacyAnalyzeWorkflowState objects passed to methods.
    """
    
    def __init__(self, pharmacy_agent_instance=None):
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        
        self.llm = ChatOpenAI(model=settings.PHARMACY_VISION_MODEL)
        
        # Store reference to the parent pharmacy agent for method reuse
        self.pharmacy_agent = pharmacy_agent_instance
        
        # Initialize data containers
        self.current_data = {}
        self.current_results = {}
        self.current_plots = []
        self.downloaded_plot_files = []
        
        # Create tools and workflow
        self.tools = self._create_tools()
        self.workflow = self._build_workflow()
    
    def _create_tools(self):
        """Create tools for the agent to use"""
        
        # Use the new pharmacy_medication_search_tool
        medication_search_tool = pharmacy_medication_search_tool
        
        @tool
        async def retrieve_pharmacy_data(request: str) -> str:
            """
            Retrieve pharmacy data based on a natural language request.
            
            The agent can use this tool to:
            - Get relevant pharmacy data for analysis
            - Verify retrieved data matches the request
            - Query additional data if needed
            - Refine queries based on analysis requirements
            
            Args:
                request: Natural language description of what pharmacy data is needed
                
            Returns:
                JSON string of retrieved pharmacy data or error message
            """
            try:
                if not self.pharmacy_agent:
                    return "Error: Pharmacy agent not available for data retrieval"
                
                # Create a temporary pharmacy state for the request
                from app.agentsv2.pharmacy_agent import PharmacyAgentState
                pharmacy_state = PharmacyAgentState(
                    original_prompt=request,
                    user_id=self.current_user_id
                )
                
                # Use the pharmacy agent's retrieval method (now properly awaited)
                result_state = await self.pharmacy_agent.retrieve_pharmacy_data(pharmacy_state)
                
                if result_state.has_error:
                    return f"Data retrieval failed: {result_state.error_context.get('message', 'Unknown error')}"
                
                # Extract raw data from the agent's execution
                # The pharmacy agent uses tools that return raw JSON data, but the final output mixes it with commentary
                # Let's try to extract just the JSON data part
                query_results = result_state.query_results
                if query_results and "output" in query_results:
                    output_content = query_results["output"]
                    
                    # Try to extract JSON arrays in the output (pharmacy data is typically returned as JSON arrays)
                    json_pattern = r'\[\s*\{.*?\}\s*\]'
                    json_matches = re.findall(json_pattern, output_content, re.DOTALL)
                    
                    if json_matches:
                        # Use the last/largest JSON match (most likely to be the complete data)
                        json_data = json_matches[-1]
                        try:
                            parsed_data = json.loads(json_data)
                            if isinstance(parsed_data, list) and parsed_data:
                                self.retrieved_data_json = json_data
                                return f"Retrieved {len(parsed_data)} pharmacy records.\n\nComplete pharmacy data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it - it will be available as 'pharmacy_data' DataFrame."
                        except json.JSONDecodeError:
                            pass
                    
                    # If no JSON found, try to extract any structured data patterns
                    # Look for lines that might contain structured data
                    lines = output_content.split('\n')
                    data_lines = []
                    for line in lines:
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            data_lines.append(line)
                        elif '"' in line and ':' in line:  # Looks like JSON-ish content
                            data_lines.append(line)
                    
                    if data_lines:
                        try:
                            # Try to reconstruct as JSON array
                            reconstructed = '[' + ','.join(data_lines) + ']'
                            parsed_data = json.loads(reconstructed)
                            if isinstance(parsed_data, list) and parsed_data:
                                self.retrieved_data_json = reconstructed
                                return f"Retrieved {len(parsed_data)} pharmacy records (reconstructed).\n\nComplete pharmacy data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it."
                        except:
                            pass
                    
                    # If we can't extract structured data, return the full raw response
                    return f"Data retrieved but could not extract structured format. Full raw response:\n{output_content}\n\nNote: The pharmacy agent returned commentary instead of raw data. You may need to refine the request."
                
                else:
                    return "No data found for the request"
                    
            except Exception as e:
                return f"Error retrieving pharmacy data: {str(e)}"
        
        @tool
        async def execute_python_code(code: str) -> str:
            """
            Execute Python code locally with safe environment.
            
            This tool allows the agent to:
            - Run pharmacy data analysis and visualization code
            - Access pandas, numpy, matplotlib, seaborn
            - Save plots directly to data/plots/ folder using save_plot()
            - Handle errors gracefully
            
            Args:
                code: Python code to execute
                
            Returns:
                Execution results or error message
            """
            try:
                import os
                import sys
                import io
                import json
                import base64
                import pandas as pd
                import numpy as np
                import matplotlib
                matplotlib.use('Agg')  # Use non-interactive backend
                import matplotlib.pyplot as plt
                import seaborn as sns
                from datetime import datetime
                
                # Create plots directory if it doesn't exist
                plots_dir = "data/plots"
                os.makedirs(plots_dir, exist_ok=True)
                
                # Results container
                results = {}
                plot_buffers = []
                saved_plot_files = []
                
                def save_plot(filename=None, plt_figure=None, format='png', dpi=100):
                    """Save matplotlib plot directly to data/plots folder"""
                    try:
                        if plt_figure is None:
                            plt_figure = plt.gcf()
                        
                        # Generate filename if not provided
                        if filename is None:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"pharmacy_plot_{timestamp}.png"
                        elif not filename.endswith('.png'):
                            filename = filename + ".png"
                        
                        # Save directly to data/plots folder
                        local_path = os.path.join(plots_dir, filename)
                        plt_figure.savefig(local_path, format=format, dpi=dpi, bbox_inches='tight')
                        
                        # Also save to base64 buffer for response
                        buffer = io.BytesIO()
                        plt_figure.savefig(buffer, format=format, dpi=dpi, bbox_inches='tight')
                        buffer.seek(0)
                        
                        plot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        plot_buffers.append(plot_base64)
                        
                        buffer.close()
                        plt.close(plt_figure)
                        
                        # Track saved files
                        saved_plot_files.append({
                            "filename": filename,
                            "local_path": local_path,
                            "base64": plot_base64,
                            "size_bytes": os.path.getsize(local_path)
                        })
                        
                        return f"Plot saved as {filename} in {plots_dir}! Total plots: {len(plot_buffers)}"
                    except Exception as e:
                        return f"Error saving plot: {str(e)}"
                
                # Set up execution environment
                exec_globals = {
                    'pd': pd,
                    'np': np,
                    'plt': plt,
                    'sns': sns,
                    'json': json,
                    'os': os,
                    'datetime': datetime,
                    'results': results,
                    'save_plot': save_plot,
                    'plot_buffers': plot_buffers,
                    'retrieved_data': self.current_data,
                    'pharmacy_data': pd.DataFrame(self.current_data) if self.current_data else pd.DataFrame()
                }
                
                # Capture stdout for output
                old_stdout = sys.stdout
                captured_output = io.StringIO()
                sys.stdout = captured_output
                
                try:
                    # Execute the code
                    exec(code, exec_globals)
                    
                    # Get the output
                    output_text = captured_output.getvalue()
                    
                    # Update current results and plots
                    self.current_results = exec_globals.get('results', {})
                    self.current_plots = plot_buffers
                    if saved_plot_files:
                        self.downloaded_plot_files = saved_plot_files
                    
                    # Format response
                    response = "Code executed successfully locally!\n"
                    if output_text.strip():
                        response += f"Output:\n{output_text}\n"
                    if self.current_results:
                        response += f"Results keys: {list(self.current_results.keys())}\n"
                    if plot_buffers:
                        response += f"Generated {len(plot_buffers)} visualization(s)\n"
                    if saved_plot_files:
                        response += f"Saved {len(saved_plot_files)} plot(s) to {plots_dir}/\n"
                        for plot in saved_plot_files:
                            response += f"  - {plot['filename']}\n"
                    
                    return response
                    
                except Exception as e:
                    return f"Code execution failed: {str(e)}"
                    
                finally:
                    # Restore stdout
                    sys.stdout = old_stdout
                
            except Exception as e:
                return f"Failed to execute code: {str(e)}"
        
        return [medication_search_tool, retrieve_pharmacy_data, execute_python_code]
    
    def get_tools(self):
        """Get the list of available tools."""
        return self.tools
    
    def _build_workflow(self):
        """Build the LangGraph workflow for pharmacy code interpretation"""
        # Set up LangSmith tracing
        tracer = LangChainTracer()
        callback_manager = CallbackManager([tracer])
        
        workflow = StateGraph(PharmacyAnalyzeWorkflowState)
        
        # Add nodes for the agent-driven approach
        workflow.add_node("analyze_request", self.analyze_request)
        workflow.add_node("agent_code_analysis", self.agent_code_analysis)
        workflow.add_node("format_results", self.format_results)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point
        workflow.add_edge(START, "analyze_request")
        
        # Workflow with error handling
        workflow.add_conditional_edges(
            "analyze_request",
            self.check_analysis_success,
            {
                "continue": "agent_code_analysis",
                "error": "handle_error"
            }
        )
        
        # Agent completes analysis and goes to format results
        workflow.add_edge("agent_code_analysis", "format_results")
        
        # End workflow
        workflow.add_edge("format_results", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    def check_analysis_success(self, state: PharmacyAnalyzeWorkflowState) -> str:
        return "error" if state.has_error else "continue"
    
    async def analyze_request(self, state: PharmacyAnalyzeWorkflowState) -> PharmacyAnalyzeWorkflowState:
        """Step 1: Analyze the request using an agent to classify analysis type and create detailed plan"""
        try:
            self.log_execution_step(state, "analyze_request", "started")
            
            # Store user_id for data retrieval tool
            self.current_user_id = state.user_id
            
            # Initialize data containers
            self.current_data = {}
            self.current_results = {}
            self.current_plots = []
            
            # Create analysis classification prompt
            classification_prompt = """
            You are a pharmacy data analysis and planning agent. Your role is to interpret user requests about pharmacy bills and medication preferences, and break them down into a structured plan of actions that a downstream execution agent (e.g., Python code executor, web browser, or API connector) can perform.

            The user may request anything from simple nutrient tracking to complex goal-based recommendations using external data sources. Your job is to:

                Understand the intent and scope of the user’s pharmacy-related query.

                Classify the core tasks involved.

                Design a multi-step plan, with each step tagged for the appropriate execution tool (e.g., python, browser, API, or manual_review).

                Identify required input data, user context, and outputs expected.

                Handle ambiguities by requesting missing details explicitly.

                Ensure privacy and ethical handling of user data at all steps.


                {{
                "user_request": "{0}",
                "goals": ["{0}"],
                "user_id": {1},
                "tasks": [
                    {{
                    "task_id": "step_1",
                    "description": "Natural language description of what needs to be done",
                    "tool": "python|browser|api|manual_review",
                    "inputs_required": ["list", "of", "data", "fields", "or", "parameters"],
                    "expected_output": "Describe the format and insight expected",
                    "notes": "Any contextual notes, assumptions, or warnings"
                    }}
                ],
                "data_requirements": {{
                    "pharmacy": ["nutrient categories", "medication logs", "dates", "portion sizes", "etc."],
                    "demographics": ["age", "sex", "weight", "goals", "activity level"],
                    "external_sources": ["yes|no|optional", "e.g., YouTube, USDA API, recipe DB"],
                    "nutrient_targets": "yes|no|optional"
                }},
                "time_period": "recent|7_days|30_days|6_months|1_year|user_specified",
                "granularity": "daily|weekly|per_prescription|as_suitable",
                "missing_information": ["list", "of", "questions", "or", "inputs", "needed", "from", "user"],
                "privacy": "All user data remains confidential and handled according to best privacy practices."
                }}
            """.format(state.original_request, state.user_id)
            
            # Use LLM to classify and plan the analysis
            try:
                response = await self.llm.ainvoke([HumanMessage(content=classification_prompt)])
                
                # Extract JSON from response
                response_content = response.content if hasattr(response, 'content') else str(response)
                
                # Try to parse JSON from the response
                import re
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    analysis_json = json_match.group()
                    analysis_data = json.loads(analysis_json)
                    
                    # Set analysis type and plan from agent response
                    state.analysis_type = analysis_data.get("analysis_type", "custom")
                    
                    # Store the complete analysis plan including goals, tasks, and detailed structure
                    state.analysis_plan = {
                        "description": f"Analyze pharmacy data: {state.original_request}",
                        "methodology": analysis_data.get("methodology", "Standard statistical analysis"),
                        "visualizations": analysis_data.get("visualizations", ["bar_chart", "line_chart"]),
                        "metrics": analysis_data.get("metrics", ["mean", "trend"]),
                        "goals": analysis_data.get("goals", [state.original_request]),
                        "tasks": analysis_data.get("tasks", []),
                        "time_period": analysis_data.get("time_period", "recent"),
                        "granularity": analysis_data.get("granularity", "daily"),
                        "missing_information": analysis_data.get("missing_information", [])
                    }
                    
                    # Store additional analysis metadata
                    state.data_requirements = analysis_data.get("data_requirements", [])
                    
                    self.log_execution_step(state, "analyze_request", "classified", {
                        "analysis_type": state.analysis_type,
                        "complexity": analysis_data.get("complexity", "moderate")
                    })
                    
                else:
                    raise Exception("Could not extract JSON from LLM response")
                    
            except Exception as e:
                # Fallback to simple classification if agent fails
                self.log_execution_step(state, "analyze_request", "fallback", {"error": str(e)})
                state.analysis_type = "statistical_summary"
                state.analysis_plan = {
                    "description": f"Perform statistical analysis of pharmacy data: {state.original_request}",
                    "methodology": "Descriptive statistics and visualization",
                    "visualizations": ["bar_chart", "summary_table"],
                    "metrics": ["mean", "median", "range", "nutrient_distribution"]
                }
                state.data_requirements = ["pharmacy_data"]
            
            self.log_execution_step(state, "analyze_request", "completed")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {"step": "analyze_request", "error": str(e)}
            self.log_execution_step(state, "analyze_request", "failed", {"error": str(e)})
        
        return state
    
    async def agent_code_analysis(self, state: PharmacyAnalyzeWorkflowState) -> PharmacyAnalyzeWorkflowState:
        """Agent-driven code analysis with iterative tool usage"""
        try:
            self.log_execution_step(state, "agent_code_analysis", "started")
            
            # Store user_id for data retrieval tool
            self.current_user_id = state.user_id
            
            # Initialize data containers for the agent's work
            self.current_data = {}
            self.current_results = {}
            self.current_plots = []
            current_date = datetime.now().strftime('%Y_%m_%d')
            # If this is the first time (no messages), set up the conversation
            if not state.messages:
                system_prompt = f"""
                You are a Python data analysis expert specializing in pharmacy and dietary data. Your goal is to perform the requested analysis by executing a detailed multi-step plan that has been created specifically for this request.

                Analysis Request: {state.original_request}
                Analysis Type: {state.analysis_type}
                Analysis Plan: {json.dumps(state.analysis_plan, indent=2)}
                Data Requirements: {json.dumps(state.data_requirements, indent=2) if state.data_requirements else 'Not specified'}
                User ID: {state.user_id}
                
                🎯 REQUEST ANALYSIS: This request asks for "{state.original_request}"
                - If this mentions "recipes", "YouTube", "browsing", or "internet": USE web_search tool!
                - If this asks for protein recommendations: USE web_search for recipe ideas!
                - If this asks for external information: USE web_search immediately!

                DETAILED EXECUTION PLAN:
                The analysis request has been broken down into a structured plan. You MUST follow this plan step by step to ensure comprehensive analysis:

                Goals to Achieve: {json.dumps(state.analysis_plan.get('goals', [state.original_request]), indent=2)}
                
                Tasks to Execute:
                {json.dumps(state.analysis_plan.get('tasks', []), indent=2)}
                
                Data Requirements:
                - Pharmacy Data: {json.dumps(state.data_requirements.get('pharmacy', []), indent=2) if isinstance(state.data_requirements, dict) else state.data_requirements}
                - Demographics: {json.dumps(state.data_requirements.get('demographics', []), indent=2) if isinstance(state.data_requirements, dict) and 'demographics' in state.data_requirements else 'Not specified'}
                - External Sources: {state.data_requirements.get('external_sources', 'Not specified') if isinstance(state.data_requirements, dict) else 'Not specified'}
                
                Time Period: {state.analysis_plan.get('time_period', 'Not specified')}
                Granularity: {state.analysis_plan.get('granularity', 'Not specified')}

                You have access to three tools:
                1. web_search: Search the web for ANY external information including:
                   - Recipe recommendations and cooking videos (YouTube, cooking sites)
                   - Pharmacy research and scientific studies
                   - Dietary guidelines and recommendations
                   - Medication composition databases
                   - Protein-rich medication lists and prescription ideas
                   - while using web_search, use your knowledge to ask a broader question like "high protein recipes for 150g daily protein means it can over multiple prescriptions"
                   
                   🎯 CRITICAL: The web_search tool now returns RICH CONTENT DATA including:
                   - Actual recipe details with ingredients and instructions
                   - Prescription plan items with pharmacyal breakdowns
                   - Cooking instructions and preparation steps
                   - Pharmacyal information and tips
                   - Structured content ready for prescription planning
                   
                   ⚠️ DO NOT just list URLs! Use the extracted content to CREATE CUSTOMIZED MEAL PLANS:
                   - Extract specific recipes from the 'recipes' field
                   - Use 'ingredients' lists to create shopping lists
                   - Use 'instructions' to provide cooking guidance
                   - Use 'prescription_plan' data to structure daily/weekly plans
                   - Use 'pharmacyal_info' to show macro breakdowns
                   - Combine multiple sources to create comprehensive plans
                   
                   USE THIS TOOL whenever you need external recipes, YouTube videos, or web research!
                   
                2. retrieve_pharmacy_data: Get pharmacy data based on natural language requests. Be very specific of the time granularity while retrieving the data and the aggregation of the data.
                3. execute_python_code: Execute Python code for analysis

                EXECUTION STRATEGY:
                Follow the detailed plan above and execute each task systematically:
                
                1. Review the Goals and Tasks: Understand what specific outcomes are expected
                2. ALWAYS use web_search when the user asks for:
                   - medication recommendations or suggestions
                   - External research or studies
                   - Any information not in the user's personal data
                3. Use retrieve_pharmacy_data to get the specific data requirements identified in the plan
                4. For each task marked as "python", use execute_python_code to perform the analysis, while performing the analysis be very specific of the time granularity while calculating the metrics.
                5. For each task marked as "browser", use web_search to gather external information
                6. Verify retrieved data matches the data requirements in the plan
                7. If data is insufficient, retrieve additional data with refined requests
                8. Create visualizations as specified in the plan
                9. Ensure all tasks in the plan are completed before concluding

                CRITICAL GUIDELINES - YOU MUST FOLLOW THESE:
                
                🚨 DO NOT ASK THE USER FOR INFORMATION! 🚨
                You have tools available - USE THEM to get the data you need!
                
                MANDATORY EXECUTION STEPS:
                1. IMMEDIATELY start by using retrieve_pharmacy_data tool to get user's pharmacy data
                2. If user asks for medication recommendations or suggestions, or external research: IMMEDIATELY use web_search tool
                3. Use execute_python_code tool to analyze the retrieved data
                4. DO NOT request additional information from the user - work with available data
                5. If initial data retrieval is insufficient, try different search terms with the tools
                
                🔍 WEB SEARCH TRIGGERS - Use web_search tool when user mentions:
                - "medication recommendations" or "medication suggestions"
                - "research" or "studies"
                - "browsing" or "internet" or "online"
                
               
                📊 EXAMPLE MEDICATION recommendations OUTPUT FORMAT:
                ```
                "Based on the medication recommendations I found, here's your customized plan along with price of the medication and pharmacy name"
                
                "Medication Name: [medication name]
                Pharmacy Name: [pharmacy name]
                Price: [price]
                Quantity: [quantity]
                Date of Purchase: [date of purchase]
                Total Tax: [total tax]
                Total Amount: [total amount]
                
                ```
                
                Tool Usage Rules:
                - retrieve_pharmacy_data: Get ALL available pharmacy data for the user - be broad in your requests
                - web_search: MUST BE USED for external information including:
                  * Medication searches: "high protein medications for 150g daily protein"
                  * Research: "medication intake recommendations studies"
                  * Medication lists: "best high protein medications list"
                  * Pharmacy searches: "pharmacy near me"
                  
                  ⚠️ CRITICAL: After web_search, ALWAYS extract and use the rich content fields:
                  * result['medications'] - actual medication content
                  * result['prescription_plan'] - prescription planning data (medication name, quantity, price, date of purchase, total tax, total amount, pharmacy name)
                  

                - execute_python_code: Perform analysis, calculations, and create visualizations
                - Store your final results in a 'results' dictionary when using execute_python_code
                - CRITICAL: To save plots, you MUST use save_plot() function, NOT plt.savefig()
                - Use save_plot('filename') after creating each visualization
                - save_plot() saves files directly to data/plots/ folder
                
                WORKFLOW ENFORCEMENT:
                - Start immediately with tool usage - no explanations or requests for more info
                - Work with whatever data is available from the tools
                - If tools return empty results, acknowledge this and provide general recommendations
                - Complete the full analysis pipeline using available tools before responding to user

                Guidelines for retrieving pharmacy data:
                - Use the retrieve_pharmacy_data tool to get relevant data for the analysis
                - Get comprehensive pharmacy data in order to perform the analysis. Don't restrict to only few nutrients, the tool is an agent so give wide request to get all the data. Ask the agent to give you in JSON format with no commentary and not reduce the data. Get all the data in the JSON format.
                - Example: "Get me all my protein intake data" or "Get me all my prescription data for the last month"
                - Use synonyms of the nutrient names and also short forms and long forms of the nutrient names.
                - Try to get all the data in the first call to retrieve_pharmacy_data tool instead of batching the requests.
                - If the data is not sufficient, use the retrieve_pharmacy_data tool again with a more specific request.
                - If the data is still not sufficient, use the retrieve_pharmacy_data tool again with a more specific request.

                PLOT SAVING EXAMPLE:
                ```python
                plt.figure(figsize=(12, 6))
                # ... create your plot ...
                plt.title('My Pharmacy Chart')
                
                # 🚨 CRITICAL: DATE FORMATTING TO PREVENT OVERLAPPING X-AXIS LABELS
                # If your plot has dates on x-axis, ALWAYS include these lines:
                import matplotlib.dates as mdates
                from matplotlib.ticker import MaxNLocator
                
                # For date-based x-axis (MANDATORY for time series):
                plt.xticks(rotation=45, ha='right')  # Rotate labels 45 degrees
                plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=8))  # Limit to 8 labels max
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))  # Short date format
                
                # Alternative for longer time periods:
                # plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))  # Month-year format
                
                # Always use tight layout to prevent label cutoff:
                plt.tight_layout()
                
                # Add date postfix to filename for uniqueness (datetime is globally available)
                
                save_plot(f'my_pharmacy_chart_name_{current_date}')  # ← Use this, NOT plt.savefig()
                plt.close()
                ```
                
                ADDITIONAL DATE FORMATTING EXAMPLES:
                ```python
                # For daily pharmacy data over weeks/months:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                plt.xticks(rotation=45)
                
                # For monthly pharmacy data over years:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                plt.xticks(rotation=45)
                
                # For automatic date formatting (recommended):
                plt.gcf().autofmt_xdate()  # Automatically format x-axis dates
                ```

                Available libraries in code execution: pandas (pd), numpy (np), matplotlib.pyplot (plt), seaborn (sns)

                
                REQUIRED RESPONSE FORMAT:
                After completing your analysis, end your response with a structured summary in this exact JSON format:
                ```json
                {{
                    "analysis_summary": "Brief summary of key findings",
                    "key_insights": ["insight 1", "insight 2", "insight 3"],
                    "visualizations_created": [
                        {{
                            "filename": "plot_filename.png",
                            "title": "Descriptive title of the plot",
                            "description": "What this visualization shows",
                            "key_findings": "Key insights from this chart",
                            "plot_path": "saved_plot_path"
                        }}
                    ],
                    "data_quality": "Assessment of data completeness and reliability",
                    "recommendations": ["recommendation 1", "recommendation 2"]
                }}
                ```

                Keep working with both tools until you achieve a comprehensive analysis and provide the structured JSON response!
                """
                
                # Start the conversation with the agent
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Please analyze: {state.original_request}")
                ]
                
                state.messages = messages
            
            # Create a ReAct agent that can execute tools automatically
            react_agent = create_react_agent(
                model=self.llm,
                tools=self.get_tools()
            )
            
            # Use the ReAct agent to process the request with tool execution
            result = await react_agent.ainvoke({"messages": state.messages})
            
            # Update state with all messages from the agent conversation
            state.messages = result["messages"]
            
            # Get the last message for debugging
            last_message = state.messages[-1] if state.messages else None
            print(f"🔍 [DEBUG] agent_code_analysis - Result type: {type(result)}")
            print(f"🔍 [DEBUG] agent_code_analysis - Last message type: {type(last_message)}")
            print(f"🔍 [DEBUG] agent_code_analysis - Total messages: {len(state.messages)}")
            print(f"🔍 [DEBUG] agent_code_analysis - ReAct agent completed with {len(result['messages'])} messages")
            
            # The agent will now use tools iteratively through the workflow
            self.log_execution_step(state, "agent_code_analysis", "setup_complete")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "step": "agent_code_analysis",
                "error": str(e)
            }
            self.log_execution_step(state, "agent_code_analysis", "failed", {"error": str(e)})
        
        return state
    
    def _convert_to_json_serializable(self, obj):
        """Convert numpy types and other non-JSON-serializable objects to native Python types"""
        import numpy as np
        import pandas as pd
        
        if isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    async def format_results(self, state: PharmacyAnalyzeWorkflowState) -> PharmacyAnalyzeWorkflowState:
        """Step 3: Format the final results"""
        try:
            self.log_execution_step(state, "format_results", "started")
            
            print(f"🔍 [DEBUG] format_results - Has error: {state.has_error}")
            print(f"🔍 [DEBUG] format_results - Current results: {self.current_results}")
            print(f"🔍 [DEBUG] format_results - Current plots: {len(self.current_plots)} plots")
            print(f"🔍 [DEBUG] format_results - Downloaded files: {len(getattr(self, 'downloaded_plot_files', []))}")
            
            if state.has_error:
                error_msg = "Unknown error"
                if state.error_context and isinstance(state.error_context, dict):
                    error_msg = state.error_context.get("error", "Unknown error")
                
                state.formatted_results = {
                    "success": False,
                    "error": error_msg,
                    "execution_log": state.execution_log
                }
            else:
                # After ReAct agent execution, get results directly from instance variables
                final_results = self._convert_to_json_serializable(self.current_results)
                final_plots = self.current_plots
                downloaded_files = getattr(self, 'downloaded_plot_files', [])
                
                # Check if we have any results from the analysis
                final_response = "Pharmacy analysis completed successfully."
                if final_results or final_plots or downloaded_files:
                    final_response = "Pharmacy analysis completed with data processing and visualization generation."
                
                state.formatted_results = {
                    "success": True,
                    "analysis": final_response,
                    "results": final_results,
                    "visualizations": final_plots,
                    "downloaded_plots": [{"filename": f["filename"], "local_path": f["local_path"], "size_bytes": f["size_bytes"]} for f in downloaded_files],
                    "data_summary": {
                        "datasets_retrieved": len(self.current_data),
                        "results_keys": list(final_results.keys()) if final_results else [],
                        "plots_generated": len(final_plots),
                        "files_downloaded": len(downloaded_files)
                    },
                    "execution_log": state.execution_log
                }
            
            print(f"🔍 [DEBUG] format_results - Formatted results success: {state.formatted_results.get('success')}")
            self.log_execution_step(state, "format_results", "completed")
            
        except Exception as e:
            print(f"🔍 [DEBUG] format_results - Exception: {str(e)}")
            state.formatted_results = {
                "success": False,
                "error": f"Error formatting results: {str(e)}",
                "execution_log": state.execution_log
            }
        
        return state
    
    async def handle_error(self, state: PharmacyAnalyzeWorkflowState) -> PharmacyAnalyzeWorkflowState:
        """Handle errors and provide meaningful feedback"""
        try:
            self.log_execution_step(state, "handle_error", "started")
            
            error_context = state.error_context or {}
            
            state.formatted_results = {
                "success": False,
                "error": error_context.get("error", "Unknown error occurred"),
                "step_failed": error_context.get("step", "unknown"),
                "analysis_type": state.analysis_type,
                "execution_log": state.execution_log,
                "suggestions": self._get_error_suggestions(error_context)
            }
            
            self.log_execution_step(state, "handle_error", "completed")
            
        except Exception as e:
            state.formatted_results = {
                "success": False,
                "error": f"Critical error in error handling: {str(e)}",
                "execution_log": state.execution_log
            }
        
        return state
    
    def _get_error_suggestions(self, error_context: Dict) -> List[str]:
        """Generate helpful suggestions based on error context"""
        suggestions = []
        
        error_step = error_context.get("step", "")
        error_msg = error_context.get("error", "").lower()
        
        if "analyze_request" in error_step:
            suggestions.extend([
                "Check if the pharmacy request is clear and specific",
                "Verify user ID is valid",
                "Ensure proper analysis type classification"
            ])
        elif "agent_code_analysis" in error_step:
            suggestions.extend([
                "Verify LLM model configuration",
                "Check tool binding and availability",
                "Review system prompt formatting"
            ])
        elif "agent_code_analysis" in error_step:
            suggestions.extend([
                "Check tool implementation for errors",
                "Verify database connectivity for pharmacy data retrieval",
                "Check local Python environment and permissions"
            ])
        
        if "timeout" in error_msg:
            suggestions.append("Consider breaking down complex pharmacy requests into smaller parts")
        elif "connection" in error_msg:
            suggestions.append("Check network connectivity and service availability")
        elif "permission" in error_msg:
            suggestions.append("Verify API keys and service permissions")
        
        return suggestions if suggestions else ["Review error logs for more details"]
    
    def log_execution_step(self, state: PharmacyAnalyzeWorkflowState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection using settings"""
        return psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )
    
    async def run(self, request: str, user_id: int) -> Dict[str, Any]:
        """
        Execute the pharmacy code interpreter workflow with agent-driven data retrieval and analysis.
        
        Args:
            request: The user's pharmacy analysis request
            user_id: User ID for data retrieval
            
        Returns:
            Dict containing the analysis results
        """
        try:
            # Initialize state without pre-retrieved data - agent will retrieve as needed
            initial_state = PharmacyAnalyzeWorkflowState(
                original_request=request,
                user_id=user_id,
                raw_data={},  # Empty - agent will populate using retrieve_pharmacy_data tool
                data_summary={},
                analysis_type="",
                analysis_plan={}
            )
            
            # Execute workflow with agent and tools and LangSmith tracing
            result = await self.workflow.ainvoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": f"pharmacy-code-interpreter-{user_id}",
                        "recursion_limit": 35
                    },
                    "callbacks": [LangChainTracer()]
                }
            )
            
            # Extract final results
            print(f"🔍 [DEBUG] run - Result type: {type(result)}")
            print(f"🔍 [DEBUG] run - Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            
            # LangGraph returns final state as dict, not object
            if isinstance(result, dict) and 'formatted_results' in result and result['formatted_results']:
                print(f"🔍 [DEBUG] run - Found formatted_results: {result['formatted_results']}")
                return result['formatted_results']
            else:
                print(f"🔍 [DEBUG] run - No formatted_results found, returning error")
                return {
                    "success": False,
                    "error": "No results generated by agent",
                    "execution_log": result.get('execution_log', []) if isinstance(result, dict) else []
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "technical"
            }

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_pharmacy_code_interpreter():
        interpreter = PharmacyAnalyzeWorkflow()
        
        # Test requests
        test_requests = [
            "Analyze my pharmacy data for protein intake and recommend me the new receipes to meet my protein intake of 150g daily"
        ]
        
        for request in test_requests:
            print(f"\n--- Testing: {request} ---")
            try:
                result = await interpreter.run(request, user_id=1)
                print(f"Analysis Type: {result.get('analysis_type', 'Unknown')}")
                print(f"Success: {result.get('success', 'Unknown')}")
                if result.get('error'):
                    print(f"Error: {result.get('error')}")
                else:
                    print(f"Results keys: {list(result.get('results', {}).keys())}")
                    print(f"Has visualization: {bool(result.get('visualizations'))}")
                    print(f"Has interpretation: {bool(result.get('interpretation'))}")
            except Exception as e:
                print(f"Test failed: {str(e)}")
    
    # Uncomment to run tests
    # asyncio.run(test_pharmacy_code_interpreter()) 