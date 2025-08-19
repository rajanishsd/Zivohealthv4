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
from configurations.nutrition_config import NUTRITION_TABLES, PRIMARY_NUTRITION_TABLE
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
from app.agentsv2.tools.nutrition_tools import nutrition_recipe_search_tool

@dataclass
class NutritionAnalyzeWorkflowState:
    """State management for the nutrition analyze workflow"""
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
    agent_response: str = ""  # Final GPT response content
    
    # Error handling
    has_error: bool = False
    error_context: Optional[Dict] = None
    
    # Execution log
    execution_log: List[Dict] = field(default_factory=list)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)

class NutritionAnalyzeWorkflow:
    """
    LangGraph-based analyze workflow for nutrition data analysis.
    
    Thread-safe and designed for shared instance usage.
    All state is managed through NutritionAnalyzeWorkflowState objects passed to methods.
    """
    
    def __init__(self, nutrition_agent_instance=None):
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        
        self.llm = ChatOpenAI(model=settings.DEFAULT_AI_MODEL)
        
        # Store reference to the parent nutrition agent for method reuse
        self.nutrition_agent = nutrition_agent_instance
        
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
        
        # Use the new nutrition_recipe_search_tool
        recipe_search_tool = nutrition_recipe_search_tool
        
        @tool
        async def retrieve_nutrition_data(request: str) -> str:
            """
            Retrieve nutrition data based on a natural language request.
            
            The agent can use this tool to:
            - Get relevant nutrition data for analysis
            - Verify retrieved data matches the request
            - Query additional data if needed
            - Refine queries based on analysis requirements
            
            Args:
                request: Natural language description of what nutrition data is needed
                
            Returns:
                JSON string of retrieved nutrition data or error message
            """
            try:
                if not self.nutrition_agent:
                    return "Error: Nutrition agent not available for data retrieval"
                
                # Create a temporary nutrition state for the request
                from app.agentsv2.nutrition_agent import NutritionAgentState
                nutrition_state = NutritionAgentState(
                    original_prompt=request,
                    user_id=self.current_user_id
                )
                
                # Use the nutrition agent's retrieval method (now properly awaited)
                result_state = await self.nutrition_agent.retrieve_nutrition_data(nutrition_state)
                
                if result_state.has_error:
                    return f"Data retrieval failed: {result_state.error_context.get('message', 'Unknown error')}"
                
                # Extract raw data from the agent's execution
                # The nutrition agent uses tools that return raw JSON data, but the final output mixes it with commentary
                # Let's try to extract just the JSON data part
                query_results = result_state.query_results
                if query_results and "output" in query_results:
                    output_content = query_results["output"]
                    
                    # Try to extract JSON arrays in the output (nutrition data is typically returned as JSON arrays)
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
                                return f"Retrieved {len(parsed_data)} nutrition records.\n\nComplete nutrition data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it - it will be available as 'nutrition_data' DataFrame."
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
                                return f"Retrieved {len(parsed_data)} nutrition records (reconstructed).\n\nComplete nutrition data:\n{json.dumps(parsed_data, indent=2)}\n\nThis data is now available for analysis. Use execute_python_code to analyze it."
                        except:
                            pass
                    
                    # If we can't extract structured data, return the full raw response
                    return f"Data retrieved but could not extract structured format. Full raw response:\n{output_content}\n\nNote: The nutrition agent returned commentary instead of raw data. You may need to refine the request."
                
                else:
                    return "No data found for the request"
                    
            except Exception as e:
                return f"Error retrieving nutrition data: {str(e)}"
        
        @tool
        async def execute_python_code(code: str) -> str:
            """
            Execute Python code locally with safe environment.
            
            This tool allows the agent to:
            - Run nutrition data analysis and visualization code
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
                            filename = f"nutrition_plot_{timestamp}.png"
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
                    'nutrition_data': pd.DataFrame(self.current_data) if self.current_data else pd.DataFrame()
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
        
        return [recipe_search_tool, retrieve_nutrition_data, execute_python_code]
    
    def get_tools(self):
        """Get the list of available tools."""
        return self.tools
    
    def _build_workflow(self):
        """Build the LangGraph workflow for nutrition code interpretation"""
        # Set up LangSmith tracing
        tracer = LangChainTracer()
        callback_manager = CallbackManager([tracer])
        
        workflow = StateGraph(NutritionAnalyzeWorkflowState)
        
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
    
    def check_analysis_success(self, state: NutritionAnalyzeWorkflowState) -> str:
        return "error" if state.has_error else "continue"
    
    async def analyze_request(self, state: NutritionAnalyzeWorkflowState) -> NutritionAnalyzeWorkflowState:
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
            You are a nutrition data analysis and planning agent. Your role is to interpret user requests about diet, nutrition, fitness goals, and food preferences, and break them down into a structured plan of actions that a downstream execution agent (e.g., Python code executor, web browser, or API connector) can perform.

            The user may request anything from simple nutrient tracking to complex goal-based recommendations using external data sources. Your job is to:

                Understand the intent and scope of the user’s nutrition-related query.

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
                    "nutrition": ["nutrient categories", "food logs", "dates", "portion sizes", "etc."],
                    "demographics": ["age", "sex", "weight", "goals", "activity level"],
                    "external_sources": ["yes|no|optional", "e.g., YouTube, USDA API, recipe DB"],
                    "nutrient_targets": "yes|no|optional"
                }},
                "time_period": "recent|7_days|30_days|6_months|1_year|user_specified",
                "granularity": "daily|weekly|per_meal|as_suitable",
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
                        "description": f"Analyze nutrition data: {state.original_request}",
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
                    "description": f"Perform statistical analysis of nutrition data: {state.original_request}",
                    "methodology": "Descriptive statistics and visualization",
                    "visualizations": ["bar_chart", "summary_table"],
                    "metrics": ["mean", "median", "range", "nutrient_distribution"]
                }
                state.data_requirements = ["nutrition_data"]
            
            self.log_execution_step(state, "analyze_request", "completed")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {"step": "analyze_request", "error": str(e)}
            self.log_execution_step(state, "analyze_request", "failed", {"error": str(e)})
        
        return state
    
    async def agent_code_analysis(self, state: NutritionAnalyzeWorkflowState) -> NutritionAnalyzeWorkflowState:
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
                You are a Python data analysis expert specializing in nutrition and dietary data. Execute the following structured analysis workflow:

## ANALYSIS CONTEXT
- Request: {state.original_request}
- Type: {state.analysis_type}
- Plan: {json.dumps(state.analysis_plan, indent=2)}
- Data Requirements: {json.dumps(state.data_requirements, indent=2) if state.data_requirements else 'Not specified'}
- User ID: {state.user_id}
- Goals: {json.dumps(state.analysis_plan.get('goals', [state.original_request]), indent=2)}
- Tasks: {json.dumps(state.analysis_plan.get('tasks', []), indent=2)}
- Time Period: {state.analysis_plan.get('time_period', 'Not specified')}
- Granularity: {state.analysis_plan.get('granularity', 'Not specified')}

## EXECUTION WORKFLOW

### STEP 1: REQUEST ANALYSIS & TOOL SELECTION
🎯 Determine request type and external information needs:

**Analysis Triggers** (always required):
- Data analysis, trends, patterns, statistical insights
- Nutritional assessment and evaluation
- Charts, graphs, visualizations

**Recommendation Triggers** (optional):
- Keywords: "recommendations", "suggest", "advice", "what should I do"
- Keywords: "meal plans", "recipes", "food suggestions"
- Keywords: "improve", "optimize", "better nutrition"
- Keywords: "help me", "guide me", "plan my meals"

**Recipe Search Usage**:
- For analysis: Research, studies, nutritional guidelines
- For recommendations: Recipes, YouTube cooking videos, meal planning content
- Use nutrition_recipe_search_tool when external information is needed for either purpose

### STEP 2: DATA RETRIEVAL
A. **retrieve_nutrition_data**:
   - Request comprehensive data (all nutrients, wide timeframe)
   - Use JSON format, broad requests to minimize calls
   - Include synonyms and variations of nutrient names
   - Specify time granularity and aggregation requirements

B. **nutrition_recipe_search_tool** (when external info needed):
   - Recipe searches: "high protein recipes for 150g daily protein"
   - Research: "protein intake recommendations studies"  
   - YouTube: "YouTube high protein meal prep recipes"
   - Food lists: "best high protein foods list"

### STEP 3: DATA PROCESSING & ANALYSIS
Use **execute_python_code** for:
- Data analysis with specific time granularity
- Statistical calculations and metrics
- Visualization creation
- Results storage in 'results' dictionary

### STEP 4: CONTENT EXTRACTION & MEAL PLANNING
When nutrition_recipe_search_tool returns results, extract rich content:
- `result['recipes']` → actual recipe content
- `result['ingredients']` → ingredient lists  
- `result['instructions']` → cooking steps
- `result['meal_plan']` → meal planning data
- `result['nutritional_info']` → macro information
- `result['tips']` → cooking and nutrition tips

## AVAILABLE TOOLS

1. **nutrition_recipe_search_tool**: External information (recipes, research, YouTube videos)
2. **retrieve_nutrition_data**: User's nutrition data with natural language requests
3. **execute_python_code**: Analysis, calculations, visualizations (pandas, numpy, matplotlib, seaborn)

## CRITICAL RULES

### MANDATORY BEHAVIORS:
- 🚨 NEVER ask user for information - use tools
- Start immediately with tool usage
- Work with available data only
- Complete full analysis pipeline before responding

### RECIPE SEARCH USAGE:
- Use for external information needed for ANALYSIS (research, studies, guidelines)
- Use for RECOMMENDATIONS when requested (recipes, meal plans, food suggestions)
- Extract actual content, NOT just URLs
- Create detailed meal plans from extracted data (only when recommendations requested)
- Combine multiple sources for comprehensive plans


### VISUALIZATION REQUIREMENTS:
- Use `save_plot('filename')` function (NOT plt.savefig())
- Save to data/plots/ folder automatically
- Close plots with plt.close() after saving

## EXECUTION ORDER:
1. Analyze request → Select appropriate tools
2. Retrieve nutrition data (if needed)
3. Perform recipe search (if external info needed for analysis OR recommendations)
4. Execute Python analysis and create visualizations
5. Provide ANALYSIS results (mandatory)
6. Provide RECOMMENDATIONS only if user specifically requests them

## RESPONSE FORMAT:

🚨 **CRITICAL: RESPOND ONLY WITH COMPREHENSIVE JSON FORMAT**

After completing your analysis and tools execution, provide your response in this EXACT JSON format with ALL details included. Do NOT provide any text before or after the JSON - respond ONLY with the JSON structure:

```json
{{
    "analysis_overview": "Comprehensive overview of the analysis performed and methodology used",
    "analysis_summary": "Detailed summary of key nutritional findings from data analysis",
    "key_findings": "Free text analysis of all findings including totals, averages, trends, patterns, and notable observations",
    "visualizations_created": [
        {{
            "filename": "plot_filename.png",
            "title": "Descriptive title of the plot",
            "description": "Detailed description of what this visualization shows",
            "key_findings": "Specific insights and trends visible in this chart",
            "plot_path": "data/plots/plot_filename.png",
            "chart_type": "Type of chart created (line, bar, scatter, etc.)"
        }}
    ]
    "recommendations": {{
        "trigger_detected": false, // Set to true only if user specifically requested recommendations
        "content": [
            {{
                "category": "Category name (e.g., 'High Protein Recipes')",
                "suggestions": [
                    {{
                        "title": "Specific recipe or suggestion title",
                        "description": "Detailed description with instructions",
                        "key_benefits": "Why this recommendation is valuable",
                        "source_url": "URL if available from web search"
                    }}
                ]
            }}
        ]
    }}
}}
```

### MANDATORY JSON RESPONSE RULES:
- 🚨 RESPOND ONLY WITH THE JSON - NO TEXT BEFORE OR AFTER
- Include ALL analysis details in the JSON structure
- Set recommendations.trigger_detected to true ONLY if user asks for recommendations using keywords: "recommendations", "suggest", "advice", "what should I do", "meal plans", "recipes", "food suggestions", "improve", "optimize", "better nutrition", "help me", "guide me", "plan my meals"
- If recommendations not requested, keep recommendations.content as empty array []
- Fill ALL sections with detailed information from your analysis
- Use specific numbers, percentages, and quantitative results wherever possible

### KEY_FINDINGS GUIDANCE:
- Include all findings in natural free text: totals, averages, trends, patterns, notable observations, and data sources

                PLOT SAVING EXAMPLE:
                ```python
                plt.figure(figsize=(12, 6))
                # ... create your plot ...
                plt.title('My Nutrition Chart')
                
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
                save_plot(f'my_nutrition_chart_name_{current_date}')  # ← Use this, NOT plt.savefig()
                plt.close()
                ```
                
                ADDITIONAL DATE FORMATTING EXAMPLES:
                ```python
                # For daily nutrition data over weeks/months:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                plt.xticks(rotation=45)
                
                # For monthly nutrition data over years:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                plt.xticks(rotation=45)
                
                # For automatic date formatting (recommended):
                plt.gcf().autofmt_xdate()  # Automatically format x-axis dates
                ```

Start execution immediately following this workflow!
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
            
            print(f"🔍 [DEBUG] agent_code_analysis - Result type: {type(result)}")
            print(f"🔍 [DEBUG] agent_code_analysis - Last message type: {type(final_message)}")
            print(f"🔍 [DEBUG] agent_code_analysis - Total messages: {len(state.messages)}")
            print(f"🔍 [DEBUG] agent_code_analysis - ReAct agent completed with {len(result['messages'])} messages")
            
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
    
    async def format_results(self, state: NutritionAnalyzeWorkflowState) -> NutritionAnalyzeWorkflowState:
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
                    "task_types": ["nutrition_analysis"],
                    "results": {
                        "analysis": structured_analysis if structured_analysis else final_response,
                        "original_request": state.original_request
                    },
                    "execution_log": state.execution_log,
                    "message": "Nutrition analysis completed successfully"
                }
                
                # Don't separately extract visualizations - they're already in the structured analysis
                # The response_utils.py will handle visualization extraction from the structured analysis
                print(f"🔍 [DEBUG] format_results - Structured analysis contains visualizations: {bool(structured_analysis and 'visualizations_created' in structured_analysis)}")
            
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
    
    async def handle_error(self, state: NutritionAnalyzeWorkflowState) -> NutritionAnalyzeWorkflowState:
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
                "Check if the nutrition request is clear and specific",
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
                "Verify database connectivity for nutrition data retrieval",
                "Check local Python environment and permissions"
            ])
        
        if "timeout" in error_msg:
            suggestions.append("Consider breaking down complex nutrition requests into smaller parts")
        elif "connection" in error_msg:
            suggestions.append("Check network connectivity and service availability")
        elif "permission" in error_msg:
            suggestions.append("Verify API keys and service permissions")
        
        return suggestions if suggestions else ["Review error logs for more details"]
    
    def log_execution_step(self, state: NutritionAnalyzeWorkflowState, step_name: str, status: str, details: Dict = None):
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
        Execute the nutrition code interpreter workflow with agent-driven data retrieval and analysis.
        
        Args:
            request: The user's nutrition analysis request
            user_id: User ID for data retrieval
            
        Returns:
            Dict containing the analysis results
        """
        try:
            # Initialize state without pre-retrieved data - agent will retrieve as needed
            initial_state = NutritionAnalyzeWorkflowState(
                original_request=request,
                user_id=user_id,
                raw_data={},  # Empty - agent will populate using retrieve_nutrition_data tool
                data_summary={},
                analysis_type="",
                analysis_plan={}
            )
            
            # Execute workflow with agent and tools and LangSmith tracing
            result = await self.workflow.ainvoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": f"nutrition-code-interpreter-{user_id}",
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
    
    async def test_nutrition_code_interpreter():
        interpreter = NutritionAnalyzeWorkflow()
        
        # Test requests
        test_requests = [
            "Analyze my nutrition data for protein intake and recommend me the new receipes to meet my protein intake of 150g daily"
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
    # asyncio.run(test_nutrition_code_interpreter()) 