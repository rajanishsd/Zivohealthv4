# ZivoHealth React Admin Dashboard

A comprehensive React Admin dashboard for monitoring agent interactions, workflows, and system health.

## 🚀 Features

- **Real-time Monitoring**: Live charts and metrics with WebSocket updates
- **Workflow Visualization**: Complete request flow tracking and agent interaction timelines
- **Performance Analytics**: Agent performance metrics, tool usage, and error analysis  
- **Interactive Charts**: Responsive charts using Recharts library
- **Agent Configuration**: CRUD operations for agent settings
- **Audit Trail**: Complete logging and compliance features

## 📋 Prerequisites

- Node.js 18+ and npm
- FastAPI backend running on http://localhost:8000

## 🛠️ Installation

### 1. Install Node.js (if not installed)
```bash
# Using Homebrew on macOS
brew install node

# Or download from https://nodejs.org/
```

### 2. Create React Admin Project
```bash
# Create project
npx create-react-app zivo-dashboard --template typescript
cd zivo-dashboard

# Install React Admin and dependencies
npm install react-admin ra-data-json-server ra-input-rich-text
npm install recharts @types/recharts
npm install @mui/material @emotion/react @emotion/styled
npm install @mui/icons-material @mui/x-data-grid
npm install axios react-query
```

### 3. Install Chart Libraries
```bash
npm install recharts victory react-vis plotly.js react-plotly.js
npm install @types/plotly.js
```

### 4. Install UI Enhancement Libraries
```bash
npm install react-flow-renderer react-timeline-range-slider
npm install @mui/x-date-pickers dayjs
npm install react-virtualized-auto-sizer react-window
```

## 📁 Project Structure

```
zivo-dashboard/
├── src/
│   ├── components/
│   │   ├── Dashboard.tsx           # Main dashboard layout
│   │   ├── charts/
│   │   │   ├── RequestTimeline.tsx # Request volume chart
│   │   │   ├── AgentPerformance.tsx # Agent metrics chart
│   │   │   ├── ToolUsage.tsx       # Tool usage pie chart
│   │   │   └── ErrorAnalysis.tsx   # Error breakdown chart
│   │   ├── workflow/
│   │   │   ├── WorkflowViewer.tsx  # Request flow visualization
│   │   │   ├── AgentTimeline.tsx   # Agent interaction timeline
│   │   │   └── RequestDetail.tsx   # Detailed request view
│   │   └── monitoring/
│   │       ├── RealTimeMetrics.tsx # Live system metrics
│   │       ├── SystemHealth.tsx    # Health status indicators
│   │       └── AlertPanel.tsx      # Error alerts
│   ├── resources/
│   │   ├── agents.tsx              # Agent CRUD operations
│   │   ├── requests.tsx            # Request management
│   │   └── auditLogs.tsx          # Audit trail management
│   ├── providers/
│   │   ├── dataProvider.tsx        # API data provider
│   │   └── authProvider.tsx        # Authentication provider
│   └── utils/
│       ├── websocket.ts           # WebSocket utilities
│       └── api.ts                 # API helper functions
```

## 🎯 Key Components

### Dashboard.tsx - Main Layout
```typescript
import React from 'react';
import { Card, CardContent, Grid, Typography } from '@mui/material';
import { LineChart, BarChart, PieChart } from 'recharts';
import RequestTimeline from './charts/RequestTimeline';
import AgentPerformance from './charts/AgentPerformance';
import WorkflowViewer from './workflow/WorkflowViewer';
import RealTimeMetrics from './monitoring/RealTimeMetrics';

const Dashboard = () => {
  return (
    <Grid container spacing={3}>
      {/* KPI Cards */}
      <Grid item xs={12} sm={6} md={3}>
        <RealTimeMetrics />
      </Grid>
      
      {/* Charts Row */}
      <Grid item xs={12} md={6}>
        <RequestTimeline />
      </Grid>
      <Grid item xs={12} md={6}>
        <AgentPerformance />
      </Grid>
      
      {/* Workflow Visualization */}
      <Grid item xs={12}>
        <WorkflowViewer />
      </Grid>
    </Grid>
  );
};
```

### Charts with Real-time Data
```typescript
// RequestTimeline.tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useQuery } from 'react-query';

const RequestTimeline = () => {
  const { data, isLoading } = useQuery(
    'request-timeline',
    () => fetch('/api/v1/dashboard/charts/request-timeline').then(res => res.json()),
    { refetchInterval: 30000 } // Refresh every 30 seconds
  );

  if (isLoading) return <div>Loading...</div>;

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data?.data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="hour_label" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="requests" stroke="#8884d8" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
};
```

