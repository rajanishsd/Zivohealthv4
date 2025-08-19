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
from configurations.lab_config import LAB_TABLES, PRIMARY_LAB_TABLE, ALL_LAB_TABLES, AGGREGATION_TABLES
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

from app.agentsv2.response_utils import format_agent_response


@dataclass
class LabAnalyzeWorkflowState:
    """State management for the lab analyze workflow"""
    # Input data
    original_request: str = ""
    user_id: Optional[int] = None
    
    # Analysis planning
    analysis_type: str = ""
    analysis_plan: Dict[str, Any] = field(default_factory=dict)
    data_requirements: List[str] = field(default_factory=list)
    
    # Data context
    raw_data: Dict[str, pd.DataFrame] = field(default_factory=dict)
    
    # Code generation and execution
    generated_code: str = ""
    execution_results: Dict[str, Any] = field(default_factory=dict)
    execution_output: str = ""
    execution_error: Optional[str] = None
    
    # Visualization
    plots: List[str] = field(default_factory=list)  # Base64 encoded images
    
    # Response formatting
    formatted_results: Dict[str, Any] = field(default_factory=dict)
    agent_response: str = ""  # Final GPT response content
    
    # Error handling
    has_error: bool = False
    error_context: Optional[Dict] = None
    
    # Execution log
    execution_log: List[Dict] = field(default_factory=list)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)

