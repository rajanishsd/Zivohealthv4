from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional, Tuple
import os
import re
import logging
from pathlib import Path
import ast
import inspect

logger = logging.getLogger(__name__)

router = APIRouter()

class LangGraphWorkflowParser:
    """Parser to extract LangGraph workflow structure from Python code"""
    
    def __init__(self):
        self.workflow_cache = {}
    
    def parse_workflow_from_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse workflow structure from a Python file containing _build_workflow method"""
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            # Find the class with _build_workflow method
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if (isinstance(method, ast.FunctionDef) and 
                            method.name == '_build_workflow'):
                            return self._extract_workflow_structure(method, content)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing workflow from {file_path}: {e}")
            return None
    
    def _extract_workflow_structure(self, method_node: ast.FunctionDef, source_code: str) -> Dict[str, Any]:
        """Extract workflow structure from _build_workflow method AST"""
        
        nodes = []
        edges = []
        conditional_edges = []
        entry_point = None
        
        # Walk through the method body to find workflow operations
        for stmt in ast.walk(method_node):
            if isinstance(stmt, ast.Call):
                # Check for workflow.add_node calls
                if (isinstance(stmt.func, ast.Attribute) and 
                    stmt.func.attr == 'add_node' and
                    len(stmt.args) >= 2):
                    
                    node_id = self._extract_string_value(stmt.args[0])
                    node_function = self._extract_string_value(stmt.args[1])
                    
                    if node_id:
                        nodes.append({
                            'id': node_id,
                            'function': node_function or node_id,
                            'type': self._determine_node_type(node_id)
                        })
                
                # Check for workflow.add_edge calls
                elif (isinstance(stmt.func, ast.Attribute) and 
                      stmt.func.attr == 'add_edge' and
                      len(stmt.args) >= 2):
                    
                    source = self._extract_string_value(stmt.args[0])
                    target = self._extract_string_value(stmt.args[1])
                    
                    if source and target:
                        edges.append({
                            'id': f"{source}_to_{target}",
                            'source': source,
                            'target': target,
                            'type': 'direct'
                        })
                
                # Check for workflow.add_conditional_edges calls
                elif (isinstance(stmt.func, ast.Attribute) and 
                      stmt.func.attr == 'add_conditional_edges' and
                      len(stmt.args) >= 3):
                    
                    source = self._extract_string_value(stmt.args[0])
                    condition_func = self._extract_string_value(stmt.args[1])
                    
                    # Extract the mapping dictionary
                    if isinstance(stmt.args[2], ast.Dict):
                        for key, value in zip(stmt.args[2].keys, stmt.args[2].values):
                            condition = self._extract_string_value(key)
                            target = self._extract_string_value(value)
                            
                            if source and condition and target:
                                conditional_edges.append({
                                    'id': f"{source}_to_{target}_on_{condition}",
                                    'source': source,
                                    'target': target,
                                    'condition': condition,
                                    'condition_function': condition_func,
                                    'type': 'conditional'
                                })
                
                # Check for workflow.set_entry_point calls
                elif (isinstance(stmt.func, ast.Attribute) and 
                      stmt.func.attr == 'set_entry_point' and
                      len(stmt.args) >= 1):
                    
                    entry_point = self._extract_string_value(stmt.args[0])
        
        return {
            'nodes': nodes,
            'edges': edges,
            'conditional_edges': conditional_edges,
            'entry_point': entry_point,
            'workflow_type': 'langgraph'
        }
    
    def _extract_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s
        elif isinstance(node, ast.Attribute):
            # Handle cases like self.method_name
            return node.attr
        return None
    
    def _determine_node_type(self, node_id: str) -> str:
        """Determine node type based on node ID patterns"""
        node_id_lower = node_id.lower()
        
        if any(keyword in node_id_lower for keyword in ['input', 'start', 'initialize', 'begin']):
            return 'input'
        elif any(keyword in node_id_lower for keyword in ['output', 'end', 'finalize', 'complete', 'response']):
            return 'output'
        elif any(keyword in node_id_lower for keyword in ['error', 'handle_error', 'exception']):
            return 'error'
        elif any(keyword in node_id_lower for keyword in ['route', 'decide', 'classify', 'analyze']):
            return 'decision'
        else:
            return 'process'
    
    def convert_to_reactflow_format(self, workflow_data: Dict[str, Any], agent_name: str) -> Tuple[List[Dict], List[Dict]]:
        """Convert parsed workflow to ReactFlow format"""
        
        if not workflow_data:
            return [], []
        
        nodes = []
        edges = []
        
        # Convert nodes
        node_positions = self._calculate_node_positions(workflow_data)
        
        for i, node in enumerate(workflow_data.get('nodes', [])):
            node_id = node['id']
            position = node_positions.get(node_id, {'x': 100 + i * 200, 'y': 100})
            
            reactflow_node = {
                'id': node_id,
                'type': node.get('type', 'default'),
                'data': {
                    'label': self._format_node_label(node_id),
                    'function': node.get('function', node_id),
                    'agent': agent_name
                },
                'position': position
            }
            
            # Mark entry point
            if node_id == workflow_data.get('entry_point'):
                reactflow_node['data']['isEntryPoint'] = True
                if reactflow_node['type'] == 'process':
                    reactflow_node['type'] = 'input'
            
            nodes.append(reactflow_node)
        
        # Convert direct edges
        for edge in workflow_data.get('edges', []):
            edges.append({
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'type': 'default',
                'data': {'type': 'direct'}
            })
        
        # Convert conditional edges
        for edge in workflow_data.get('conditional_edges', []):
            edges.append({
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'type': 'default',
                'label': edge.get('condition', ''),
                'data': {
                    'type': 'conditional',
                    'condition': edge.get('condition'),
                    'condition_function': edge.get('condition_function')
                },
                'style': {
                    'strokeDasharray': '5,5',
                    'stroke': '#ff6b6b'
                }
            })
        
        return nodes, edges
    
    def _calculate_node_positions(self, workflow_data: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
        """Calculate positions for nodes in a flow layout"""
        
        nodes = workflow_data.get('nodes', [])
        edges = workflow_data.get('edges', []) + workflow_data.get('conditional_edges', [])
        entry_point = workflow_data.get('entry_point')
        
        if not nodes:
            return {}
        
        # Build adjacency list
        graph = {}
        for node in nodes:
            graph[node['id']] = []
        
        for edge in edges:
            if edge['source'] in graph:
                graph[edge['source']].append(edge['target'])
        
        # Perform topological sort starting from entry point
        positions = {}
        visited = set()
        levels = {}
        
        def assign_level(node_id, level):
            if node_id in levels:
                levels[node_id] = max(levels[node_id], level)
            else:
                levels[node_id] = level
            
            if node_id not in visited:
                visited.add(node_id)
                for neighbor in graph.get(node_id, []):
                    assign_level(neighbor, level + 1)
        
        # Start from entry point or first node
        start_node = entry_point if entry_point else nodes[0]['id']
        assign_level(start_node, 0)
        
        # Assign remaining nodes
        for node in nodes:
            if node['id'] not in levels:
                levels[node['id']] = 0
        
        # Calculate positions based on levels
        level_counts = {}
        for node_id, level in levels.items():
            if level not in level_counts:
                level_counts[level] = 0
            level_counts[level] += 1
        
        level_positions = {}
        for node_id, level in levels.items():
            if level not in level_positions:
                level_positions[level] = 0
            
            x = 150 + level * 250
            y = 100 + level_positions[level] * 120
            
            positions[node_id] = {'x': x, 'y': y}
            level_positions[level] += 1
        
        return positions
    
    def _format_node_label(self, node_id: str) -> str:
        """Format node ID into a readable label"""
        # Convert snake_case to Title Case
        words = node_id.replace('_', ' ').split()
        return ' '.join(word.capitalize() for word in words)

class AgentAnalyzer:
    """Enhanced analyzer that extracts real LangGraph workflows from agent files"""
    
    def __init__(self):
        self.agents_dir = Path(__file__).parent.parent.parent.parent / "agents"
        self.workflow_parser = LangGraphWorkflowParser()
    
    def analyze_agents(self) -> Dict[str, Any]:
        """Analyze all agent files and extract their real LangGraph workflows"""
        
        logger.info(f"Looking for agents in: {self.agents_dir}")
        logger.info(f"Agents directory exists: {self.agents_dir.exists()}")
        
        if not self.agents_dir.exists():
            logger.error(f"Agents directory not found: {self.agents_dir}")
            return self._get_fallback_agents()
        
        agent_files = list(self.agents_dir.glob("*_agent.py"))
        # Also include document_processing_workflow.py
        workflow_file = self.agents_dir / "document_processing_workflow.py"
        if workflow_file.exists():
            agent_files.append(workflow_file)
        
        logger.info(f"Found {len(agent_files)} agent files: {[f.name for f in agent_files]}")
        
        agents = {}
        
        for file_path in agent_files:
            try:
                agent_data = self._analyze_agent_file(file_path)
                if agent_data:
                    agents[agent_data['id']] = agent_data['workflow']
                    logger.info(f"Successfully analyzed {file_path.name} -> {agent_data['id']}")
                else:
                    logger.warning(f"No data returned for {file_path.name}")
            except Exception as e:
                logger.error(f"Error analyzing {file_path.name}: {e}")
                continue
        
        # Add fallback agents if none found
        if not agents:
            logger.warning("No agents found, using fallback data")
            agents = self._get_fallback_agents()
        
        return agents
    
    def _analyze_agent_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single agent file and extract real LangGraph workflow"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            agent_name = self._extract_agent_name(content, file_path.name)
            capabilities = self._extract_capabilities(content)
            data_types = self._extract_data_types(content, file_path.name)
            operations = self._extract_operations(content)
            tools = self._extract_tools(content)
            description = self._extract_description(content, file_path.name)
            
            # Parse real LangGraph workflow from _build_workflow method
            workflow_data = self.workflow_parser.parse_workflow_from_file(file_path)
            
            if workflow_data:
                # Convert to ReactFlow format
                nodes, edges = self.workflow_parser.convert_to_reactflow_format(workflow_data, agent_name)
                logger.info(f"Extracted real LangGraph workflow from {file_path.name}: {len(nodes)} nodes, {len(edges)} edges")
            else:
                # Fallback to generated workflow if parsing fails
                logger.warning(f"Could not parse LangGraph workflow from {file_path.name}, using fallback")
                nodes, edges = self._generate_workflow_from_agent(content, agent_name, file_path.name)
            
            agent_id = file_path.stem.replace('_agent', '').replace('_', '').replace('document_processing_workflow', 'documentprocessing')
            
            workflow = {
                'name': agent_name,
                'description': description,
                'color': self._get_agent_color(agent_id),
                'capabilities': capabilities,
                'dataTypes': data_types,
                'operations': operations,
                'tools': tools,
                'endToEndFlow': self._generate_end_to_end_flow(operations),
                'avgResponseTime': self._estimate_response_time(operations),
                'successRate': self._estimate_success_rate(agent_id),
                'nodes': nodes,
                'edges': edges,
                'workflowType': workflow_data.get('workflow_type', 'generated') if workflow_data else 'generated',
                'entryPoint': workflow_data.get('entry_point') if workflow_data else None,
                'isLangGraphWorkflow': bool(workflow_data)
            }
            
            return {'id': agent_id, 'workflow': workflow}
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path.name}: {e}")
            return None
    
    def _extract_agent_name(self, content: str, filename: str) -> str:
        """Extract agent name from content or filename"""
        # Try to extract class name
        class_match = re.search(r'class\s+(\w+Agent)\s*\(', content)
        if class_match:
            name = class_match.group(1)
            # Convert CamelCase to Title Case
            return re.sub(r'([A-Z])', r' \1', name).strip()
        
        # Fallback to filename
        base_name = filename.replace('_agent.py', '').replace('_', ' ')
        return base_name.title() + ' Agent'
    
    def _extract_capabilities(self, content: str) -> List[str]:
        """Extract capabilities from agent content"""
        capabilities = []
        
        # Look for explicit capabilities
        patterns = [
            r'capabilities\s*=\s*\[(.*?)\]',
            r'self\.capabilities\s*=\s*\[(.*?)\]',
            r'"capabilities":\s*\[(.*?)\]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                caps_str = match.group(1)
                caps = [cap.strip().strip('\'"') for cap in caps_str.split(',') if cap.strip()]
                capabilities.extend(caps)
                break
        
        # If no explicit capabilities, infer from methods
        if not capabilities:
            if 'extract_data' in content:
                capabilities.append('extract')
            if 'store_data' in content:
                capabilities.append('store')
            if 'retrieve_data' in content:
                capabilities.append('retrieve')
            if 'assess_question_relevance' in content:
                capabilities.append('assess')
        
        return capabilities if capabilities else ['extract', 'store', 'retrieve', 'assess']
    
    def _extract_data_types(self, content: str, filename: str) -> List[str]:
        """Extract data types from agent content"""
        data_types = []
        
        # Look for explicit data types
        patterns = [
            r'data_types\s*=\s*\[(.*?)\]',
            r'self\.data_types\s*=\s*\[(.*?)\]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                types_str = match.group(1)
                types = [t.strip().strip('\'"') for t in types_str.split(',') if t.strip()]
                data_types.extend(types)
                break
        
        # Infer data types from agent type
        if not data_types:
            if 'lab' in filename.lower():
                data_types = ['test_results', 'reference_ranges', 'lab_categories']
            elif 'vitals' in filename.lower():
                data_types = ['vital_signs', 'measurements', 'trends']
            elif 'pharmacy' in filename.lower():
                data_types = ['medications', 'costs', 'pharmacy_bills']
            elif 'prescription' in filename.lower():
                data_types = ['medications', 'dosages', 'prescriptions', 'instructions']
            elif 'medical_doctor' in filename.lower():
                data_types = ['medical_queries', 'health_assessments', 'recommendations']
            elif 'customer' in filename.lower():
                data_types = ['customer_queries', 'interactions', 'support_requests']
            else:
                data_types = ['health_data', 'medical_records']
        
        return data_types
    
    def _extract_operations(self, content: str) -> List[str]:
        """Extract operations from agent content"""
        operations = []
        
        # Look for async def methods
        method_matches = re.findall(r'async def (\w+)', content)
        standard_ops = ['extract_data', 'store_data', 'retrieve_data', 'assess_question_relevance']
        
        for method in method_matches:
            if method in standard_ops:
                operations.append(method)
        
        return operations if operations else standard_ops
    
    def _extract_tools(self, content: str) -> List[str]:
        """Extract tools from agent content"""
        tools = set()
        
        tool_patterns = {
            r'ChatOpenAI|OpenAI|GPT': 'GPT-4',
            r'OCR|Tesseract': 'Tesseract OCR',
            r'Database|PostgreSQL|psycopg': 'PostgreSQL',
            r'Redis': 'Redis',
            r'FastAPI': 'FastAPI',
            r'SQLAlchemy': 'SQLAlchemy'
        }
        
        for pattern, tool_name in tool_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                tools.add(tool_name)
        
        return list(tools) if tools else ['GPT-4', 'Database']
    
    def _extract_description(self, content: str, filename: str) -> str:
        """Extract description from agent content"""
        # Look for class docstring
        docstring_match = re.search(r'class\s+\w+Agent\s*\([^)]*\):\s*"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            return docstring_match.group(1).strip()
        
        # Look for module docstring
        module_docstring = re.search(r'^"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
        if module_docstring:
            return module_docstring.group(1).strip()
        
        # Generate description based on filename
        agent_type = filename.replace('_agent.py', '').replace('_', ' ').title()
        return f"Handles {agent_type.lower()} related operations and data processing"
    
    def _generate_workflow_from_agent(self, content: str, agent_name: str, filename: str) -> tuple:
        """Generate workflow nodes and edges based on agent type"""
        if 'customer' in filename.lower():
            return self._generate_customer_workflow()
        elif 'lab' in filename.lower():
            return self._generate_lab_workflow()
        elif 'vitals' in filename.lower():
            return self._generate_vitals_workflow()
        elif 'pharmacy' in filename.lower():
            return self._generate_pharmacy_workflow()
        elif 'prescription' in filename.lower():
            return self._generate_prescription_workflow()
        elif 'medical_doctor' in filename.lower():
            return self._generate_medical_doctor_workflow()
        else:
            return self._generate_default_workflow(agent_name)
    
    def _generate_customer_workflow(self) -> tuple:
        """Generate customer agent workflow"""
        nodes = [
            {'id': 'input', 'type': 'input', 'data': {'label': 'Customer Query'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'process', 'data': {'label': 'Process Query'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'analyze', 'data': {'label': 'Analyze Intent'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'response', 'type': 'output', 'data': {'label': 'Generate Response'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'input', 'target': 'process'},
            {'id': 'e2', 'source': 'process', 'target': 'analyze'},
            {'id': 'e3', 'source': 'analyze', 'target': 'response'}
        ]
        return nodes, edges
    
    def _generate_lab_workflow(self) -> tuple:
        """Generate lab agent workflow"""
        nodes = [
            {'id': 'upload', 'type': 'input', 'data': {'label': 'Lab Document'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'ocr', 'data': {'label': 'OCR Processing'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'extract', 'data': {'label': 'Extract Values'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'store', 'type': 'output', 'data': {'label': 'Store Results'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'upload', 'target': 'ocr'},
            {'id': 'e2', 'source': 'ocr', 'target': 'extract'},
            {'id': 'e3', 'source': 'extract', 'target': 'store'}
        ]
        return nodes, edges
    
    def _generate_vitals_workflow(self) -> tuple:
        """Generate vitals agent workflow"""
        nodes = [
            {'id': 'input', 'type': 'input', 'data': {'label': 'Vitals Data'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'validate', 'data': {'label': 'Validate Ranges'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'analyze', 'data': {'label': 'Analyze Trends'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'alert', 'type': 'output', 'data': {'label': 'Generate Alerts'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'input', 'target': 'validate'},
            {'id': 'e2', 'source': 'validate', 'target': 'analyze'},
            {'id': 'e3', 'source': 'analyze', 'target': 'alert'}
        ]
        return nodes, edges
    
    def _generate_pharmacy_workflow(self) -> tuple:
        """Generate pharmacy agent workflow"""
        nodes = [
            {'id': 'receipt', 'type': 'input', 'data': {'label': 'Pharmacy Receipt'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'parse', 'data': {'label': 'Parse Medications'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'cost', 'data': {'label': 'Calculate Costs'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'summary', 'type': 'output', 'data': {'label': 'Cost Summary'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'receipt', 'target': 'parse'},
            {'id': 'e2', 'source': 'parse', 'target': 'cost'},
            {'id': 'e3', 'source': 'cost', 'target': 'summary'}
        ]
        return nodes, edges
    
    def _generate_prescription_workflow(self) -> tuple:
        """Generate prescription agent workflow"""
        nodes = [
            {'id': 'prescription', 'type': 'input', 'data': {'label': 'Prescription'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'extract', 'data': {'label': 'Extract Medications'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'dosage', 'data': {'label': 'Parse Dosages'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'schedule', 'type': 'output', 'data': {'label': 'Create Schedule'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'prescription', 'target': 'extract'},
            {'id': 'e2', 'source': 'extract', 'target': 'dosage'},
            {'id': 'e3', 'source': 'dosage', 'target': 'schedule'}
        ]
        return nodes, edges
    
    def _generate_medical_doctor_workflow(self) -> tuple:
        """Generate medical doctor agent workflow"""
        nodes = [
            {'id': 'query', 'type': 'input', 'data': {'label': 'Medical Query'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'assess', 'data': {'label': 'Assess Symptoms'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'recommend', 'data': {'label': 'Generate Recommendations'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'response', 'type': 'output', 'data': {'label': 'Medical Response'}, 'position': {'x': 700, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'query', 'target': 'assess'},
            {'id': 'e2', 'source': 'assess', 'target': 'recommend'},
            {'id': 'e3', 'source': 'recommend', 'target': 'response'}
        ]
        return nodes, edges
    
    def _generate_default_workflow(self, agent_name: str) -> tuple:
        """Generate default workflow for unknown agent types"""
        nodes = [
            {'id': 'start', 'type': 'input', 'data': {'label': 'Input'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'process', 'data': {'label': 'Process'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'end', 'type': 'output', 'data': {'label': 'Output'}, 'position': {'x': 500, 'y': 100}}
        ]
        edges = [
            {'id': 'e1', 'source': 'start', 'target': 'process'},
            {'id': 'e2', 'source': 'process', 'target': 'end'}
        ]
        return nodes, edges
    
    def _get_agent_color(self, agent_id: str) -> str:
        """Get color for agent based on type"""
        color_map = {
            'customer': '#4CAF50',
            'lab': '#2196F3',
            'vitals': '#FF9800',
            'pharmacy': '#9C27B0',
            'prescription': '#F44336',
            'medicaldoctor': '#00BCD4',
            'enhancedcustomer': '#4CAF50',
            'documentprocessing': '#795548'
        }
        return color_map.get(agent_id, '#607D8B')
    
    def _generate_end_to_end_flow(self, operations: List[str]) -> str:
        """Generate end-to-end flow description"""
        if not operations:
            return "Input → Process → Output"
        
        flow_map = {
            'extract_data': 'Extract',
            'store_data': 'Store',
            'retrieve_data': 'Retrieve',
            'assess_question_relevance': 'Assess'
        }
        
        flow_steps = [flow_map.get(op, op.replace('_', ' ').title()) for op in operations]
        return ' → '.join(flow_steps)
    
    def _estimate_response_time(self, operations: List[str]) -> str:
        """Estimate response time based on operations"""
        base_time = 1
        for op in operations:
            if 'extract' in op:
                base_time += 2
            elif 'store' in op:
                base_time += 1
            elif 'retrieve' in op:
                base_time += 1
            elif 'assess' in op:
                base_time += 1
        
        return f"{base_time}-{base_time + 2} seconds"
    
    def _estimate_success_rate(self, agent_id: str) -> str:
        """Estimate success rate based on agent type"""
        rates = {
            'customer': '95%',
            'lab': '92%',
            'vitals': '96%',
            'pharmacy': '90%',
            'prescription': '88%',
            'medicaldoctor': '94%'
        }
        return rates.get(agent_id, '90%')
    
    def _get_fallback_agents(self) -> Dict[str, Any]:
        """Return fallback agent data when analysis fails"""
        return {
            'customer': {
                'name': 'Customer Agent',
                'description': 'Handles customer queries and interactions',
                'color': '#4CAF50',
                'capabilities': ['query', 'interact', 'assist'],
                'dataTypes': ['customer_data', 'queries'],
                'operations': ['process_query', 'provide_response'],
                'tools': ['GPT-4', 'Database'],
                'endToEndFlow': 'Query → Process → Response',
                'avgResponseTime': '2-3 seconds',
                'successRate': '95%',
                'nodes': self._generate_customer_workflow()[0],
                'edges': self._generate_customer_workflow()[1]
            },
            'lab': {
                'name': 'Lab Agent',
                'description': 'Processes laboratory test results and medical data',
                'color': '#2196F3',
                'capabilities': ['extract', 'analyze', 'validate'],
                'dataTypes': ['test_results', 'reference_ranges', 'lab_categories'],
                'operations': ['extract_data', 'store_data', 'retrieve_data'],
                'tools': ['GPT-4', 'Tesseract OCR', 'PostgreSQL'],
                'endToEndFlow': 'Extract → Store → Retrieve',
                'avgResponseTime': '3-5 seconds',
                'successRate': '92%',
                'nodes': self._generate_lab_workflow()[0],
                'edges': self._generate_lab_workflow()[1]
            }
        }

    def get_use_cases(self) -> Dict[str, Any]:
        """Get predefined use cases"""
        return {
            'file-upload': {
                'id': 'file-upload',
                'name': 'File Upload Analysis',
                'description': 'Analyze uploaded medical documents',
                'scenario': 'User uploads medical documents for analysis',
                'workflow': 'Upload → Process → Analyze → Report',
                'agents': ['Lab Agent', 'Vitals Agent'],
                'nodes': self._generate_file_upload_nodes(),
                'edges': self._generate_file_upload_edges(),
                'complexity': 'Medium',
                'avgTime': '30-60 seconds'
            },
            'question-only': {
                'id': 'question-only',
                'name': 'Question Only Query',
                'description': 'Process text-based medical questions',
                'scenario': 'User asks medical questions without file upload',
                'workflow': 'Question → Analyze → Respond',
                'agents': ['Medical Doctor Agent', 'Customer Agent'],
                'nodes': self._generate_question_only_nodes(),
                'edges': self._generate_question_only_edges(),
                'complexity': 'Low',
                'avgTime': '5-15 seconds'
            },
            'file-and-question': {
                'id': 'file-and-question',
                'name': 'File and Question Analysis',
                'description': 'Analyze documents with specific questions',
                'scenario': 'User uploads files and asks specific questions',
                'workflow': 'Upload → Process → Question → Analyze → Respond',
                'agents': ['Lab Agent', 'Medical Doctor Agent', 'Customer Agent'],
                'nodes': self._generate_file_and_question_nodes(),
                'edges': self._generate_file_and_question_edges(),
                'complexity': 'High',
                'avgTime': '45-90 seconds'
            }
        }
    
    def _generate_file_upload_nodes(self) -> List[Dict]:
        """Generate nodes for file upload use case"""
        return [
            {'id': 'upload', 'type': 'input', 'data': {'label': 'Upload File'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'validate', 'data': {'label': 'Validate File'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'process', 'data': {'label': 'Process Document'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'analyze', 'data': {'label': 'Analyze Content'}, 'position': {'x': 700, 'y': 100}},
            {'id': 'report', 'type': 'output', 'data': {'label': 'Generate Report'}, 'position': {'x': 900, 'y': 100}}
        ]
    
    def _generate_file_upload_edges(self) -> List[Dict]:
        """Generate edges for file upload use case"""
        return [
            {'id': 'e1', 'source': 'upload', 'target': 'validate'},
            {'id': 'e2', 'source': 'validate', 'target': 'process'},
            {'id': 'e3', 'source': 'process', 'target': 'analyze'},
            {'id': 'e4', 'source': 'analyze', 'target': 'report'}
        ]
    
    def _generate_question_only_nodes(self) -> List[Dict]:
        """Generate nodes for question only use case"""
        return [
            {'id': 'question', 'type': 'input', 'data': {'label': 'Medical Question'}, 'position': {'x': 100, 'y': 100}},
            {'id': 'analyze', 'data': {'label': 'Analyze Question'}, 'position': {'x': 300, 'y': 100}},
            {'id': 'respond', 'type': 'output', 'data': {'label': 'Generate Response'}, 'position': {'x': 500, 'y': 100}}
        ]
    
    def _generate_question_only_edges(self) -> List[Dict]:
        """Generate edges for question only use case"""
        return [
            {'id': 'e1', 'source': 'question', 'target': 'analyze'},
            {'id': 'e2', 'source': 'analyze', 'target': 'respond'}
        ]
    
    def _generate_file_and_question_nodes(self) -> List[Dict]:
        """Generate nodes for file and question use case"""
        return [
            {'id': 'upload', 'type': 'input', 'data': {'label': 'Upload File'}, 'position': {'x': 100, 'y': 50}},
            {'id': 'question', 'type': 'input', 'data': {'label': 'Ask Question'}, 'position': {'x': 100, 'y': 150}},
            {'id': 'process', 'data': {'label': 'Process File'}, 'position': {'x': 300, 'y': 50}},
            {'id': 'combine', 'data': {'label': 'Combine Context'}, 'position': {'x': 500, 'y': 100}},
            {'id': 'analyze', 'data': {'label': 'Analyze Together'}, 'position': {'x': 700, 'y': 100}},
            {'id': 'respond', 'type': 'output', 'data': {'label': 'Generate Response'}, 'position': {'x': 900, 'y': 100}}
        ]
    
    def _generate_file_and_question_edges(self) -> List[Dict]:
        """Generate edges for file and question use case"""
        return [
            {'id': 'e1', 'source': 'upload', 'target': 'process'},
            {'id': 'e2', 'source': 'process', 'target': 'combine'},
            {'id': 'e3', 'source': 'question', 'target': 'combine'},
            {'id': 'e4', 'source': 'combine', 'target': 'analyze'},
            {'id': 'e5', 'source': 'analyze', 'target': 'respond'}
        ]

# Initialize the analyzer
analyzer = AgentAnalyzer()

@router.get("/analyze")
async def get_agent_analysis():
    """Get analysis of all agents"""
    try:
        workflows = analyzer.analyze_agents()
        return workflows
    except Exception as e:
        logger.error(f"Error in get_agent_analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze agents")

@router.get("/use-cases")
async def get_use_cases():
    """Get predefined use cases"""
    try:
        use_cases = analyzer.get_use_cases()
        return use_cases
    except Exception as e:
        logger.error(f"Error in get_use_cases: {e}")
        raise HTTPException(status_code=500, detail="Failed to get use cases") 