### Workflow Visualization
```typescript
// WorkflowViewer.tsx
import ReactFlow, { Node, Edge } from 'react-flow-renderer';

const WorkflowViewer = () => {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Convert agent workflow to React Flow nodes and edges
  const buildWorkflowGraph = (workflowSteps) => {
    const nodes = workflowSteps.map((step, index) => ({
      id: step.step_number.toString(),
      type: 'default',
      position: { x: index * 200, y: 0 },
      data: { 
        label: `${step.agent_name}\n${step.event_type}`,
        style: {
          background: step.is_error ? '#ff6b6b' : '#51cf66',
          color: 'white'
        }
      }
    }));

    const edges = workflowSteps.slice(0, -1).map((step, index) => ({
      id: `e${index}-${index + 1}`,
      source: step.step_number.toString(),
      target: (step.step_number + 1).toString(),
      animated: true
    }));

    return { nodes, edges };
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Request Workflow Visualization
        </Typography>
        <div style={{ height: 400 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            attributionPosition="top-right"
          />
        </div>
      </CardContent>
    </Card>
  );
};
```

## 🌐 API Integration

### Data Provider Configuration
```typescript
// providers/dataProvider.tsx
import { DataProvider } from 'react-admin';
import axios from 'axios';

const apiUrl = 'http://localhost:8000/api/v1';

export const dataProvider: DataProvider = {
  getList: (resource, params) => {
    return axios.get(`${apiUrl}/${resource}`, { params })
      .then(({ data }) => ({ data: data.data, total: data.total }));
  },
  
  getOne: (resource, params) => {
    return axios.get(`${apiUrl}/${resource}/${params.id}`)
      .then(({ data }) => ({ data }));
  },
  
  // Add other CRUD methods...
};
```

### WebSocket Integration
```typescript
// utils/websocket.ts
export class DashboardWebSocket {
  private ws: WebSocket | null = null;
  private listeners: ((data: any) => void)[] = [];

  connect() {
    this.ws = new WebSocket('ws://localhost:8000/api/v1/dashboard/ws');
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.listeners.forEach(listener => listener(data));
    };
  }

  subscribe(callback: (data: any) => void) {
    this.listeners.push(callback);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

## 🎨 UI Features

### Responsive Design
- Material-UI components for professional appearance
- Responsive grid layout that works on all devices
- Dark/light theme support

### Interactive Charts
- Hover tooltips with detailed information
- Zoom and pan capabilities
- Real-time data updates
- Export functionality

### Workflow Visualization
- Interactive flow diagrams using React Flow
- Drag and drop interface
- Agent interaction timelines
- Error highlighting

### Performance Monitoring
- Real-time KPI cards
- System health indicators
- Alert notifications
- Historical trend analysis

## 🚀 Running the Dashboard

### Development Mode
```bash
npm start
# Opens http://localhost:3000
```

### Production Build
```bash
npm run build
npm install -g serve
serve -s build -l 3000
```

## 🔧 Configuration

### Environment Variables
```bash
# .env
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_WS_URL=ws://localhost:8000/api/v1/dashboard/ws
REACT_APP_REFRESH_INTERVAL=30000
```

### API Endpoints Used
- `GET /dashboard/metrics/overview` - KPI metrics
- `GET /dashboard/charts/request-timeline` - Request volume data
- `GET /dashboard/charts/agent-performance` - Agent performance data
- `GET /dashboard/workflow/requests` - Workflow data
- `WS /dashboard/ws` - Real-time updates

## 📊 Available Visualizations

1. **Request Timeline**: Line chart showing request volume over time
2. **Agent Performance**: Bar chart with error rates and response times
3. **Tool Usage**: Pie chart showing tool utilization
4. **Error Analysis**: Stacked bar chart of errors by type and agent
5. **Workflow Diagrams**: Interactive flow charts of request processing
6. **System Health**: Real-time status indicators
7. **Audit Trail**: Searchable data table with filters

## 🎯 Next Steps

1. Run `npm install` in the created project
2. Copy the component files from this guide
3. Configure API endpoints
4. Start development server
5. Access dashboard at http://localhost:3000

The dashboard will provide complete visibility into your agent interactions with beautiful, responsive charts and real-time monitoring capabilities! 