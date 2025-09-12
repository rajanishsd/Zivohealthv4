import React, { useState, useEffect } from 'react';
import './App.css';
import DynamicWorkflowVisualization from './components/DynamicWorkflowVisualization';

// API base URL: use env override if provided, otherwise use relative URLs (same origin)
const API_BASE = (process.env.REACT_APP_API_BASE_URL || '');
const apiUrl = (path: string) => `${API_BASE}${path}`;

interface UserSession {
  session_id: string;
  user_id: string;
  start_time: string;
  end_time: string;
  total_messages: number;
  agents_involved: string[];
  session_status: string;
}

interface WorkflowAuditEntry {
  request_id: string;
  user_id: string;
  session_id: string;
  timestamp: string;
  user_message: string;
  agent_workflow: WorkflowStep[];
  hierarchical_lineage?: any[];
  duration_ms: number;
  status: 'success' | 'error' | 'pending';
  agents_involved: string[];
  tools_used: string[];
}

interface WorkflowStep {
  step_number: number;
  timestamp: string;
  agent_name: string;
  event_type: string;
  message: string;
  details: any;
  tool_used?: string;
  execution_time_ms?: number;
  is_error: boolean;
}

interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  user: any | null;
}

interface SystemHealth {
  status: string;
  status_color: string;
  health_score: number;
  issues: string[];
  current_metrics: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    memory_gb: number;
    memory_total_gb: number;
    disk_gb: number;
    disk_total_gb: number;
  };
  recent_requests: number;
  error_rate: number;
  avg_response_time_ms: number;
}

interface PerformanceOverview {
  overview: {
    requests_per_hour: number;
    avg_response_time_ms: number;
    p95_response_time_ms: number;
    error_rate: number;
    error_count: number;
  };
  endpoint_stats: Array<{
    endpoint: string;
    request_count: number;
    avg_response_time_ms: number;
    error_rate: number;
    methods: string[];
  }>;
}

