import axios from 'axios';

export interface AgentWorkflow {
  name: string;
  description: string;
  color: string;
  capabilities: string[];
  dataTypes: string[];
  operations: string[];
  tools: string[];
  endToEndFlow: string;
  avgResponseTime: string;
  successRate: string;
  nodes: any[];
  edges: any[];
}

export interface UseCase {
  id: string;
  name: string;
  description: string;
  scenario: string;
  workflow: string;
  agents: string[];
  nodes: any[];
  edges: any[];
  complexity: string;
  avgTime: string;
}

class AgentAnalyzer {
  private agentWorkflows: Record<string, AgentWorkflow> = {};
  private useCases: Record<string, UseCase> = {};
  private apiBaseUrl: string;

  constructor() {
    this.apiBaseUrl = process.env.REACT_APP_API_BASE_URL || '';
    this.initializeAgents();
    this.initializeUseCases();
  }

  private async initializeAgents() {
    try {
      const response = await axios.get<Record<string, AgentWorkflow>>(`${this.apiBaseUrl}/api/agents/analyze`);
      this.agentWorkflows = response.data;
    } catch (error) {
      console.error('Error fetching agent data:', error);
      this.loadFallbackAgents();
    }
  }

  private async initializeUseCases() {
    try {
      const response = await axios.get<Record<string, UseCase>>(`${this.apiBaseUrl}/api/use-cases`);
      this.useCases = response.data;
    } catch (error) {
      console.error('Error fetching use cases:', error);
      this.loadFallbackUseCases();
    }
  }

  private loadFallbackAgents() {
    this.agentWorkflows = {
      customer: {
        name: 'Customer Agent',
        description: 'Handles customer queries and interactions',
        color: '#4CAF50',
        capabilities: ['query', 'interact', 'assist'],
        dataTypes: ['customer_data', 'queries'],
        operations: ['process_query', 'provide_response'],
        tools: ['GPT-4', 'Database'],
        endToEndFlow: 'Query → Process → Response',
        avgResponseTime: '2-3 seconds',
        successRate: '95%',
        nodes: this.generateDefaultWorkflow('Customer').nodes,
        edges: this.generateDefaultWorkflow('Customer').edges
      }
    };
  }

  private loadFallbackUseCases() {
    this.useCases = {
      'file-upload': {
        id: 'file-upload',
        name: 'File Upload Analysis',
        description: 'Analyze uploaded medical documents',
        scenario: 'User uploads medical documents for analysis',
        workflow: 'Upload → Process → Analyze → Report',
        agents: ['Lab Agent', 'Vitals Agent'],
        nodes: this.generateFileUploadNodes(),
        edges: this.generateFileUploadEdges(),
        complexity: 'Medium',
        avgTime: '30-60 seconds'
      }
    };
  }

  private generateDefaultWorkflow(agentName: string): { nodes: any[], edges: any[] } {
    return {
      nodes: [
        { id: 'start', type: 'input', data: { label: 'Start' } },
        { id: 'process', data: { label: 'Process' } },
        { id: 'end', type: 'output', data: { label: 'End' } }
      ],
      edges: [
        { id: 'e1', source: 'start', target: 'process' },
        { id: 'e2', source: 'process', target: 'end' }
      ]
    };
  }

  private generateFileUploadNodes(): any[] {
    return [
      { id: 'upload', type: 'input', data: { label: 'Upload File' } },
      { id: 'process', data: { label: 'Process Document' } },
      { id: 'analyze', data: { label: 'Analyze Content' } },
      { id: 'report', type: 'output', data: { label: 'Generate Report' } }
    ];
  }

  private generateFileUploadEdges(): any[] {
    return [
      { id: 'e1', source: 'upload', target: 'process' },
      { id: 'e2', source: 'process', target: 'analyze' },
      { id: 'e3', source: 'analyze', target: 'report' }
    ];
  }

  public getAgentWorkflows(): Record<string, AgentWorkflow> {
    return this.agentWorkflows;
  }

  public getUseCases(): Record<string, UseCase> {
    return this.useCases;
  }
}

export default new AgentAnalyzer(); 