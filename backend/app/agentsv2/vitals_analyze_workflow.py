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
from app.utils.timezone import now_local, isoformat_now
from configurations.vitals_config import VITALS_TABLES, PRIMARY_VITALS_TABLE
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
from app.agentsv2.tools.web_search_tool import web_search_tool

@dataclass
class VitalsAnalyzeWorkflowState:
    """State management for the vitals analyze workflow"""
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
    saved_plots: List[Dict[str, Any]] = field(default_factory=list)  # Saved plot metadata (S3 URIs)
    
    # Response formatting
    formatted_results: Dict[str, Any] = field(default_factory=dict)
    
    # Error handling
    has_error: bool = False
    error_context: Optional[Dict] = None
    
    # Execution log
    execution_log: List[Dict] = field(default_factory=list)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)

class VitalsAnalyzeWorkflow:
    """
    LangGraph-based analyze workflow for vitals data analysis.
    
    Thread-safe and designed for shared instance usage.
    All state is managed through VitalsAnalyzeWorkflowState objects passed to methods.
    """
    
    def __init__(self, vitals_agent_instance=None):
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        
        self.llm = ChatOpenAI(model=settings.DEFAULT_AI_MODEL)
        
        # Store reference to the parent vitals agent for method reuse
        self.vitals_agent = vitals_agent_instance
        
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
        
        # Use the web search tool for external information
        web_search = web_search_tool
        
        @tool
        async def retrieve_vitals_data(request: str) -> str:
            """
            Retrieve vitals data based on a natural language request.
            
            The agent can use this tool to:
            - Get relevant vitals data for analysis
            - Verify retrieved data matches the request
            - Query additional data if needed
            - Refine queries based on analysis requirements
            
            Args:
                request: Natural language description of what vitals data is needed
                
            Returns:
                JSON string of retrieved vitals data or error message
            """
            try:
                if not self.vitals_agent:
                    return "Error: Vitals agent not available for data retrieval"
                
                # Create a temporary vitals state for the request
                from app.agentsv2.vitals_agent import VitalsAgentState
                vitals_state = VitalsAgentState(
                    original_prompt=request,
                    user_id=self.current_user_id
                )
                
                # Use the vitals agent's retrieval method (now properly awaited)
                result_state = await self.vitals_agent.retrieve_vitals_data(vitals_state)
                
                if result_state.has_error:
                    return f"Data retrieval failed: {result_state.error_context.get('message', 'Unknown error')}"
                
                # Extract raw data from the agent's execution
                # The vitals agent uses tools that return raw JSON data, but the final output mixes it with commentary
                # Let's try to extract just the JSON data part
                query_results = result_state.query_results
                if query_results and "output" in query_results:
                    output_content = query_results["output"]
                    
                    # Try to extract JSON arrays in the output (vitals data is typically returned as JSON arrays)
                    json_pattern = r'\[\s*\{.*?\}\s*\]'
                    json_matches = re.findall(json_pattern, output_content, re.DOTALL)
                    
                    if json_matches:
                        # Use the last/largest JSON match (most likely to be the complete data)
                        json_data = json_matches[-1]
                        try:
                            parsed_data = json.loads(json_data)
                            if isinstance(parsed_data, list) and parsed_data:
                                self.retrieved_data_json = json_data
                                return f"Retrieved {len(parsed_data)} vitals records.\n\nComplete vitals data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it - it will be available as 'vitals_data' DataFrame."
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
                                return f"Retrieved {len(parsed_data)} vitals records (reconstructed).\n\nComplete vitals data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it."
                        except:
                            pass
                    
                    # If we can't extract structured data, return the full raw response
                    return f"Data retrieved but could not extract structured format. Full raw response:\n{output_content}\n\nNote: The vitals agent returned commentary instead of raw data. You may need to refine the request."
                
                else:
                    return "No data found for the request"
                    
            except Exception as e:
                return f"Error retrieving vitals data: {str(e)}"
        
        @tool
        async def execute_python_code(code: str) -> str:
            """
            Execute Python code locally with safe environment.
            
            This tool allows the agent to:
            - Run vitals data analysis and visualization code
            - Access pandas, numpy, matplotlib, seaborn
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
                    """Save matplotlib plot to local folder and upload to S3 when enabled"""
                    try:
                        if plt_figure is None:
                            plt_figure = plt.gcf()
                        
                        # Generate filename if not provided
                        if filename is None:
                            timestamp = now_local().strftime("%Y%m%d_%H%M%S")
                            filename = f"vitals_plot_{timestamp}.png"
                        elif not filename.endswith('.png'):
                            filename = filename + ".png"
                        
                        # Save to local folder
                        local_path = os.path.join(plots_dir, filename)
                        plt_figure.savefig(local_path, format=format, dpi=dpi, bbox_inches='tight')
                        
                        # Also save to base64 buffer for response
                        buffer = io.BytesIO()
                        plt_figure.savefig(buffer, format=format, dpi=dpi, bbox_inches='tight')
                        buffer.seek(0)
                        
                        plot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        plot_buffers.append(plot_base64)
                        
                        # Upload to S3 if enabled (single saved path)
                        saved_path = local_path
                        try:
                            from app.core.config import settings as _settings
                            if bool(getattr(_settings, 'USE_S3_UPLOADS', False)):
                                from app.services.s3_service import upload_bytes_and_get_uri
                                s3_prefix = getattr(_settings, 'UPLOADS_S3_PREFIX', 'uploads') or 'uploads'
                                s3_key = f"{s3_prefix.rstrip('/')}/plots/{filename}"
                                s3_uri = upload_bytes_and_get_uri(
                                    bucket=_settings.AWS_S3_BUCKET,
                                    key=s3_key,
                                    data=buffer.getvalue(),
                                    content_type='image/png'
                                )
                                print(f"  [save_plot] S3 upload: {s3_uri}")
                                saved_path = s3_uri
                        except Exception as upload_exc:
                            # Non-fatal: keep local save and proceed
                            print(f"⚠️  [save_plot] S3 upload failed, using local file only: {str(upload_exc)}")
                            saved_path = local_path
                        
                        buffer.close()
                        plt.close(plt_figure)
                        
                        # Track saved files
                        saved_plot_files.append({
                            "filename": filename,
                            "local_path": saved_path,
                            "base64": plot_base64,
                            "size_bytes": os.path.getsize(local_path)
                        })
                        
                        location_msg = saved_path
                        return f"Plot saved as {filename} to {location_msg}! Total plots: {len(plot_buffers)}"
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
                    'vitals_data': pd.DataFrame(self.current_data) if self.current_data else pd.DataFrame()
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
        
        return [web_search, retrieve_vitals_data, execute_python_code]
    
    def get_tools(self):
        """Get the list of available tools."""
        return self.tools
    
    def _build_workflow(self):
        """Build the LangGraph workflow for vitals code interpretation"""
        # Set up LangSmith tracing
        tracer = LangChainTracer()
        callback_manager = CallbackManager([tracer])
        
        workflow = StateGraph(VitalsAnalyzeWorkflowState)
        
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
    
    def check_analysis_success(self, state: VitalsAnalyzeWorkflowState) -> str:
        return "error" if state.has_error else "continue"
    
    async def analyze_request(self, state: VitalsAnalyzeWorkflowState) -> VitalsAnalyzeWorkflowState:
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
            You are a vitals data analysis and planning agent. Your role is to interpret user requests about health monitoring, vital signs tracking, fitness goals, and health management, and break them down into a structured plan of actions that a downstream execution agent (e.g., Python code executor, web browser,) can perform.

            The user may request anything from simple vital signs tracking to complex health goal analysis using external data sources. Your job is to:

                Understand the intent and scope of the user's health-related query.

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
                    "description": "Natural language description of what type of analysis needs to be done",
                    "tool": "python|browser|api|manual_review",
                    "inputs_required": ["list", "of", "data", "fields", "or", "parameters"],
                    "expected_output": "Describe the format and insight expected",
                    "notes": "Any contextual notes, assumptions, or warnings"
                    }}
                ],
                "data_requirements": {{
                    "vitals": ["vital sign categories", "measurement logs", "dates", "device types", "etc."],
                    "external_sources": ["yes|no|optional", "e.g., YouTube, health research, exercise DB"],
                    "health_targets": "yes|no|optional"
                }},
                "time_period": "recent|7_days|30_days|6_months|1_year|user_specified",
                "granularity": "daily|weekly|per_measurement|as_suitable",
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
                        "description": f"Analyze vitals data: {state.original_request}",
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
                    "description": f"Perform statistical analysis of vitals data: {state.original_request}",
                    "methodology": "Descriptive statistics and visualization",
                    "visualizations": ["bar_chart", "summary_table"],
                    "metrics": ["mean", "median", "range", "vital_sign_distribution"]
                }
                state.data_requirements = ["vitals_data"]
            
            self.log_execution_step(state, "analyze_request", "completed")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {"step": "analyze_request", "error": str(e)}
            self.log_execution_step(state, "analyze_request", "failed", {"error": str(e)})
        
        return state
    
    async def agent_code_analysis(self, state: VitalsAnalyzeWorkflowState) -> VitalsAnalyzeWorkflowState:
        """Agent-driven code analysis with iterative tool usage"""
        try:
            self.log_execution_step(state, "agent_code_analysis", "started")
            
            # Store user_id for data retrieval tool
            self.current_user_id = state.user_id
            
            # Initialize data containers for the agent's work
            self.current_data = {}
            self.current_results = {}
            self.current_plots = []
            current_date = now_local().strftime('%Y_%m_%d')
            # If this is the first time (no messages), set up the conversation
            if not state.messages:
                system_prompt = f"""
                You are a Python data analysis expert specializing in health monitoring and vitals data. Your goal is to perform the requested analysis by executing a detailed multi-step plan that has been created specifically for this request.

                Analysis Request: {state.original_request}
                Analysis Type: {state.analysis_type}
                Analysis Plan: {json.dumps(state.analysis_plan, indent=2)}
                Data Requirements: {json.dumps(state.data_requirements, indent=2) if state.data_requirements else 'Not specified'}
                User ID: {state.user_id}
                
                🎯 REQUEST ANALYSIS: This request asks for "{state.original_request}"
                - If this mentions "exercise", "workout", "YouTube", or "videos": USE web_search tool!
                - If this asks for health recommendations: USE web_search for exercise and wellness ideas!
                - If this asks for external information: USE web_search immediately!

                DETAILED EXECUTION PLAN:
                The analysis request has been broken down into a structured plan. You MUST follow this plan step by step to ensure comprehensive analysis:

                Goals to Achieve: {json.dumps(state.analysis_plan.get('goals', [state.original_request]), indent=2)}
                
                Tasks to Execute:
                {json.dumps(state.analysis_plan.get('tasks', []), indent=2)}
                
                Data Requirements:
                - Vitals Data: {json.dumps(state.data_requirements.get('vitals', []), indent=2) if isinstance(state.data_requirements, dict) else state.data_requirements}
                - External Sources: {state.data_requirements.get('external_sources', 'Not specified') if isinstance(state.data_requirements, dict) else 'Not specified'}
                
                Time Period: {state.analysis_plan.get('time_period', 'Not specified')}
                Granularity: {state.analysis_plan.get('granularity', 'Not specified')}

                You have access to three tools:
                1. web_search: Search the web for ANY external information including:
                   - Exercise recommendations and workout videos (YouTube, fitness sites)
                   - Health research and medical studies
                   - Cardiovascular health guidelines and recommendations
                   - Fitness programs and exercise routines
                   - Blood pressure management techniques
                   - Weight loss and health improvement plans
                   - while using web_search, use your knowledge to ask a broader question like "cardiovascular health improvement exercises for blood pressure management"
                   
                   🎯 CRITICAL: The web_search tool now returns RICH CONTENT DATA including:
                   - Actual exercise routines with step-by-step instructions
                   - Workout plans with specific exercises and durations
                   - Health improvement tips and recommendations
                   - Structured content ready for health planning
                   
                   ⚠️ DO NOT just list URLs! Use the extracted content to CREATE CUSTOMIZED HEALTH PLANS:
                   - Extract specific exercises from the 'exercises' field
                   - Use 'workout_plans' to create structured routines
                   - Use 'instructions' to provide detailed guidance
                   - Use 'health_tips' data to structure daily/weekly plans
                   - Use 'benefits' to show health improvement potential
                   - Combine multiple sources to create comprehensive plans
                   
                   USE THIS TOOL whenever you need external exercises, YouTube videos, or health research!
                   
                2. retrieve_vitals_data: Get vitals data based on natural language requests. Be very specific of the time granularity while retrieving the data and the aggregation of the data.
                3. execute_python_code: Execute Python code for analysis

                EXECUTION STRATEGY:
                Follow the detailed plan above and execute each task systematically:
                
                1. Review the Goals and Tasks: Understand what specific outcomes are expected
                2. ALWAYS use web_search when the user asks for:
                   - Exercise recommendations or workout ideas
                   - YouTube videos or fitness tutorials
                   - External research or studies
                   - Health improvement plans or wellness ideas
                   - Any information not in the user's personal data
                3. Use retrieve_vitals_data to get the specific data requirements identified in the plan
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
                1. IMMEDIATELY start by using retrieve_vitals_data tool to get user's health data
                2. If user asks for exercises, YouTube videos, or external research: IMMEDIATELY use web_search tool
                3. Use execute_python_code tool to analyze the retrieved data
                4. DO NOT request additional information from the user - work with available data
                5. If initial data retrieval is insufficient, try different search terms with the tools
                
                🔍 WEB SEARCH TRIGGERS - Use web_search tool when user mentions:
                - "exercise" or "workout recommendations"
                - "YouTube" or "videos" or "tutorials"
                - "browsing" or "internet" or "online"
                - "research" or "studies"
                - "health improvement" or "wellness suggestions"
                
                🏃 HEALTH PLANNING REQUIREMENTS - When creating exercise recommendations:
                1. EXTRACT ACTUAL CONTENT from web_search results, don't just list URLs
                2. CREATE STRUCTURED HEALTH PLANS using the rich data returned:
                   - Cardiovascular: [specific exercises with instructions & duration]
                   - Strength Training: [specific exercises with instructions & duration]  
                   - Flexibility: [specific exercises with instructions & duration]
                   - Daily Activities: [specific recommendations with health benefits]
                3. PROVIDE DETAILED EXERCISE PLANS including:
                   - Exercise lists with specific instructions
                   - Step-by-step workout routines
                   - Health benefits and target improvements
                   - Duration and frequency recommendations
                4. CREATE WORKOUT SCHEDULES from extracted exercise data
                5. CUSTOMIZE based on user's current vitals and health goals
                6. COMBINE multiple web sources to create comprehensive plans
                
                📊 EXAMPLE HEALTH PLAN OUTPUT FORMAT:
                ```
                ## Customized Cardiovascular Health Plan (Based on Your Blood Pressure Data)
                
                ### Daily Cardio Routine (30-45 minutes)
                **Morning Walk/Jog Program**
                - Exercise: Brisk walking progressing to light jogging
                - Instructions: Start with 15 min walk, increase by 5 min weekly
                - Target: Improve cardiovascular health and blood pressure
                - Frequency: 5 days per week
                
                ### Strength Training (3x per week)
                **Upper Body Routine**
                - Exercises: [extracted from web_search results]
                - Instructions: [detailed steps from web_search results]
                - Benefits: Muscle strengthening and metabolic improvement
                
                ### Flexibility & Recovery (Daily)
                **Yoga and Stretching**
                - Routine: [extracted from web_search]
                - Instructions: [extracted from web_search]
                
                ### Weekly Schedule
                - [organized workout calendar from extracted data]
                
                ### Health Monitoring Tips
                - [extracted from web_search tips sections]
                ```
                
                Tool Usage Rules:
                - retrieve_vitals_data: Get ALL available vitals data for the user - be broad in your requests
                - web_search: MUST BE USED for external information including:
                  * Exercise searches: "cardiovascular exercises for blood pressure improvement"
                  * YouTube videos: "YouTube blood pressure lowering exercises"
                  * Research: "hypertension exercise studies"
                  * Health plans: "weight loss exercise routines"
                  
                  ⚠️ CRITICAL: After web_search, ALWAYS extract and use the rich content fields:
                  * result['exercises'] - actual exercise content
                  * result['workout_plans'] - structured workout routines
                  * result['instructions'] - exercise steps
                  * result['health_tips'] - wellness recommendations
                  * result['benefits'] - health improvement information
                  * result['schedules'] - workout timing and frequency
                  
                - execute_python_code: Perform analysis, calculations, and create visualizations
                - Store your final results in a 'results' dictionary when using execute_python_code
                - CRITICAL: To save plots, you MUST use save_plot() function, NOT plt.savefig()
                - Use save_plot('filename') after creating each visualization
                
                WORKFLOW ENFORCEMENT:
                - Start immediately with tool usage - no explanations or requests for more info
                - Work with whatever data is available from the tools
                - If tools return empty results, acknowledge this and provide general recommendations
                - Complete the full analysis pipeline using available tools before responding to user

                Guidelines for retrieving vitals data:
                - Use the retrieve_vitals_data tool to get relevant data for the analysis
                - Get comprehensive vitals data in order to perform the analysis. Don't restrict to only few vital signs, the tool is an agent so give wide request to get all the data. Ask the agent to give you in JSON format with no commentary and not reduce the data. Get all the data in the JSON format.
                - Example: "Get me all my blood pressure data" or "Get me all my vital signs for the last month"
                - Use synonyms of the vital sign names and also short forms and long forms of the measurement names.
                - Try to get all the data in the first call to retrieve_vitals_data tool instead of batching the requests.
                - If the data is not sufficient, use the retrieve_vitals_data tool again with a more specific request.
                - If the data is still not sufficient, use the retrieve_vitals_data tool again with a more specific request.

                PLOT SAVING EXAMPLE:
                ```python
                plt.figure(figsize=(12, 6))
                # ... create your plot ...
                plt.title('My Blood Pressure Trend')
                
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
                current_date = now_local().strftime('%Y_%m_%d')
                save_plot(f'blood_pressure_trend_chart_{current_date}')  # ← Use this, NOT plt.savefig()
                plt.close()
                ```
                
                ADDITIONAL DATE FORMATTING EXAMPLES:
                ```python
                # For daily vitals data over weeks/months:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                plt.xticks(rotation=45)
                
                # For monthly vitals data over years:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                plt.xticks(rotation=45)
                
                # For automatic date formatting (recommended):
                plt.gcf().autofmt_xdate()  # Automatically format x-axis dates
                ```

                Available libraries in code execution: pandas (pd), numpy (np), matplotlib.pyplot (plt), seaborn (sns)

                🚨 FINAL CRITICAL INSTRUCTION - HEALTH PLAN CREATION:
                When providing exercise recommendations, you MUST:
                1. NEVER just list URLs like "1. [Exercise Plan](URL) - Description"
                2. ALWAYS extract and present actual content from web_search results
                3. CREATE detailed health plans with specific exercises, instructions, and schedules
                4. USE the rich content data (exercises, workout_plans, instructions, health_tips) returned by web_search
                5. ORGANIZE content into cardio, strength, flexibility with health benefits
                6. PROVIDE workout schedules and health monitoring tips from extracted content
                
                ❌ WRONG APPROACH:
                "Here are some exercise recommendations:
                1. [Cardio Plan](url) - Description
                2. [Strength Training](url) - Description"
                
                ✅ CORRECT APPROACH:
                "Based on the fitness content I found, here's your customized plan:
                
                ## Cardiovascular Health Program (Based on Your BP Data)
                **Daily Walking Program**
                - Week 1-2: 20 minutes brisk walking
                - Week 3-4: 25 minutes with 2-minute jog intervals  
                - Week 5+: 30 minutes alternating walk/jog
                Instructions: [detailed steps from web content]
                
                ## Strength Training (3x per week)
                **Upper Body Circuit**
                - [specific exercises with reps from web content]
                - [detailed instructions from web content]"

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
            
            # If we have saved plots, persist them in state (single source of truth for visuals)
            if getattr(self, 'downloaded_plot_files', None):
                state.saved_plots = list(self.downloaded_plot_files)
            
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
    
    async def format_results(self, state: VitalsAnalyzeWorkflowState) -> VitalsAnalyzeWorkflowState:
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
                # After ReAct agent execution, get results and build visualizations from downloaded files
                final_results = self._convert_to_json_serializable(self.current_results)
                direct_visualizations = []
                for p in state.saved_plots or []:
                    if isinstance(p, dict):
                        s3_uri = p.get("local_path") or p.get("s3_uri") or p.get("file_path")
                        filename = p.get("filename", "")
                        title = filename or "Analysis Chart"
                        direct_visualizations.append({
                            "id": f"viz_{hash(filename) & 0xffff:04x}",
                            "type": "chart",
                            "title": title,
                            "description": p.get("description", "Generated visualization"),
                            "filename": filename,
                            "s3_uri": s3_uri,
                            "plot_path": s3_uri,
                            "file_path": s3_uri,
                        })
                
                # Check if we have any results from the analysis
                final_response = "Vitals analysis completed successfully."
                if final_results or direct_visualizations or state.saved_plots:
                    final_response = "Vitals analysis completed with data processing and visualization generation."
                
                state.formatted_results = {
                    "success": True,
                    "analysis": final_response,
                    "results": final_results,
                    "visualizations": direct_visualizations,
                    "downloaded_plots": [{"filename": f["filename"], "local_path": f["local_path"], "size_bytes": f["size_bytes"]} for f in state.saved_plots or []],
                    "data_summary": {
                        "datasets_retrieved": len(self.current_data),
                        "results_keys": list(final_results.keys()) if final_results else [],
                        "plots_generated": len(direct_visualizations),
                        "files_downloaded": len(state.saved_plots or [])
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
    
    async def handle_error(self, state: VitalsAnalyzeWorkflowState) -> VitalsAnalyzeWorkflowState:
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
                "Check if the vitals request is clear and specific",
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
                "Verify database connectivity for vitals data retrieval",
                "Check local Python environment and permissions"
            ])
        
        if "timeout" in error_msg:
            suggestions.append("Consider breaking down complex vitals requests into smaller parts")
        elif "connection" in error_msg:
            suggestions.append("Check network connectivity and service availability")
        elif "permission" in error_msg:
            suggestions.append("Verify API keys and service permissions")
        
        return suggestions if suggestions else ["Review error logs for more details"]
    
    def log_execution_step(self, state: VitalsAnalyzeWorkflowState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": isoformat_now(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection using centralized utility (deprecated direct usage)."""
        from app.core.database_utils import get_raw_db_connection
        return get_raw_db_connection()
    
    async def run(self, request: str, user_id: int) -> Dict[str, Any]:
        """
        Execute the vitals code interpreter workflow with agent-driven data retrieval and analysis.
        
        Args:
            request: The user's vitals analysis request
            user_id: User ID for data retrieval
            
        Returns:
            Dict containing the analysis results
        """
        try:
            # Initialize state without pre-retrieved data - agent will retrieve as needed
            initial_state = VitalsAnalyzeWorkflowState(
                original_request=request,
                user_id=user_id,
                raw_data={},  # Empty - agent will populate using retrieve_vitals_data tool
                data_summary={},
                analysis_type="",
                analysis_plan={}
            )
            
            # Execute workflow with agent and tools and LangSmith tracing
            result = await self.workflow.ainvoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": f"vitals-code-interpreter-{user_id}",
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
    
    async def test_vitals_code_interpreter():
        interpreter = VitalsAnalyzeWorkflow()
        
        # Test requests
        test_requests = [
            "Analyze my vitals data for heart rate trends and recommend me exercise plans to improve my sleep quality"
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
    # asyncio.run(test_vitals_code_interpreter()) 