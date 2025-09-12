const API_BASE = (process.env.REACT_APP_API_BASE_URL || '');
const apiUrl = (path: string) => `${API_BASE}${path}`;
import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  NodeTypes,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import agentAnalyzer from '../services/agentAnalyzer';
import type { AgentWorkflow, UseCase } from '../services/agentAnalyzer';

// Simple and effective ResizeObserver error suppression
(() => {
  const originalError = console.error;
  console.error = (...args) => {
    if (args[0] && args[0].toString().includes('ResizeObserver')) {
      return;
    }
    originalError(...args);
  };
})();

// Add custom styles for ReactFlow nodes
const customStyles = `
  .react-flow__node {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  .custom-node {
    background: #ffffff;
    border: 2px solid #d1d5db;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
    font-weight: 500;
    color: #374151;
    min-width: 140px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .custom-node-input {
    background: #e3f2fd;
    border: 2px solid #2196f3;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
    font-weight: 500;
    color: #374151;
    min-width: 140px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .custom-node-output {
    background: #e8f5e8;
    border: 2px solid #4caf50;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
    font-weight: 500;
    color: #374151;
    min-width: 140px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .expandable-icon {
    font-size: 16px;
    opacity: 0.8;
    margin-left: 6px;
  }
`;

// Custom Node Component
const CustomNode = ({ data, selected }: { data: any; selected: boolean }) => {
  return (
    <div
      style={{
        ...data.style,
        position: 'relative',
        cursor: data.expandable ? 'pointer' : 'default',
        padding: '12px',
        borderRadius: '8px',
        minWidth: '140px',
        textAlign: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        fontSize: '14px',
        fontWeight: '500',
        color: '#374151',
        border: selected ? '2px solid #3b82f6' : '2px solid #d1d5db',
        background: '#ffffff',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
        <span>{data.label}</span>
        {data.expandable && (
          <span style={{ fontSize: '16px', opacity: 0.8, color: '#059669' }}>🔍</span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

// Custom Input Node Component
const CustomInputNode = ({ data, selected }: { data: any; selected: boolean }) => {
  return (
    <div
      style={{
        ...data.style,
        position: 'relative',
        cursor: data.expandable ? 'pointer' : 'default',
        padding: '12px',
        borderRadius: '8px',
        minWidth: '140px',
        textAlign: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        fontSize: '14px',
        fontWeight: '500',
        color: '#374151',
        border: selected ? '2px solid #3b82f6' : '2px solid #2196f3',
        background: '#e3f2fd',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
        <span>{data.label}</span>
        {data.expandable && (
          <span style={{ fontSize: '16px', opacity: 0.8, color: '#059669' }}>🔍</span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

// Custom Output Node Component
const CustomOutputNode = ({ data, selected }: { data: any; selected: boolean }) => {
  return (
    <div
      style={{
        ...data.style,
        position: 'relative',
        cursor: data.expandable ? 'pointer' : 'default',
        padding: '12px',
        borderRadius: '8px',
        minWidth: '140px',
        textAlign: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        fontSize: '14px',
        fontWeight: '500',
        color: '#374151',
        border: selected ? '2px solid #3b82f6' : '2px solid #4caf50',
        background: '#e8f5e8',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
        <span>{data.label}</span>
        {data.expandable && (
          <span style={{ fontSize: '16px', opacity: 0.8, color: '#059669' }}>🔍</span>
        )}
      </div>
    </div>
  );
};

// Define node types
const nodeTypes: NodeTypes = {
  default: CustomNode,
  input: CustomInputNode,
  output: CustomOutputNode,
};

interface DynamicWorkflowVisualizationProps {
  selectedAgent?: string;
  onAgentChange?: (agent: string) => void;
}

const DynamicWorkflowVisualization: React.FC<DynamicWorkflowVisualizationProps> = ({
  selectedAgent = 'enhancedcustomer',
  onAgentChange
}) => {
  const [activeTab, setActiveTab] = useState<'agents' | 'usecases'>('usecases');
  const [currentAgent, setCurrentAgent] = useState(selectedAgent);
  const [currentUseCase, setCurrentUseCase] = useState('question-only');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [agentWorkflows, setAgentWorkflows] = useState<Record<string, AgentWorkflow>>({});
  const [useCases, setUseCases] = useState<Record<string, UseCase>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Fetch data from API
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        // Fetch agent workflows and use cases concurrently
        const [workflows, cases] = await Promise.all([
          fetch(apiUrl('/api/v1/agents/analyze')).then(res => res.json()),
          fetch(apiUrl('/api/v1/agents/use-cases')).then(res => res.json())
        ]);
        
        setAgentWorkflows(workflows);
        setUseCases(cases);
        
        // Set default selections if they don't exist
        if (!workflows[currentAgent] && Object.keys(workflows).length > 0) {
          setCurrentAgent(Object.keys(workflows)[0]);
        }
        if (!cases[currentUseCase] && Object.keys(cases).length > 0) {
          setCurrentUseCase(Object.keys(cases)[0]);
        }
      } catch (error) {
        console.error('Failed to fetch agent data:', error);
        // Fallback to analyzer's fallback data
        setAgentWorkflows(agentAnalyzer.getAgentWorkflows());
        setUseCases(agentAnalyzer.getUseCases());
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Initialize nodes and edges based on current selection
  const getInitialNodesAndEdges = useCallback(() => {
    if (activeTab === 'agents') {
      const workflow = agentWorkflows[currentAgent];
      return { nodes: workflow?.nodes || [], edges: workflow?.edges || [] };
    } else {
      const useCase = useCases[currentUseCase];
      return { nodes: useCase?.nodes || [], edges: useCase?.edges || [] };
    }
  }, [activeTab, currentAgent, currentUseCase, agentWorkflows, useCases]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleAgentChange = (agent: string) => {
    setCurrentAgent(agent);
    setExpandedAgents(new Set()); // Reset expanded agents when changing agent
    if (onAgentChange) {
      onAgentChange(agent);
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    // Re-fetch data
    const fetchData = async () => {
      try {
        const [workflows, cases] = await Promise.all([
          fetch(apiUrl('/api/v1/agents/analyze')).then(res => res.json()),
          fetch(apiUrl('/api/v1/agents/use-cases')).then(res => res.json())
        ]);
        
        setAgentWorkflows(workflows);
        setUseCases(cases);
      } catch (error) {
        console.error('Failed to refresh agent data:', error);
      } finally {
        setIsRefreshing(false);
      }
    };

    fetchData();
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  // Update nodes and edges when selection changes
  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = getInitialNodesAndEdges();
    
    // Add expandable property to nodes that represent agents in use cases
    const processedNodes = newNodes.map(node => {
      if (activeTab === 'usecases') {
        const agentKey = getAgentKeyFromNode(node);
        if (agentKey && agentWorkflows[agentKey]) {
          return {
            ...node,
            data: {
              ...node.data,
              expandable: true
            }
          };
        }
      }
      return node;
    });
    
    setNodes(processedNodes);
    setEdges(newEdges);
    setExpandedAgents(new Set()); // Reset expanded agents when changing tabs/selections
  }, [activeTab, currentAgent, currentUseCase, agentWorkflows, useCases, getInitialNodesAndEdges, setNodes, setEdges]);

  // Handle node clicks for expansion
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    if (activeTab === 'usecases' && node.data.expandable) {
      const agentKey = getAgentKeyFromNode(node);
      if (agentKey && agentWorkflows[agentKey]) {
        const newExpandedAgents = new Set(expandedAgents);
        
        if (expandedAgents.has(node.id)) {
          // Collapse: remove expanded nodes and edges
          newExpandedAgents.delete(node.id);
          setNodes(nodes => nodes.filter(n => !n.id.startsWith(`${node.id}-expanded-`)));
          setEdges(edges => edges.filter(e => 
            !e.id.startsWith(`${node.id}-expanded-`) && 
            e.id !== `${node.id}-connection`
          ));
        } else {
          // Expand: add agent's internal workflow
          newExpandedAgents.add(node.id);
          
          const agentWorkflow = agentWorkflows[agentKey];
          const expandedNodes = agentWorkflow.nodes.map((n, index) => ({
            ...n,
            id: `${node.id}-expanded-${n.id}`,
            position: {
              x: node.position.x + 200 + (index * 150),
              y: node.position.y + 100
            },
            data: {
              ...n.data,
              label: `${n.data.label} (${agentWorkflow.name})`
            },
            style: {
              ...n.style,
              opacity: 0.8,
              border: '2px dashed #9ca3af'
            }
          }));
          
          const expandedEdges = agentWorkflow.edges.map(e => ({
            ...e,
            id: `${node.id}-expanded-${e.id}`,
            source: `${node.id}-expanded-${e.source}`,
            target: `${node.id}-expanded-${e.target}`,
            style: { 
              ...e.style, 
              opacity: 0.6,
              strokeDasharray: '5,5'
            }
          }));
          
          // Add a connection from parent to first expanded node
          const connectionEdge = {
            id: `${node.id}-connection`,
            source: node.id,
            target: `${node.id}-expanded-${agentWorkflow.nodes[0].id}`,
            style: { 
              stroke: '#9ca3af', 
              strokeWidth: 2, 
              strokeDasharray: '10,5',
              opacity: 0.7
            },
            label: 'Internal Workflow',
            labelStyle: { fontSize: '10px', fill: '#6b7280' }
          };
          
          setNodes(nodes => [...nodes, ...expandedNodes]);
          setEdges(edges => [...edges, ...expandedEdges, connectionEdge]);
        }
        
        setExpandedAgents(newExpandedAgents);
      }
    }
  }, [activeTab, expandedAgents, agentWorkflows, setNodes, setEdges]);

  // Helper function to get agent key from node
  const getAgentKeyFromNode = (node: Node): string | null => {
    const label = node.data.label;
    if (label.includes('Lab')) return 'lab';
    if (label.includes('Vitals')) return 'vitals';
    if (label.includes('Pharmacy')) return 'pharmacy';
    if (label.includes('Prescription')) return 'prescription';
    if (label.includes('Medical Doctor') || label.includes('MD')) return 'medicaldoctor';
    if (label.includes('Customer')) return 'enhancedcustomer';
    return null;
  };

  if (isLoading) {
    return (
      <div className="w-full space-y-6">
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-xl border border-blue-100">
          <div className="flex items-center justify-center h-64">
            <div className="text-lg text-gray-600">Loading agent workflows...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Inject custom styles for ReactFlow nodes */}
      <style dangerouslySetInnerHTML={{ __html: customStyles }} />
      
      {/* Clean Header Section */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-xl border border-blue-100">
        <div className="section-header">
          <div className="section-title">Healthcare Agent Workflows</div>
          <button
            className={`refresh-button ${isRefreshing ? 'refreshing' : ''}`}
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Refresh Workflow"
          >
            {isRefreshing ? '⏳' : '🔄'}
          </button>
        </div>
        
        {/* Tab Navigation */}
        <div className="mb-12">
          <div className="relative">
            <nav className="flex" role="tablist">
              <button
                onClick={() => setActiveTab('agents')}
                className={`px-8 py-4 font-semibold transition-all duration-200 ${
                  activeTab === 'agents'
                    ? 'bg-white text-teal-600 z-10 relative'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 hover:text-gray-800'
                }`}
                style={{
                  fontSize: '28px',
                  border: '2px solid #d1d5db',
                  borderBottom: activeTab === 'agents' ? '2px solid white' : '2px solid #d1d5db',
                  borderTopLeftRadius: '8px',
                  borderTopRightRadius: '8px',
                  borderBottomLeftRadius: '0px',
                  borderBottomRightRadius: '0px',
                  marginRight: '4px',
                  marginBottom: activeTab === 'agents' ? '-2px' : '0',
                  outline: 'none',
                  cursor: 'pointer'
                }}
                role="tab"
                aria-selected={activeTab === 'agents'}
              >
                Individual Agents
              </button>
              <button
                onClick={() => setActiveTab('usecases')}
                className={`px-8 py-4 font-semibold transition-all duration-200 ${
                  activeTab === 'usecases'
                    ? 'bg-white text-teal-600 z-10 relative'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 hover:text-gray-800'
                }`}
                style={{
                  fontSize: '28px',
                  border: '2px solid #d1d5db',
                  borderBottom: activeTab === 'usecases' ? '2px solid white' : '2px solid #d1d5db',
                  borderTopLeftRadius: '8px',
                  borderTopRightRadius: '8px',
                  borderBottomLeftRadius: '0px',
                  borderBottomRightRadius: '0px',
                  marginBottom: activeTab === 'usecases' ? '-2px' : '0',
                  outline: 'none',
                  cursor: 'pointer'
                }}
                role="tab"
                aria-selected={activeTab === 'usecases'}
              >
                Use Cases
              </button>
            </nav>
            <div style={{ borderBottom: '2px solid #d1d5db', marginTop: '-2px' }}></div>
          </div>
        </div>

        {/* Selection Controls */}
        <div className="flex items-center space-x-8" style={{ marginBottom: '80px', paddingTop: '40px' }}>
          {activeTab === 'agents' ? (
            <>
              <label className="font-medium text-gray-700" style={{ fontSize: '28px' }}>
                Select Agent:
              </label>
              <select
                value={currentAgent}
                onChange={(e) => handleAgentChange(e.target.value)}
                className="px-6 py-4 bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 min-w-72 text-lg"
              >
                {Object.entries(agentWorkflows).map(([key, workflow]) => (
                  <option key={key} value={key}>
                    {workflow.name}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <>
              <label className="font-medium text-gray-700" style={{ fontSize: '28px' }}>
                Select Use Case:
              </label>
              <select
                value={currentUseCase}
                onChange={(e) => setCurrentUseCase(e.target.value)}
                className="px-6 py-4 bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 min-w-72 text-lg"
              >
                {Object.entries(useCases).map(([key, useCase]) => (
                  <option key={key} value={key}>
                    {useCase.name}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>
      </div>

      {/* Workflow Visualization */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden" style={{ marginTop: '60px' }}>
        <div className="border-b border-gray-200" style={{ padding: '32px', textAlign: 'center' }}>
          <h5 className="font-semibold text-gray-900" style={{ fontSize: '24px' }}>
            {activeTab === 'agents' ? 'Agent Workflow Diagram' : 'Use Case Flow Diagram'}
          </h5>
          {activeTab === 'usecases' && (
            <p className="text-sm text-gray-600 mt-2">
              💡 Click on nodes with 🔍 icon to expand and see internal agent workflows
            </p>
          )}
        </div>
        <div style={{ width: '100%', height: '600px' }}>
          {nodes.length === 0 ? (
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              height: '100%', 
              fontSize: '18px', 
              color: '#6b7280' 
            }}>
              Loading workflow diagram...
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              fitView
              className="bg-gray-50"
              nodeTypes={nodeTypes}
            >
              <Background color="#f1f5f9" gap={20} />
              <Controls />
              <MiniMap />
            </ReactFlow>
          )}
        </div>
      </div>
    </div>
  );
};

export default DynamicWorkflowVisualization; 