function App() {
  const [activeTab, setActiveTab] = useState('system');
  const [userSessions, setUserSessions] = useState<UserSession[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [performanceOverview, setPerformanceOverview] = useState<PerformanceOverview | null>(null);
  const [auth, setAuth] = useState<AuthState>({
    isAuthenticated: false,
    token: null,
    user: null
  });
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: ''
  });
  const [loginMode, setLoginMode] = useState<'password' | 'otp'>('password');
  const [otpCode, setOtpCode] = useState('');
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState('');
  const [forgotPasswordMessage, setForgotPasswordMessage] = useState('');
  const [loginError, setLoginError] = useState('');
  const [workflowAudits, setWorkflowAudits] = useState<WorkflowAuditEntry[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowAuditEntry | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [auditTimeRange, setAuditTimeRange] = useState(24); // hours
  const [isRefreshing, setIsRefreshing] = useState({
    system: false,
    app: false,
    agent: false,
    audit: false
  });
  const [selectedAgent, setSelectedAgent] = useState<string>('enhanced_customer');
  const [workflowViewType, setWorkflowViewType] = useState<'hierarchical' | 'chronological'>('hierarchical');

  // Check for existing token on app load
  useEffect(() => {
    const token = localStorage.getItem('dashboard_token');
    const user = localStorage.getItem('dashboard_user');
    if (token && user) {
      setAuth({
        isAuthenticated: true,
        token,
        user: JSON.parse(user)
      });
    }
  }, []);

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    
    try {
      if (loginMode === 'password') {
        const formData = new FormData();
        formData.append('username', loginForm.username);
        formData.append('password', loginForm.password);
        
        const response = await fetch(apiUrl('/api/v1/auth/login'), {
          method: 'POST',
          body: formData
        });
        
        if (response.ok) {
          const data = await response.json();
          const authState = {
            isAuthenticated: true,
            token: data.access_token,
            user: data.user || { username: loginForm.username }
          };
          
          setAuth(authState);
          localStorage.setItem('dashboard_token', data.access_token);
          localStorage.setItem('dashboard_user', JSON.stringify(authState.user));
          
          setLoginForm({ username: '', password: '' });
        } else {
          const errorData = await response.json();
          setLoginError(errorData.detail || 'Login failed');
        }
      } else {
        const response = await fetch(apiUrl('/api/v1/auth/email/otp/verify'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: loginForm.username, code: otpCode })
        });
        
        if (response.ok) {
          const data = await response.json();
          const authState = {
            isAuthenticated: true,
            token: data.access_token,
            user: data.user || { username: loginForm.username }
          };
          setAuth(authState);
          localStorage.setItem('dashboard_token', data.access_token);
          localStorage.setItem('dashboard_user', JSON.stringify(authState.user));
          setLoginForm({ username: '', password: '' });
          setOtpCode('');
        } else {
          const errorData = await response.json();
          setLoginError(errorData.detail || 'OTP verification failed');
        }
      }
    } catch (error) {
      setLoginError('Network error. Please try again.');
      console.error('Login error:', error);
    }
  };

  const requestOtp = async () => {
    setLoginError('');
    try {
      const response = await fetch(apiUrl('/api/v1/auth/email/otp/request'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginForm.username })
      });
      if (response.ok) {
        setLoginMode('otp');
      } else {
        const errorData = await response.json();
        setLoginError(errorData.detail || 'Failed to request OTP');
      }
    } catch (e) {
      setLoginError('Network error requesting OTP');
    }
  };

  const requestPasswordReset = async () => {
    setForgotPasswordMessage('');
    setLoginError('');
    try {
      const response = await fetch(apiUrl('/api/v1/auth/forgot-password'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotPasswordEmail || loginForm.username })
      });
      if (response.ok) {
        setForgotPasswordMessage('If the email exists, a reset link was sent.');
      } else {
        setForgotPasswordMessage('If the email exists, a reset link was sent.');
      }
    } catch (e) {
      setLoginError('Network error requesting password reset');
    }
  };

  const logout = () => {
    setAuth({
      isAuthenticated: false,
      token: null,
      user: null
    });
    localStorage.removeItem('dashboard_token');
    localStorage.removeItem('dashboard_user');
  };

  const getAuthHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = {};
    if (auth.token) {
      headers['Authorization'] = `Bearer ${auth.token}`;
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  };

  const fetchUserSessions = async () => {
    if (!auth.isAuthenticated) return;
    
    setIsRefreshing(prev => ({ ...prev, agent: true }));
    try {
      const response = await fetch(apiUrl('/api/v1/chat-sessions/statistics'), {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('Authentication failed for chat sessions, logging out...');
        logout();
        return;
      }
      
      const data = await response.json();
      // Ensure each session has all required properties with defaults
      const sessionsWithDefaults = (data.sessions || []).map((session: any) => ({
        session_id: session.session_id || '',
        user_id: session.user_id || '',
        start_time: session.start_time || '',
        end_time: session.end_time || '',
        total_messages: session.total_messages || 0,
        agents_involved: session.agents_involved || [],
        session_status: session.session_status || 'unknown'
      }));
      setUserSessions(sessionsWithDefaults);
    } catch (error) {
      console.error('Error fetching user sessions:', error);
      setUserSessions([]); // Set empty array on error to prevent crashes
    } finally {
      setIsRefreshing(prev => ({ ...prev, agent: false }));
    }
  };

  const fetchSystemHealth = async () => {
    setIsRefreshing(prev => ({ ...prev, system: true }));
    try {
      const response = await fetch(apiUrl('/dashboard/monitoring/system-health'), {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('Authentication failed for system health, logging out...');
        logout();
        return;
      }
      
      const data = await response.json();
      setSystemHealth(data);
    } catch (error) {
      console.error('Error fetching system health:', error);
    } finally {
      setIsRefreshing(prev => ({ ...prev, system: false }));
    }
  };

  const fetchPerformanceOverview = async () => {
    setIsRefreshing(prev => ({ ...prev, app: true }));
    try {
      const response = await fetch(apiUrl('/dashboard/metrics/overview'), {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('Authentication failed for performance overview, logging out...');
        logout();
        return;
      }
      
      const data = await response.json();
      // Transform the data to match the expected PerformanceOverview interface
      const transformedData = {
        overview: {
          requests_per_hour: data.total_requests || 0,
          avg_response_time_ms: data.avg_response_time || 0,
          p95_response_time_ms: data.avg_response_time * 1.5 || 0, // Approximate p95
          error_rate: data.error_rate || 0,
          error_count: Math.round((data.error_rate || 0) * (data.total_interactions || 0))
        },
        endpoint_stats: [] // We'll need to update this when we have endpoint-specific data
      };
      setPerformanceOverview(transformedData);
    } catch (error) {
      console.error('Error fetching performance overview:', error);
    } finally {
      setIsRefreshing(prev => ({ ...prev, app: false }));
    }
  };

  const fetchWorkflowAudits = async (userId?: string) => {
    if (!auth.isAuthenticated) return;
    
    setIsRefreshing(prev => ({ ...prev, audit: true }));
    try {
      let url = apiUrl(`/api/v1/dashboard/workflow/requests?hours=${auditTimeRange}&limit=100`);
      if (userId) {
        url += `&user_id=${userId}`;
      }
      
      const response = await fetch(url, {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('Authentication failed for workflow audits, logging out...');
        logout();
        return;
      }
      
      const data = await response.json();
      
      // Transform the data to match our interface
      const auditEntries: WorkflowAuditEntry[] = await Promise.all(
        data.requests.map(async (req: any) => {
          // Fetch detailed workflow for each request
          try {
            const detailResponse = await fetch(
              apiUrl(`/api/v1/dashboard/workflow/request/${req.id}`),
              { headers: getAuthHeaders() }
            );
            
            if (detailResponse.ok) {
              const detailData = await detailResponse.json();
              
              return {
                request_id: req.id,
                user_id: detailData.user_id?.toString() || 'unknown',
                session_id: detailData.session_id?.toString() || 'unknown',
                timestamp: req.timestamp,
                user_message: req.user_message,
                agent_workflow: detailData.lineage?.map((step: any, index: number) => ({
                  step_number: index + 1,
                  timestamp: step.timestamp,
                  agent_name: step.agent_name,
                  event_type: step.operation,
                  message: step.operation,
                  details: step.metadata || {},
                  tool_used: step.metadata?.tool_used,
                  execution_time_ms: step.duration_ms,
                  is_error: step.status === 'ERROR'
                })) || [],
                hierarchical_lineage: detailData.hierarchical_lineage || null,
                duration_ms: req.duration_ms,
                status: req.status,
                agents_involved: req.agents_involved,
                tools_used: req.tools_used
              };
            } else {
              // Fallback for requests without detailed workflow
              return {
                request_id: req.id,
                user_id: 'unknown',
                session_id: 'unknown',
                timestamp: req.timestamp,
                user_message: req.user_message,
                agent_workflow: [],
                duration_ms: req.duration_ms,
                status: req.status,
                agents_involved: req.agents_involved,
                tools_used: req.tools_used
              };
            }
          } catch (error) {
            console.error('Error fetching workflow details:', error);
            return {
              request_id: req.id,
              user_id: 'unknown',
              session_id: 'unknown',
              timestamp: req.timestamp,
              user_message: req.user_message,
              agent_workflow: [],
              duration_ms: req.duration_ms,
              status: req.status,
              agents_involved: req.agents_involved,
              tools_used: req.tools_used
            };
          }
        })
      );
      
      setWorkflowAudits(auditEntries);
    } catch (error) {
      console.error('Error fetching workflow audits:', error);
      setWorkflowAudits([]);
    } finally {
      setIsRefreshing(prev => ({ ...prev, audit: false }));
    }
  };

  useEffect(() => {
    if (auth.isAuthenticated) {
      fetchUserSessions();
      fetchSystemHealth();
      fetchPerformanceOverview();
      fetchWorkflowAudits();
      
      // Set up polling for real-time updates
      const interval = setInterval(() => {
        fetchSystemHealth();
        fetchPerformanceOverview();
        fetchUserSessions();
        fetchWorkflowAudits();
      }, 30000); // Update every 30 seconds
      
      return () => clearInterval(interval);
    }
  }, [auth.isAuthenticated, auditTimeRange]);

  // Render System Monitoring Page
  const renderSystemMonitoring = () => (
    <div className="monitoring-section">
      <div className="section-header">
        <div className="section-title">System Performance Monitoring</div>
        <button 
          className={`refresh-button ${isRefreshing.system ? 'refreshing' : ''}`} 
          onClick={fetchSystemHealth} 
          disabled={isRefreshing.system}
          title="Refresh System Metrics"
        >
          {isRefreshing.system ? '⏳' : '🔄'}
        </button>
      </div>
      
      {/* System Metrics */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">
            {systemHealth ? `${systemHealth.current_metrics.cpu_percent.toFixed(1)}%` : '--'}
          </div>
          <div className="stat-label">CPU Usage</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {systemHealth ? `${systemHealth.current_metrics.memory_percent.toFixed(1)}%` : '--'}
          </div>
          <div className="stat-label">Memory Usage</div>
          {systemHealth && (
            <div className="stat-detail">
              {systemHealth.current_metrics.memory_gb.toFixed(1)}GB used of {systemHealth.current_metrics.memory_total_gb.toFixed(1)}GB
            </div>
          )}
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {systemHealth ? `${systemHealth.current_metrics.disk_percent.toFixed(1)}%` : '--'}
          </div>
          <div className="stat-label">Disk Usage</div>
          {systemHealth && (
            <div className="stat-detail">
              {systemHealth.current_metrics.disk_gb.toFixed(1)}GB used of {systemHealth.current_metrics.disk_total_gb.toFixed(1)}GB
            </div>
          )}
        </div>
      </div>

      {/* System Issues (if any) */}
      {systemHealth && systemHealth.issues.length > 0 && (
        <div className="system-issues">
          <div className="section-title">System Issues</div>
          <div className="issues-list">
            {systemHealth.issues.map((issue, index) => (
              <div key={index} className="issue-item">
                <span className="issue-icon">⚠️</span>
                <span className="issue-text">{issue}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );

  // Render App Monitoring Page  
  const renderAppMonitoring = () => (
    <div className="monitoring-section">
      <div className="section-header">
        <div className="section-title">Application Performance Monitoring</div>
        <button 
          className={`refresh-button ${isRefreshing.app ? 'refreshing' : ''}`} 
          onClick={fetchPerformanceOverview} 
          disabled={isRefreshing.app}
          title="Refresh App Metrics"
        >
          {isRefreshing.app ? '⏳' : '🔄'}
        </button>
      </div>
      
      {performanceOverview && (
        <>
          {/* App Overview Metrics */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number">{performanceOverview.endpoint_stats.length}</div>
              <div className="stat-label">Active Endpoints</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{performanceOverview.overview.error_count}</div>
              <div className="stat-label">Total Errors</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{(performanceOverview.overview.error_rate * 100).toFixed(2)}%</div>
              <div className="stat-label">Error Rate</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{performanceOverview.overview.requests_per_hour.toFixed(1)}</div>
              <div className="stat-label">Requests/Hour</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{performanceOverview.overview.avg_response_time_ms.toFixed(0)}ms</div>
              <div className="stat-label">Avg Response Time</div>
              <div className="stat-detail">
                P95: {performanceOverview.overview.p95_response_time_ms.toFixed(0)}ms
              </div>
            </div>
          </div>

          {/* Top Endpoints Table */}
          <div className="section-title">Top Endpoints Performance</div>
          <div className="endpoints-table">
            <div className="table-header">
              <div>Endpoint</div>
              <div>Requests</div>
              <div>Avg Time</div>
              <div>Error Rate</div>
              <div>Methods</div>
            </div>
            {performanceOverview.endpoint_stats.map((endpoint, index) => (
              <div key={index} className="table-row">
                <div className="endpoint-path">{endpoint.endpoint}</div>
                <div>{endpoint.request_count}</div>
                <div>{endpoint.avg_response_time_ms.toFixed(0)}ms</div>
                <div className={endpoint.error_rate > 0.05 ? 'error-rate-high' : 'error-rate-low'}>
                  {(endpoint.error_rate * 100).toFixed(1)}%
                </div>
                <div className="methods">{endpoint.methods.join(', ')}</div>
              </div>
            ))}
          </div>
        </>
      )}

    </div>
  );

  // Render Agent Monitoring Page
  const renderAgentMonitoring = () => (
    <div className="monitoring-section">
      <div className="section-header">
        <div className="section-title">Agent Performance Monitoring</div>
        <button 
          className={`refresh-button ${isRefreshing.agent ? 'refreshing' : ''}`} 
          onClick={fetchUserSessions} 
          disabled={isRefreshing.agent}
          title="Refresh Agent Metrics"
        >
          {isRefreshing.agent ? '⏳' : '🔄'}
        </button>
      </div>
      
      {/* Agent Statistics */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">{userSessions.length > 0 ? userSessions.length : '--'}</div>
          <div className="stat-label">Total Sessions</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {userSessions.length > 0 ? userSessions.reduce((total, session) => total + session.total_messages, 0) : '--'}
          </div>
          <div className="stat-label">Total Messages</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">2</div>
          <div className="stat-label">Active Agents</div>
          <div className="stat-detail">CustomerAgent, DoctorAgent</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {userSessions.length > 0 ? userSessions.filter(s => s.session_status === 'active').length : '--'}
          </div>
          <div className="stat-label">Active Sessions</div>
        </div>
      </div>

      {/* Recent Sessions Table */}
      {userSessions.length > 0 && (
        <>
          <div className="section-title">Recent Chat Sessions</div>
          <div className="sessions-table">
            <div className="table-header">
              <div>Session ID</div>
              <div>User ID</div>
              <div>Start Time</div>
              <div>Messages</div>
              <div>Agents</div>
              <div>Status</div>
            </div>
            {userSessions.slice(0, 10).map((session, index) => (
              <div key={index} className="table-row">
                <div className="session-id">#{session.session_id}</div>
                <div>{session.user_id}</div>
                <div>{new Date(session.start_time).toLocaleString()}</div>
                <div>{session.total_messages}</div>
                <div className="methods">{session.agents_involved.join(', ')}</div>
                <div>
                  <span className={`status-badge ${session.session_status}`}>
                    {session.session_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

    </div>
  );

  // Render Workflow Audit Page
  const renderWorkflowAudit = () => (
    <div className="monitoring-section">
      <div className="section-header">
        <div className="section-title">Workflow Audit</div>
        <div className="audit-controls">
          <select 
            value={auditTimeRange} 
            onChange={(e) => setAuditTimeRange(Number(e.target.value))}
            className="time-range-select"
          >
            <option value={1}>Last Hour</option>
            <option value={24}>Last 24 Hours</option>
            <option value={168}>Last Week</option>
            <option value={720}>Last Month</option>
          </select>
          <button 
            className={`refresh-button ${isRefreshing.audit ? 'refreshing' : ''}`}
            onClick={() => fetchWorkflowAudits(selectedUserId)}
            disabled={isRefreshing.audit}
            title="Refresh Workflow Audits"
          >
            {isRefreshing.audit ? '⏳' : '🔄'}
          </button>
        </div>
      </div>
      
      {/* Existing workflow audit content */}
      <div className="workflow-stats-grid">
        <div className="stat-card">
          <div className="stat-number">{workflowAudits.length}</div>
          <div className="stat-label">Total Requests</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {workflowAudits.length > 0 ? new Set(workflowAudits.map(w => w.user_id)).size : 0}
          </div>
          <div className="stat-label">Unique Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {workflowAudits.filter(w => w.status === 'success').length}
          </div>
          <div className="stat-label">Successful Workflows</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">
            {workflowAudits.filter(w => w.status === 'error').length}
          </div>
          <div className="stat-label">Failed Workflows</div>
        </div>
      </div>

      {/* Workflow Requests Table */}
      {workflowAudits.length > 0 && (
        <>
          <div className="section-title">Recent Workflow Requests</div>
          <div className="workflow-table">
            <div className="table-header">
              <div>Request ID</div>
              <div>User ID</div>
              <div>Timestamp</div>
              <div>Message Preview</div>
              <div>Agents</div>
              <div>Duration</div>
              <div>Status</div>
              <div>Actions</div>
            </div>
            {workflowAudits.slice(0, 20).map((workflow, index) => (
              <div key={index} className="table-row">
                <div className="request-id">#{workflow.request_id.slice(0, 8)}</div>
                <div>{workflow.user_id}</div>
                <div>{new Date(workflow.timestamp).toLocaleString()}</div>
                <div className="message-preview" title={workflow.user_message}>
                  {workflow.user_message.length > 50 
                    ? workflow.user_message.slice(0, 50) + '...' 
                    : workflow.user_message}
                </div>
                <div className="methods">{workflow.agents_involved.join(', ')}</div>
                <div>{workflow.duration_ms}ms</div>
                <div>
                  <span className={`status-badge ${workflow.status}`}>
                    {workflow.status}
                  </span>
                </div>
                <div>
                  <button 
                    className="view-workflow-btn"
                    onClick={() => setSelectedWorkflow(workflow)}
                  >
                    View Workflow
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Workflow Detail Modal */}
      {selectedWorkflow && (
        <div className="workflow-modal-overlay" onClick={() => setSelectedWorkflow(null)}>
          <div className="workflow-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Workflow Details - Request #{selectedWorkflow.request_id.slice(0, 8)}</h3>
              <button className="close-btn" onClick={() => setSelectedWorkflow(null)}>×</button>
            </div>
            
            <div className="modal-content">
              <div className="workflow-summary">
                <div className="summary-item">
                  <strong>User ID:</strong> {selectedWorkflow.user_id}
                </div>
                <div className="summary-item">
                  <strong>Session ID:</strong> {selectedWorkflow.session_id}
                </div>
                <div className="summary-item">
                  <strong>Timestamp:</strong> {new Date(selectedWorkflow.timestamp).toLocaleString()}
                </div>
                <div className="summary-item">
                  <strong>Duration:</strong> {selectedWorkflow.duration_ms}ms
                </div>
                <div className="summary-item">
                  <strong>Status:</strong> 
                  <span className={`status-badge ${selectedWorkflow.status}`}>
                    {selectedWorkflow.status}
                  </span>
                </div>
              </div>

              <div className="user-message-section">
                <h4>User Message:</h4>
                <div className="user-message">{selectedWorkflow.user_message}</div>
              </div>

              <div className="workflow-steps-section">
                <h4>Agent Workflow Steps:</h4>
                
                {/* Add toggle for hierarchical vs chronological view */}
                <div className="view-toggle" style={{ marginBottom: '20px' }}>
                  <label>
                    <input
                      type="radio"
                      name="viewType"
                      value="hierarchical"
                      checked={workflowViewType === 'hierarchical'}
                      onChange={(e) => setWorkflowViewType('hierarchical')}
                    />
                    Hierarchical View (Orchestration)
                  </label>
                  <label style={{ marginLeft: '20px' }}>
                    <input
                      type="radio"
                      name="viewType"
                      value="chronological"
                      checked={workflowViewType === 'chronological'}
                      onChange={(e) => setWorkflowViewType('chronological')}
                    />
                    Chronological View (Timeline)
                  </label>
                </div>

                {workflowViewType === 'hierarchical' ? (
                  // Hierarchical view
                  <div className="hierarchical-workflow">
                    {selectedWorkflow.hierarchical_lineage ? (
                      renderHierarchicalWorkflow(selectedWorkflow.hierarchical_lineage)
                    ) : (
                      <div className="no-hierarchy">
                        <p>Hierarchical data not available for this request.</p>
                        <p>Showing chronological view:</p>
                        {renderChronologicalWorkflow(selectedWorkflow.agent_workflow)}
                      </div>
                    )}
                  </div>
                ) : (
                  // Chronological view
                  <div className="workflow-steps">
                    {renderChronologicalWorkflow(selectedWorkflow.agent_workflow)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );

  // Add new render function for Agent Workflows section
  const renderAgentWorkflows = () => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <DynamicWorkflowVisualization 
        selectedAgent={selectedAgent} 
        onAgentChange={setSelectedAgent}
      />
    </div>
  );

  // Helper function to render chronological workflow
  const renderChronologicalWorkflow = (workflow: any[]) => (
    workflow.map((step, index) => (
      <div key={index} className={`workflow-step ${step.is_error ? 'error' : ''}`}>
        <div className="step-header">
          <span className="step-number">{step.step_number}</span>
          <span className="step-agent">{step.agent_name}</span>
          <span className="step-event">{step.event_type}</span>
          <span className="step-time">{new Date(step.timestamp).toLocaleTimeString()}</span>
          {step.execution_time_ms && (
            <span className="step-duration">{step.execution_time_ms}ms</span>
          )}
        </div>
        <div className="step-message">{step.message}</div>
        {step.tool_used && (
          <div className="step-tool">Tool: {step.tool_used}</div>
        )}
        {step.details && Object.keys(step.details).length > 0 && (
          <details className="step-details">
            <summary>Details</summary>
            <pre>{JSON.stringify(step.details, null, 2)}</pre>
          </details>
        )}
      </div>
    ))
  );

  // Helper function to render hierarchical workflow
  const renderHierarchicalWorkflow = (hierarchicalData: any[], level: number = 0) => (
    <div className="hierarchical-steps" style={{ marginLeft: `${level * 30}px` }}>
      {hierarchicalData.map((node, index) => (
        <div key={index} className={`hierarchical-step ${node.status === 'ERROR' ? 'error' : ''}`}>
          <div className="step-header">
            <span className="step-level">L{level}</span>
            <span className="step-agent">{node.agent_name}</span>
            <span className="step-operation">{node.operation}</span>
            <span className="step-time">{new Date(node.timestamp).toLocaleTimeString()}</span>
            {node.duration_ms > 0 && (
              <span className="step-duration">{node.duration_ms}ms</span>
            )}
            {node.orchestrator && level > 0 && (
              <span className="orchestrator">← {node.orchestrator}</span>
            )}
          </div>
          
          {/* Enhanced Message Content Display */}
          {node.message_content && Object.keys(node.message_content).length > 0 && (
            <div className="step-messages">
              {node.message_content.user_message && (
                <div className="message-item user-message">
                  <span className="message-label">📝 User:</span>
                  <span className="message-content">{node.message_content.user_message}</span>
                </div>
              )}
              
              {node.message_content.message_type && (
                <div className="message-item interaction-type">
                  <span className="message-label">🔄 Type:</span>
                  <span className="message-content">{node.message_content.message_type}</span>
                </div>
              )}
              
              {node.message_content.operation_type && (
                <div className="message-item operation-type">
                  <span className="message-label">⚙️ Operation:</span>
                  <span className="message-content">{node.message_content.operation_type}</span>
                </div>
              )}
              
              {node.message_content.classified_domain && (
                <div className="message-item classification">
                  <span className="message-label">🎯 Classified as:</span>
                  <span className="message-content">{node.message_content.classified_domain}</span>
                </div>
              )}
              
              {node.message_content.coordination_mode && (
                <div className="message-item coordination">
                  <span className="message-label">🤝 Coordination:</span>
                  <span className="message-content">{node.message_content.coordination_mode}</span>
                </div>
              )}
              
              {node.message_content.guardrails_safe !== undefined && (
                <div className={`message-item guardrails ${node.message_content.guardrails_safe ? 'safe' : 'unsafe'}`}>
                  <span className="message-label">🛡️ Guardrails:</span>
                  <span className="message-content">
                    {node.message_content.guardrails_safe ? '✅ Safe' : '❌ Blocked'}
                    {node.message_content.guardrails_violations && 
                      ` (${node.message_content.guardrails_violations} violations)`}
                  </span>
                </div>
              )}
              
              {node.message_content.tests_extracted && (
                <div className="message-item medical-data">
                  <span className="message-label">🧪 Lab Data:</span>
                  <span className="message-content">
                    {node.message_content.tests_extracted} tests extracted
                    {node.message_content.abnormal_tests && 
                      `, ${node.message_content.abnormal_tests} abnormal`}
                  </span>
                </div>
              )}
              
              {node.message_content.agents_used && (
                <div className="message-item agents-summary">
                  <span className="message-label">👥 Agents Used:</span>
                  <span className="message-content">{node.message_content.agents_used} agents</span>
                </div>
              )}
              
              {node.message_content.routing_time && (
                <div className="message-item timing">
                  <span className="message-label">⏱️ Routing Time:</span>
                  <span className="message-content">{node.message_content.routing_time}</span>
                </div>
              )}
              
              {node.message_content.success !== undefined && (
                <div className={`message-item status ${node.message_content.success ? 'success' : 'error'}`}>
                  <span className="message-label">📊 Result:</span>
                  <span className="message-content">
                    {node.message_content.success ? '✅ Success' : '❌ Failed'}
                  </span>
                </div>
              )}
              
              {node.message_content.error && (
                <div className="message-item error-info">
                  <span className="message-label">❌ Error:</span>
                  <span className="message-content">{node.message_content.error}</span>
                </div>
              )}
            </div>
          )}
          
          {/* Original metadata details (collapsed by default) */}
          {node.metadata && Object.keys(node.metadata).length > 0 && (
            <details className="step-details">
              <summary>Technical Details</summary>
              <pre>{JSON.stringify(node.metadata, null, 2)}</pre>
            </details>
          )}
          
          {/* Recursively render children */}
          {node.children && node.children.length > 0 && (
            <div className="child-steps">
              {renderHierarchicalWorkflow(node.children, level + 1)}
            </div>
          )}
        </div>
      ))}
    </div>
  );

  // Login component
  if (!auth.isAuthenticated) {
    return (
      <div className="login-container">
        <div className="login-form">
          <h2>🏥 ZivoHealth Dashboard</h2>
          <p>Please login to access the admin dashboard</p>
          
          <form onSubmit={login}>
            <div className="form-group">
              <label>Username:</label>
              <input
                type="text"
                value={loginForm.username}
                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                placeholder="Enter your username"
                required
              />
            </div>
            
            {loginMode === 'password' && (
              <div className="form-group">
                <label>Password:</label>
                <input
                  type="password"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                  placeholder="Enter your password"
                  required
                />
              </div>
            )}

            {loginMode === 'otp' && (
              <div className="form-group">
                <label>One-Time Password (OTP):</label>
                <input
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="Enter the OTP sent to your email"
                  required
                />
              </div>
            )}
            
            {loginError && (
              <div className="error-message">
                {loginError}
              </div>
            )}
            
            <button type="submit" className="login-button">
              {loginMode === 'password' ? 'Login' : 'Verify OTP'}
            </button>

            {loginMode === 'password' && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button type="button" className="login-button" style={{ background: '#6c757d', width: '48%' }} onClick={requestOtp}>
                  Login with OTP
                </button>
                <button type="button" className="login-button" style={{ background: '#17a2b8', width: '48%' }} onClick={requestPasswordReset}>
                  Forgot Password
                </button>
              </div>
            )}

            {loginMode === 'otp' && (
              <div style={{ marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#6c757d' }} onClick={() => setLoginMode('password')}>
                  Back to Password Login
                </button>
              </div>
            )}
          </form>

          {forgotPasswordMessage && (
            <div className="demo-credentials" style={{ marginTop: 12 }}>
              <p>{forgotPasswordMessage}</p>
            </div>
          )}
          
          <div className="demo-credentials">
            <p><strong>Demo Credentials:</strong></p>
            <p>Username: patient@zivohealth.com</p>
            <p>Password: patient123</p>
          </div>
        </div>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">🏥 ZivoHealth Monitoring Dashboard</h1>
          <div className="header-right">
            {/* System Health Status */}
            {systemHealth && systemHealth.status && (
              <div className="health-status-compact">
                <div className={`status-dot ${systemHealth.status}`}></div>
                <span className="status-text">
                  {systemHealth.status.toUpperCase()} • {systemHealth.health_score || 0}%
                </span>
              </div>
            )}
            <div className="user-info">
              <span>Welcome, {auth.user?.username || 'User'}</span>
              <button onClick={logout} className="logout-button">Logout</button>
            </div>
          </div>
        </div>
      </header>

      <div className="app-body">
        {/* Left Navigation */}
        <nav className="left-nav">
          <div className="nav-items">
            <button 
              className={`nav-item ${activeTab === 'system' ? 'active' : ''}`}
              onClick={() => setActiveTab('system')}
            >
              <span className="nav-icon">🖥️</span>
              <span className="nav-label">System Monitoring</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'app' ? 'active' : ''}`}
              onClick={() => setActiveTab('app')}
            >
              <span className="nav-icon">📊</span>
              <span className="nav-label">App Monitoring</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'agent' ? 'active' : ''}`}
              onClick={() => setActiveTab('agent')}
            >
              <span className="nav-icon">🤖</span>
              <span className="nav-label">Agent Monitoring</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'workflows' ? 'active' : ''}`}
              onClick={() => setActiveTab('workflows')}
            >
              <span className="nav-icon">🔍</span>
              <span className="nav-label">Agent Workflows</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'audit' ? 'active' : ''}`}
              onClick={() => setActiveTab('audit')}
            >
              <span className="nav-icon">🔍</span>
              <span className="nav-label">Workflow Audit</span>
            </button>
          </div>
        </nav>

        <main className="app-main">
          {activeTab === 'system' && renderSystemMonitoring()}
          {activeTab === 'app' && renderAppMonitoring()}
          {activeTab === 'agent' && renderAgentMonitoring()}
          {activeTab === 'workflows' && renderAgentWorkflows()}
          {activeTab === 'audit' && renderWorkflowAudit()}
        </main>
      </div>
    </div>
  );
}

export default App;