class LabAnalyzeWorkflow:
    """
    LangGraph-based analyze workflow for lab data analysis.
    
    Thread-safe and designed for shared instance usage.
    All state is managed through LabAnalyzeWorkflowState objects passed to methods.
    """
    
    def __init__(self, lab_agent_instance=None):
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        
        self.llm = ChatOpenAI(model=settings.LAB_AGENT)
        
        # Store reference to the parent lab agent for method reuse
        self.lab_agent = lab_agent_instance
        
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
        
        @tool
        def web_search(query: str) -> str:
            """
            Search the web for information using DuckDuckGo.
            
            ⚠️ MANDATORY REASONING REQUIREMENT ⚠️
            BEFORE CALLING this tool, you MUST include your reasoning explaining:
            1. Why you are selecting this specific tool
            2. What information you hope to get from this tool
            3. How this tool call fits into your overall strategy
            4. What you will do with the results
            5. What specific medical information you need to find
            6. How this search will help with the analysis
            
            This tool allows the agent to:
            - Search for medical information, lab test references, and research
            - Find current medical guidelines and recommendations
            - Look up lab test normal ranges and interpretations
            - Research medical studies and evidence
            
            Args:
                query: Search query string
                
            Returns:
                Search results as formatted text
            """
            try:
                from langchain_community.tools import DuckDuckGoSearchRun
                search = DuckDuckGoSearchRun()
                results = search.run(query)
                return f"Search results for '{query}':\n{results}"
            except Exception as e:
                return f"Search failed: {str(e)}"
        
        @tool
        async def retrieve_lab_data(request: str) -> str:
            """
            Retrieve lab data based on a natural language request.
            
            ⚠️ MANDATORY REASONING REQUIREMENT ⚠️
            BEFORE CALLING this tool, you MUST include your reasoning explaining:
            1. Why you are selecting this specific tool
            2. What information you hope to get from this tool
            3. How this tool call fits into your overall strategy
            4. What you will do with the results
            5. What specific lab data you need for the analysis
            6. How this data will contribute to your analysis goals
            
            The agent can use this tool to:
            - Get relevant lab data for analysis
            - Verify retrieved data matches the request
            - Query additional data if needed
            - Refine queries based on analysis requirements
            
            Args:
                request: Natural language description of what data is needed
                
            Returns:
                JSON string of retrieved lab data or error message
            """
            try:
                if not self.lab_agent:
                    return "Error: Lab agent not available for data retrieval"
                
                # Create a temporary lab state for the request
                from app.agentsv2.lab_agent import LabAgentState
                lab_state = LabAgentState(
                    original_prompt=request,
                    user_id=self.current_user_id
                )
                
                # Use the lab agent's retrieval method (now properly awaited)
                result_state = await self.lab_agent.retrieve_lab_data(lab_state)
                
                if result_state.has_error:
                    return f"Data retrieval failed: {result_state.error_context.get('message', 'Unknown error')}"
                
                # Extract raw data from the agent's execution
                # The lab agent uses tools that return raw JSON data, but the final output mixes it with commentary
                # Let's try to extract just the JSON data part
                query_results = result_state.query_results
                if query_results and "output" in query_results:
                    output_content = query_results["output"]
                    
                    # Try to extract JSON arrays in the output (lab data is typically returned as JSON arrays)
                    json_pattern = r'\[\s*\{.*?\}\s*\]'
                    json_matches = re.findall(json_pattern, output_content, re.DOTALL)
                    
                    if json_matches:
                        # Use the last/largest JSON match (most likely to be the complete data)
                        json_data = json_matches[-1]
                        try:
                            parsed_data = json.loads(json_data)
                            if isinstance(parsed_data, list) and parsed_data:
                                self.retrieved_data_json = json_data
                                self.current_data = parsed_data  # Fix: Set current_data for execute_python_code tool
                                return f"Retrieved {len(parsed_data)} lab records.\n\nComplete lab data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it - it will be available as 'lab_data' DataFrame."
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
                                self.current_data = parsed_data  # Fix: Set current_data for execute_python_code tool
                                return f"Retrieved {len(parsed_data)} lab records (reconstructed).\n\nComplete lab data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it."
                        except:
                            pass
                    
                    # If we can't extract structured data, return the full raw response
                    return f"Data retrieved but could not extract structured format. Full raw response:\n{output_content}\n\nNote: The lab agent returned commentary instead of raw data. You may need to refine the request."
                
                else:
                    return "No data found for the request"
                    
            except Exception as e:
                return f"Error retrieving lab data: {str(e)}"
        
        @tool
        async def execute_python_code(code: str) -> str:
            """
            Execute Python code locally with safe environment.
            
            ⚠️ MANDATORY REASONING REQUIREMENT ⚠️
            BEFORE CALLING this tool, you MUST include your reasoning explaining:
            1. Why you are selecting this specific tool
            2. What information you hope to get from this tool
            3. How this tool call fits into your overall strategy
            4. What you will do with the results
            5. What specific analysis or visualization you're implementing
            6. How this code execution will help answer the user's request
            
            This tool allows the agent to:
            - Run data analysis and visualization code, Fix any python errors and retry until you achieve comprehensive results
            - Access pandas, numpy, matplotlib, seaborn
            - Save plots directly to data/plots/ folder using save_plot()
            - Handle errors gracefully, Fix any python errors and retry until you achieve comprehensive results
            
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
                            filename = f"plot_{timestamp}.png"
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
                    'lab_data': pd.DataFrame(self.current_data) if self.current_data else pd.DataFrame()
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
        
        return [web_search, retrieve_lab_data, execute_python_code]
    


    
    def get_tools(self):
        """Get the list of available tools."""
        return self.tools
    
    def _build_workflow(self):
        """Build the LangGraph workflow for code interpretation"""
        # Set up LangSmith tracing
        tracer = LangChainTracer()
        callback_manager = CallbackManager([tracer])
        
        workflow = StateGraph(LabAnalyzeWorkflowState)
        
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
    

    
    def check_analysis_success(self, state: LabAnalyzeWorkflowState) -> str:
        return "error" if state.has_error else "continue"
    
    async def analyze_request(self, state: LabAnalyzeWorkflowState) -> LabAnalyzeWorkflowState:
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
            You are a medical data analysis expert. Analyze the following user request regarding lab and health data. Your job is to:

            User Request: {}
            User ID: {}

            Classify the type of analysis requested.
            Create a detailed analysis plan, including interpretive guidance.
            Identify all data requirements (including extensive lab data tests, reference ranges, demographics, etc.)
            Specify the recommended time period and the desired granularity for analysis.
            Assess the complexity of the analysis.
            List any missing information needed to deliver the requested analysis.
            Ensure that privacy and confidentiality are maintained.
            Return a single JSON object in the following structure:

           

            Classify the analysis type and create a detailed plan. Return a JSON object with:
            {{
                "analysis_type": "trend_analysis|correlation_analysis|distribution_analysis|comparative_analysis|risk_assessment|statistical_summary|custom",
                "analysis_plan": {{
                    "description": "Brief description of what analysis will be performed",
                    "methodology": "Statistical or analytical approach to be used",
                    "visualizations": ["list", "of", "chart", "types", "needed"],
                    "metrics": ["list", "of", "calculations", "or", "statistics"],
                    "interpretation_guidance": "Advice for user on how to interpret and act on results"
                }},
                "data_requirements": {{
                    "labs": ["test categories", "loinc_code", "units", "dates"],
                    "demographics": ["age", "sex", "relevant clinical info if needed (e.g., weight, diagnosis)"],
                    "reference_ranges": "yes|no|optional"
                }},
                "time_period": "recent|30_days|6_months|1_year|all_time|user_specified",
                "granularity": "daily|weekly|monthly|quarterly|as_suitable",
                "complexity": "simple|moderate|complex",
                "missing_information": ["list", "of", "additional", "data", "or", "clarifications", "needed"],
                "privacy": "All data remains confidential and is handled according to best privacy practices."
            }}
            
            If the user request is ambiguous or contains multiple intents, identify and split the analysis into separate subtasks, each with its own plan object. If critical information is missing, explicitly specify what to request from the user next in the "missing_information" field.

            Examples:
            "Show correlation between my glucose and HbA1c over the last year" → correlation_analysis
            "Track my liver function trends" → trend_analysis
            "Compare my cholesterol levels to healthy ranges" → comparative_analysis
            "Show the distribution of my white blood cell counts" → distribution_analysis   
            

            
            Analyze this request and return only the JSON object with the classification and action plan.
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
                    state.analysis_plan = analysis_data.get("analysis_plan", {
                        "description": f"Analyze lab data: {state.original_request}",
                        "methodology": analysis_data.get("methodology", "Standard statistical analysis"),
                        "visualizations": analysis_data.get("visualizations", ["bar_chart", "line_chart"]),
                        "metrics": analysis_data.get("metrics", ["mean", "trend"])
                    })
                    
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
                    "description": f"Perform statistical analysis of lab data: {state.original_request}",
                    "methodology": "Descriptive statistics and visualization",
                    "visualizations": ["bar_chart", "summary_table"],
                    "metrics": ["mean", "median", "range", "status_distribution"]
                }
                state.data_requirements = ["lab_test_results"]
            
            self.log_execution_step(state, "analyze_request", "completed")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {"step": "analyze_request", "error": str(e)}
            self.log_execution_step(state, "analyze_request", "failed", {"error": str(e)})
        
        return state
    
    async def agent_code_analysis(self, state: LabAnalyzeWorkflowState) -> LabAnalyzeWorkflowState:
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
            system_prompt = f"""
            You are a Python data analysis expert specializing in medical lab data. Your goal is to perform the requested analysis by first retrieving relevant data, then analyzing it.

            Analysis Request: {state.original_request}
            Analysis Type: {state.analysis_type}
            Analysis Plan: {json.dumps(state.analysis_plan, indent=2)}
            User ID: {state.user_id}

            You have access to three tools:
            1. web_search: Search the web for medical information, research, and guidelines
            2. retrieve_lab_data: Get lab data based on natural language requests
            3. execute_python_code: Execute Python code for analysis, Fix any python errors and retry until you achieve comprehensive results

            Your workflow should be:
            1. Use web_search if you need external medical information, research, or guidelines
            2. Use retrieve_lab_data to get relevant personal lab data for the analysis
            3. Verify the retrieved data matches your needs
            4. If data is insufficient, retrieve additional data with refined requests
            5. Use execute_python_code to analyze the data iteratively, if execution fails, retry with a different approach dont retrieve the data again.
            6. Create appropriate visualizations
            7. Fix any python errors and retry until you achieve comprehensive results

            Guidelines:
            - Start by retrieving data that matches the user's request. 
            - Check if retrieved data is sufficient for the analysis
            - Query additional data if needed (different time periods, test categories, etc.)
            - Store your final results in a 'results' dictionary when using execute_python_code
            - CRITICAL: To save plots, you MUST use save_plot() function, NOT plt.savefig()
            - Use save_plot('filename') after creating each visualization
            - save_plot() saves files directly to data/plots/ folder
            - Include error handling and provide clear, medical-focused analysis
            - Iterate until you have a complete analysis that answers the user's request
            - IMPORTANT: At the end of your analysis, return your findings in a structured JSON format (see below)

            guidelines for retrieving lab data:
            - Use the retrieve_lab_data tool ONLY ONCE to get all relevant data for the analysis
            - Get exhaustive lab test data in order to perform the analysis. Don't restrict to only few tests, the tool is an agent so give wide request to get all the data. Ask the agent to give you in JSON format with no commentary and not reduce the data. Get all the data in the JSON format.
            - Example: "Get me all my kidney function tests" or "Get me all Liver function tests"
            - use synonyms of the test names and also short forms and long forms of the test names.
            - Make your request comprehensive to get all the data in the first call to retrieve_lab_data tool instead of batching the requests.
            - IMPORTANT: Once you receive data from retrieve_lab_data, proceed to execute_python_code. Do NOT call retrieve_lab_data again.
            - If code execution fails, retry to address the problem reported and try again till you get the results, but do NOT retrieve data again.


            PLOT SAVING EXAMPLE:
            ```python
            plt.figure(figsize=(12, 6))
            # ... create your plot ...
            plt.title('My Chart')
            
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
            current_date = datetime.now().strftime('%Y_%m_%d')
            save_plot(f'my_chart_name_{current_date}')  # ← Use this, NOT plt.savefig()
            plt.close()
            ```
            
            ADDITIONAL DATE FORMATTING EXAMPLES:
            ```python
            # For daily data over weeks/months:
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.xticks(rotation=45)
            
            # For monthly data over years:
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=45)
            
            # For automatic date formatting (recommended):
            plt.gcf().autofmt_xdate()  # Automatically format x-axis dates
            ```

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
                        "plot_path": "saved_plot_path,
                    }}
                ],
                "data_quality": "Assessment of data completeness and reliability",
                "recommendations": ["recommendation 1", "recommendation 2"]
            }}
            ```

            Available libraries in code execution: pandas (pd), numpy (np), matplotlib.pyplot (plt), seaborn (sns)

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
            
            # Get the final GPT message content
            final_message = state.messages[-1] if state.messages else None
            if final_message and hasattr(final_message, 'content'):
                # Use the GPT message content directly
                state.agent_response = final_message.content
                print(f"🔍 [DEBUG] agent_code_analysis - GPT Response: {final_message.content[:200]}...")
            
            self.log_execution_step(state, "agent_code_analysis", "completed")
            
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

    
    async def format_results(self, state: LabAnalyzeWorkflowState) -> LabAnalyzeWorkflowState:
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
                
                # Use the actual GPT agent response - this contains the analyzed results
                final_response = state.agent_response if state.agent_response else "Analysis completed successfully."
                
                # Try to extract structured JSON response from agent response
                structured_analysis = self._extract_json_from_response(final_response)
                
                # The agent already returns structured analysis with visualizations
                state.formatted_results = {
                    "success": True,
                    "task_types": ["lab_analysis"],
                    "results": {
                        "analysis": structured_analysis if structured_analysis else final_response,
                        "original_request": state.original_request
                    },
                    "execution_log": state.execution_log,
                    "message": "Lab analysis completed successfully"
                }
                
                # Extract visualizations from the structured analysis if present
                if structured_analysis and "visualizations_created" in structured_analysis:
                    state.formatted_results["visualizations"] = structured_analysis["visualizations_created"]
                    print(f"🔍 [DEBUG] format_results - Visualizations: {state.formatted_results['visualizations']}")
            
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
    
    async def handle_error(self, state: LabAnalyzeWorkflowState) -> LabAnalyzeWorkflowState:
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
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract structured JSON from agent response"""
        try:
            # Look for JSON blocks in the response (both objects and arrays)
            import re
            json_pattern = r'```json\s*(\{.*?\}|\[.*?\])\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                # Try to parse the last JSON block found
                json_str = matches[-1]
                parsed = json.loads(json_str)
                # If it's an array (like visualizations), wrap it in an object
                if isinstance(parsed, list):
                    return {"visualizations_created": parsed}
                return parsed
            
            # If no JSON blocks found, try to find JSON-like content at the end
            # Look for lines that might contain a JSON object
            lines = response.split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith('{') or stripped.startswith('[')) and not in_json:
                    in_json = True
                    json_lines = [stripped]
                    start_char = stripped[0]
                    end_char = '}' if start_char == '{' else ']'
                elif in_json:
                    json_lines.append(stripped)
                    if stripped.endswith(end_char):
                        # Count brackets to make sure we have a complete structure
                        full_json = '\n'.join(json_lines)
                        open_count = full_json.count('{' if end_char == '}' else '[')
                        close_count = full_json.count(end_char)
                        if close_count >= open_count:
                            break
            
            if json_lines:
                json_str = '\n'.join(json_lines)
                parsed = json.loads(json_str)
                # If it's an array (like visualizations), wrap it in an object
                if isinstance(parsed, list):
                    return {"visualizations_created": parsed}
                return parsed
                
            return None
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"🔍 [DEBUG] Failed to extract JSON from response: {str(e)}")
            return None
    
    def _get_error_suggestions(self, error_context: Dict) -> List[str]:
        """Generate helpful suggestions based on error context"""
        suggestions = []
        
        error_step = error_context.get("step", "")
        error_msg = error_context.get("error", "").lower()
        
        if "analyze_request" in error_step:
            suggestions.extend([
                "Check if the request is clear and specific",
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
                "Verify database connectivity for data retrieval",
                "Check local Python environment and permissions"
            ])
        
        if "timeout" in error_msg:
            suggestions.append("Consider breaking down complex requests into smaller parts")
        elif "connection" in error_msg:
            suggestions.append("Check network connectivity and service availability")
        elif "permission" in error_msg:
            suggestions.append("Verify API keys and service permissions")
        
        return suggestions if suggestions else ["Review error logs for more details"]
    
    def log_execution_step(self, state: LabAnalyzeWorkflowState, step_name: str, status: str, details: Dict = None):
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
        Execute the code interpreter workflow with agent-driven data retrieval and analysis.
        
        Args:
            request: The user's analysis request
            user_id: User ID for data retrieval
            
        Returns:
            Dict containing the analysis results
        """
        try:
            # Initialize state without pre-retrieved data - agent will retrieve as needed
            initial_state = LabAnalyzeWorkflowState(
                original_request=request,
                user_id=user_id,
                raw_data={},  # Empty - agent will populate using retrieve_lab_data tool
                analysis_type="",
                analysis_plan={}
            )
            
            # Execute workflow with agent and tools and LangSmith tracing
            result = await self.workflow.ainvoke(
                initial_state,
                config={
                    "configurable": {"thread_id": f"lab-code-interpreter-{user_id}"},
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
    
    async def test_code_interpreter():
        interpreter = LabAnalyzeWorkflow()
        
        # Test requests
        test_requests = [
            "Analyze my lab data for kidney function and show me the trends in a beautiful line chart"
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
    # asyncio.run(test_code_interpreter()) 