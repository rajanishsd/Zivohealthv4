import React, { useState, useEffect } from 'react';
import './App.css';
import { hmacGenerator } from './utils/hmac';
import HealthScoreOps from './components/HealthScoreOps';
import AdminManagement from './components/AdminManagement';
import AdminPasswordReset from './components/AdminPasswordReset';

// API base URL: use env override if provided, otherwise use relative URLs (same origin)
const API_BASE = (process.env.REACT_APP_API_BASE_URL || '');
const API_KEY = (process.env.REACT_APP_API_KEY || '');
const apiUrl = (path: string) => `${API_BASE}${path}`;




interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  user: any | null;
  isSuperAdmin?: boolean;
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

// Feedback types
interface FeedbackItem {
  id: string;
  user_id?: number | null;
  submitter_role?: string | null; // "user" | "doctor"
  submitter_name?: string | null;
  s3_key: string;
  category?: string | null;
  description?: string | null;
  route?: string | null;
  app_version?: string | null;
  build_number?: string | null;
  platform?: string | null;
  os_version?: string | null;
  device_model?: string | null;
  app_identifier?: string | null;
  status: string;
  closed_date?: string | null;
  extra?: Record<string, any> | null;
  created_at?: string;
  updated_at?: string;
}

function App() {
  const [activeTab, setActiveTab] = useState('system');
  // Users management state
  const [users, setUsers] = useState<Array<any>>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [selectAllUsers, setSelectAllUsers] = useState(false);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [performanceOverview, setPerformanceOverview] = useState<PerformanceOverview | null>(null);
  const [auth, setAuth] = useState<AuthState>({
    isAuthenticated: false,
    token: null,
    user: null,
    isSuperAdmin: false
  });
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: ''
  });
  const [loginMode, setLoginMode] = useState<'password' | 'otp' | 'otp-enter' | 'forgot-password'>('password');
  const [otpCode, setOtpCode] = useState('');
  const [otpEmail, setOtpEmail] = useState('');
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState('');
  const [forgotPasswordMessage, setForgotPasswordMessage] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState({
    system: false,
    app: false
  });

  // Check if we're on the password reset page
  const urlParams = new URLSearchParams(window.location.search);
  const resetToken = urlParams.get('token');
  const [showPasswordReset, setShowPasswordReset] = useState(!!resetToken);

  // Feedback state
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [isLoadingFeedback, setIsLoadingFeedback] = useState(false);
  const [editingFeedback, setEditingFeedback] = useState<string | null>(null);
  const [tempStatus, setTempStatus] = useState<string>('');
  const [updatingFeedback, setUpdatingFeedback] = useState<string | null>(null);
  const [feedbackFilters, setFeedbackFilters] = useState({
    role: 'all' as 'all' | 'user' | 'doctor',
    status: 'all' as 'all' | 'open' | 'in_progress' | 'resolved',
    category: 'all' as string,
    search: '' as string,
    startDate: '' as string,
    endDate: '' as string,
  });

  // Check for existing token on app load
  // Helper function to fetch current admin info (including isSuperAdmin flag)
  const fetchAdminInfo = async (token: string) => {
    try {
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };
      
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }
      
      // Add HMAC headers for GET requests with empty payload
      const hmacHeaders = hmacGenerator.generateHeaders('');
      Object.assign(headers, hmacHeaders);
      
      const response = await fetch(apiUrl('/api/v1/admin/admins/me'), {
        headers: headers
      });
      if (response.ok) {
        const adminData = await response.json();
        console.log('Admin info fetched:', adminData);
        return adminData.is_superadmin || false;
      } else {
        console.error('Failed to fetch admin info, status:', response.status);
      }
    } catch (error) {
      console.error('Failed to fetch admin info:', error);
    }
    return false;
  };

  useEffect(() => {
    const token = localStorage.getItem('dashboard_token');
    const user = localStorage.getItem('dashboard_user');
    const isSuperAdmin = localStorage.getItem('dashboard_is_superadmin') === 'true';
    
    if (token && user) {
      setAuth({
        isAuthenticated: true,
        token,
        user: JSON.parse(user),
        isSuperAdmin
      });
      
      // Re-fetch admin info to ensure it's up to date
      fetchAdminInfo(token).then(superAdmin => {
        if (superAdmin !== isSuperAdmin) {
          localStorage.setItem('dashboard_is_superadmin', String(superAdmin));
          setAuth(prev => ({ ...prev, isSuperAdmin: superAdmin }));
        }
      });
    }
  }, []);

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    
    try {
      if (loginMode === 'password') {
        const payload = { email: loginForm.username, password: loginForm.password };
        const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);
        
        const response = await fetch(apiUrl('/api/v1/auth/admin/login'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
            ...hmacHeaders
          },
          body: JSON.stringify(payload)
        });
        
        if (response.ok) {
          const data = await response.json();
          
          // Fetch admin info to check if super admin
          const isSuperAdmin = await fetchAdminInfo(data.access_token);
          
          const authState = {
            isAuthenticated: true,
            token: data.access_token,
            user: data.admin || { username: loginForm.username },
            isSuperAdmin
          };
          
          setAuth(authState);
          localStorage.setItem('dashboard_token', data.access_token);
          localStorage.setItem('dashboard_user', JSON.stringify(authState.user));
          localStorage.setItem('dashboard_is_superadmin', String(isSuperAdmin));
          
          setLoginForm({ username: '', password: '' });
        } else {
          const errorData = await response.json().catch(() => ({}));
          // Handle FastAPI validation errors (detail is an array)
          let errorMessage = 'Admin login failed';
          if (errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              // Validation errors: extract first error message
              errorMessage = errorData.detail[0]?.msg || errorMessage;
            } else if (typeof errorData.detail === 'string') {
              errorMessage = errorData.detail;
            }
          }
          setLoginError(errorMessage);
        }
      } else if (loginMode === 'otp-enter') {
        // Admin OTP verify
        const payload = { email: loginForm.username, code: otpCode };
        const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);
        
        const response = await fetch(apiUrl('/api/v1/auth/admin/otp/verify'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
            ...hmacHeaders
          },
          body: JSON.stringify(payload)
        });
        
        if (response.ok) {
          const data = await response.json();
          
          // Fetch admin info to check if super admin
          const isSuperAdmin = await fetchAdminInfo(data.access_token);
          
          const authState = {
            isAuthenticated: true,
            token: data.access_token,
            user: data.admin || { username: loginForm.username },
            isSuperAdmin
          };
          setAuth(authState);
          localStorage.setItem('dashboard_token', data.access_token);
          localStorage.setItem('dashboard_user', JSON.stringify(authState.user));
          localStorage.setItem('dashboard_is_superadmin', String(isSuperAdmin));
          setLoginForm({ username: '', password: '' });
          setOtpCode('');
        } else {
          const errorData = await response.json().catch(() => ({}));
          // Handle FastAPI validation errors (detail is an array)
          let errorMessage = 'OTP verification failed';
          if (errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              // Validation errors: extract first error message
              errorMessage = errorData.detail[0]?.msg || errorMessage;
            } else if (typeof errorData.detail === 'string') {
              errorMessage = errorData.detail;
            }
          }
          setLoginError(errorMessage);
        }
      }
    } catch (error) {
      setLoginError('Network error. Please try again.');
      console.error('Login error:', error);
    }
  };

  const requestOtp = async (email: string) => {
    setLoginError('');
    try {
      const payload = { email };
      const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);
      
      const response = await fetch(apiUrl('/api/v1/auth/admin/otp/request'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
          ...hmacHeaders
        },
        body: JSON.stringify(payload)
      });
      
      if (response.ok) {
        const data = await response.json();
        setOtpEmail(email);
        setLoginMode('otp-enter');
        // Show success message without alert
        setLoginError('');
      } else {
        const errorData = await response.json().catch(() => ({}));
        let errorMessage = 'Failed to request OTP';
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail[0]?.msg || errorMessage;
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          }
        }
        setLoginError(errorMessage);
      }
    } catch (e) {
      setLoginError('Network error requesting OTP');
    }
  };

  const requestPasswordReset = async (email: string) => {
    setForgotPasswordMessage('');
    setLoginError('');
    try {
      const payload = { email };
      const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);
      
      const response = await fetch(apiUrl('/api/v1/auth/admin/password/forgot'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
          ...hmacHeaders
        },
        body: JSON.stringify(payload)
      });
      
      if (response.ok) {
        const data = await response.json();
        setForgotPasswordMessage(data.message || 'If this email is registered as an admin, a password reset link has been sent.');
      } else {
        const errorData = await response.json().catch(() => ({}));
        // Still show success message for security (don't reveal if admin exists)
        setForgotPasswordMessage('If this email is registered as an admin, a password reset link has been sent.');
      }
    } catch (e) {
      setLoginError('Network error requesting password reset');
    }
  };

  const logout = () => {
    setAuth({
      isAuthenticated: false,
      token: null,
      user: null,
      isSuperAdmin: false
    });
    localStorage.removeItem('dashboard_token');
    localStorage.removeItem('dashboard_user');
    localStorage.removeItem('dashboard_is_superadmin');
  };

  const getAuthHeaders = (payload?: any): Record<string, string> => {
    const headers: Record<string, string> = {};
    if (API_KEY) {
      headers['X-API-Key'] = API_KEY;
    }
    if (auth.token) {
      headers['Authorization'] = `Bearer ${auth.token}`;
      headers['Content-Type'] = 'application/json';
    }
    
    // Add HMAC headers for ALL API calls (both GET and POST)
    console.log('🔐 [Dashboard] Generating HMAC headers...');
    console.log('🔐 [Dashboard] Payload:', payload);
    console.log('🔐 [Dashboard] API_KEY set:', !!API_KEY);
    console.log('🔐 [Dashboard] Auth token set:', !!auth.token);
    
    if (payload) {
      // For POST requests with payload
      const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);
      Object.assign(headers, hmacHeaders);
    } else {
      // For GET requests, generate HMAC headers with empty payload
      const hmacHeaders = hmacGenerator.generateHeaders('');
      Object.assign(headers, hmacHeaders);
    }
    
    console.log('🔐 [Dashboard] Final headers:', headers);
    return headers;
  };

  const fetchFeedback = async () => {
    if (!auth.isAuthenticated) return;
    setIsLoadingFeedback(true);
    try {
      const response = await fetch(apiUrl('/api/v1/feedback'), { headers: getAuthHeaders() });
      if (response.status === 401 || response.status === 403) {
        console.log('Authentication failed for feedback, logging out...');
        logout();
        return;
      }
      const data = await response.json();
      const items: FeedbackItem[] = Array.isArray(data) ? data : (data.items || []);
      // Normalize datetimes to ISO strings
      const normalized = items.map(it => ({
        ...it,
        created_at: (it as any).created_at ? new Date((it as any).created_at as any).toISOString() : undefined,
        updated_at: (it as any).updated_at ? new Date((it as any).updated_at as any).toISOString() : undefined,
      }));
      setFeedback(normalized);
    } catch (e) {
      console.error('Error fetching feedback:', e);
      setFeedback([]);
    } finally {
      setIsLoadingFeedback(false);
    }
  };

  const viewScreenshot = async (feedbackId: string) => {
    try {
      const resp = await fetch(apiUrl(`/api/v1/feedback/${feedbackId}/view-url`), { headers: getAuthHeaders() });
      if (!resp.ok) return;
      const data = await resp.json();
      const url = data.viewUrl;
      if (url) window.open(url, '_blank');
    } catch (e) {
      console.error('Failed to get view URL:', e);
    }
  };

  const updateFeedbackStatus = async (feedbackId: string, status: string, closedDate?: string) => {
    console.log('Updating feedback status:', { feedbackId, status, closedDate });
    setUpdatingFeedback(feedbackId);
    try {
      const payload: { status: string; closed_date?: string } = { status };
      if (closedDate) {
        payload.closed_date = closedDate;
      }
      
      console.log('Sending payload:', payload);
      console.log('API URL:', apiUrl(`/api/v1/feedback/${feedbackId}`));
      
      const response = await fetch(apiUrl(`/api/v1/feedback/${feedbackId}`), {
        method: 'PATCH',
        headers: getAuthHeaders(payload),
        body: JSON.stringify(payload)
      });
      
      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);
      
      if (response.ok) {
        const updatedFeedback = await response.json();
        console.log('Updated feedback received:', updatedFeedback);
        setFeedback(prev => prev.map(fb => fb.id === feedbackId ? updatedFeedback : fb));
        setEditingFeedback(null);
        setTempStatus('');
        console.log('Feedback updated successfully');
      } else {
        const errorText = await response.text();
        console.error('Failed to update feedback status:', response.status, errorText);
        alert('Failed to update feedback status. Please try again.');
      }
    } catch (e) {
      console.error('Error updating feedback status:', e);
      alert('Error updating feedback status. Please try again.');
    } finally {
      setUpdatingFeedback(null);
    }
  };

  const deleteFeedback = async (feedbackId: string) => {
    const confirmed = window.confirm(
      'Are you sure you want to delete this feedback?\n\n' +
      'This will permanently delete:\n' +
      '- The feedback entry from the database\n' +
      '- The screenshot from S3\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    try {
      const response = await fetch(apiUrl(`/api/v1/feedback/${feedbackId}`), {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('Feedback deleted:', result);
        // Remove from local state
        setFeedback(prev => prev.filter(fb => fb.id !== feedbackId));
        alert(result.message || 'Feedback deleted successfully');
      } else {
        const errorText = await response.text();
        console.error('Failed to delete feedback:', response.status, errorText);
        alert('Failed to delete feedback. Please try again.');
      }
    } catch (e) {
      console.error('Error deleting feedback:', e);
      alert('Error deleting feedback. Please try again.');
    }
  };


  const fetchSystemHealth = async () => {
    setIsRefreshing(prev => ({ ...prev, system: true }));
    try {
      const response = await fetch(apiUrl('/api/v1/dashboard/system-health'), {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('System health unauthorized; check API key and admin token.');
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

  const fetchUsers = async () => {
    if (!auth.isAuthenticated) return;
    setUsersLoading(true);
    try {
      const resp = await fetch(apiUrl('/api/v1/admin/users?limit=500'), { headers: getAuthHeaders() });
      if (resp.status === 401 || resp.status === 403) {
        logout();
        return;
      }
      const data = await resp.json();
      setUsers(Array.isArray(data) ? data : []);
      // Reset selection when reloading
      setSelectedUserIds(new Set());
      setSelectAllUsers(false);
    } catch (e) {
      console.error('Failed to load users', e);
      setUsers([]);
    } finally {
      setUsersLoading(false);
    }
  };

  const toggleSelectAllUsers = () => {
    if (selectAllUsers) {
      setSelectedUserIds(new Set());
      setSelectAllUsers(false);
    } else {
      const all = new Set<number>(users.map((u: any) => u.id));
      setSelectedUserIds(all);
      setSelectAllUsers(true);
    }
  };

  const toggleSelectUser = (id: number) => {
    setSelectedUserIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const markUsersForDeletion = async () => {
    const ids = Array.from(selectedUserIds.values());
    if (ids.length === 0) return;
    if (!window.confirm(`Mark ${ids.length} user(s) for deletion?\n\nThis will deactivate their accounts but preserve all data.`)) return;
    try {
      const payload = { user_ids: ids };
      const resp = await fetch(apiUrl('/api/v1/admin/users/mark-for-deletion'), {
        method: 'POST',
        headers: getAuthHeaders(payload),
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const text = await resp.text();
        alert(`Failed to mark users for deletion: ${resp.status} ${text}`);
        return;
      }
      const result = await resp.json();
      await fetchUsers();
      setSelectedUserIds(new Set()); // Clear selection
      alert(result.message || 'Users marked for deletion');
    } catch (e) {
      console.error('Mark for deletion failed', e);
      alert('Failed to mark users for deletion');
    }
  };

  const permanentlyDeleteUsers = async () => {
    const ids = Array.from(selectedUserIds.values());
    if (ids.length === 0) return;
    
    // Double confirmation for permanent deletion
    const firstConfirm = window.confirm(
      `⚠️ PERMANENT DELETION WARNING ⚠️\n\n` +
      `You are about to PERMANENTLY DELETE ${ids.length} user(s) and ALL their data:\n` +
      `- User accounts and profiles\n` +
      `- All health data (nutrition, vitals, lab reports)\n` +
      `- All appointments, prescriptions, and chat history\n` +
      `- ALL related records\n\n` +
      `This action is IRREVERSIBLE!\n\n` +
      `Are you sure you want to continue?`
    );
    
    if (!firstConfirm) return;
    
    const secondConfirm = window.confirm(
      `FINAL CONFIRMATION\n\n` +
      `Type or think "DELETE" to confirm.\n\n` +
      `Delete ${ids.length} user(s) PERMANENTLY?`
    );
    
    if (!secondConfirm) return;
    
    try {
      const payload = { user_ids: ids };
      const resp = await fetch(apiUrl('/api/v1/admin/users/delete-permanently'), {
        method: 'POST',
        headers: getAuthHeaders(payload),
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const text = await resp.text();
        alert(`Failed to delete users permanently: ${resp.status} ${text}`);
        return;
      }
      const result = await resp.json();
      await fetchUsers();
      setSelectedUserIds(new Set()); // Clear selection
      
      let message = result.message || `Permanently deleted ${result.deleted} user(s)`;
      if (result.errors && result.errors.length > 0) {
        message += '\n\nErrors:\n' + result.errors.join('\n');
      }
      alert(message);
    } catch (e) {
      console.error('Permanent deletion failed', e);
      alert('Failed to permanently delete users');
    }
  };

  const fetchPerformanceOverview = async () => {
    setIsRefreshing(prev => ({ ...prev, app: true }));
    try {
      const response = await fetch(apiUrl('/api/v1/dashboard/metrics/overview'), {
        headers: getAuthHeaders()
      });
      
      if (response.status === 401 || response.status === 403) {
        console.log('Performance overview unauthorized; check API key and admin token.');
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


  useEffect(() => {
    if (auth.isAuthenticated) {
      fetchSystemHealth();
      fetchPerformanceOverview();
      fetchFeedback();
      fetchUsers();
      
      // Set up polling for real-time updates
      const interval = setInterval(() => {
        fetchSystemHealth();
        fetchPerformanceOverview();
      }, 30000); // Update every 30 seconds
      
      return () => clearInterval(interval);
    }
  }, [auth.isAuthenticated]);

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


  // Render Feedback Page
  const renderFeedback = () => {
    // Apply client-side filters
    const { role, status, category, search, startDate, endDate } = feedbackFilters;
    const startTs = startDate ? new Date(startDate).getTime() : undefined;
    const endTs = endDate ? new Date(endDate).getTime() : undefined;

    const filtered = feedback.filter(item => {
      if (role !== 'all' && (item.submitter_role || 'user') !== role) return false;
      if (status !== 'all' && (item.status || 'open') !== status) return false;
      if (category !== 'all' && (item.category || '') !== category) return false;
      if (search) {
        const hay = `${item.submitter_name || ''} ${item.category || ''} ${item.description || ''} ${item.app_identifier || ''}`.toLowerCase();
        if (!hay.includes(search.toLowerCase())) return false;
      }
      if (startTs && item.created_at) {
        const t = new Date(item.created_at).getTime();
        if (t < startTs) return false;
      }
      if (endTs && item.created_at) {
        const t = new Date(item.created_at).getTime();
        if (t > endTs) return false;
      }
      return true;
    });

    const categories = Array.from(new Set(feedback.map(f => f.category).filter(Boolean))) as string[];

    return (
      <div className="monitoring-section">
        <div className="section-header">
          <div className="section-title">User/Doctor Feedback</div>
          <button 
            className={`refresh-button ${isLoadingFeedback ? 'refreshing' : ''}`} 
            onClick={fetchFeedback} 
            disabled={isLoadingFeedback}
            title="Refresh Feedback"
          >
            {isLoadingFeedback ? '⏳' : '🔄'}
          </button>
        </div>

        {/* Filters */}
        <div className="filters" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
          <select value={feedbackFilters.role} onChange={e => setFeedbackFilters(prev => ({ ...prev, role: e.target.value as any }))}>
            <option value="all">All Roles</option>
            <option value="user">User</option>
            <option value="doctor">Doctor</option>
          </select>
          <select value={feedbackFilters.status} onChange={e => setFeedbackFilters(prev => ({ ...prev, status: e.target.value as any }))}>
            <option value="all">All Status</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
          <select value={feedbackFilters.category} onChange={e => setFeedbackFilters(prev => ({ ...prev, category: e.target.value }))}>
            <option value="all">All Categories</option>
            {categories.map((c, idx) => (
              <option key={idx} value={c}>{c}</option>
            ))}
          </select>
          <input
            type="date"
            value={feedbackFilters.startDate}
            onChange={e => setFeedbackFilters(prev => ({ ...prev, startDate: e.target.value }))}
            placeholder="Start date"
          />
          <input
            type="date"
            value={feedbackFilters.endDate}
            onChange={e => setFeedbackFilters(prev => ({ ...prev, endDate: e.target.value }))}
            placeholder="End date"
          />
          <input
            type="text"
            placeholder="Search..."
            value={feedbackFilters.search}
            onChange={e => setFeedbackFilters(prev => ({ ...prev, search: e.target.value }))}
            style={{ flex: 1, minWidth: 200 }}
          />
        </div>

        {/* Feedback Table */}
        <div className="workflow-table">
          <div className="table-header">
            <div>Created</div>
            <div>Submitter</div>
            <div>Role</div>
            <div>Category</div>
            <div>Description</div>
            <div>Status</div>
            <div>Closed Date</div>
            <div>App</div>
            <div>Actions</div>
          </div>
          {filtered.slice(0, 100).map((fb, idx) => (
            <div key={idx} className="table-row">
              <div>{fb.created_at ? new Date(fb.created_at).toLocaleString() : '-'}</div>
              <div>{fb.submitter_name || (fb.user_id ?? '-')}</div>
              <div>
                <span className={`status-badge ${fb.submitter_role === 'doctor' ? 'pending' : 'success'}`}>
                  {fb.submitter_role || 'user'}
                </span>
              </div>
              <div>{fb.category || '-'}</div>
              <div className="message-preview" title={fb.description || ''}>
                {(fb.description || '').length > 60 ? `${(fb.description || '').slice(0, 60)}...` : (fb.description || '')}
              </div>
              <div>
                {editingFeedback === fb.id ? (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <select 
                      value={tempStatus || fb.status || 'open'} 
                      onChange={(e) => setTempStatus(e.target.value)}
                      style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc', minWidth: '120px' }}
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In Progress</option>
                      <option value="resolved">Resolved</option>
                    </select>
                    <button 
                      className="view-workflow-btn" 
                      onClick={() => {
                        console.log('Update button clicked for feedback:', fb.id);
                        console.log('Current tempStatus:', tempStatus);
                        console.log('Current fb.status:', fb.status);
                        const newStatus = tempStatus || fb.status || 'open';
                        console.log('New status to update:', newStatus);
                        const closedDate = newStatus === 'resolved' ? new Date().toISOString() : undefined;
                        console.log('Closed date:', closedDate);
                        updateFeedbackStatus(fb.id, newStatus, closedDate);
                      }}
                      disabled={updatingFeedback === fb.id}
                      style={{ 
                        background: updatingFeedback === fb.id ? '#6c757d' : '#28a745', 
                        minWidth: '60px', 
                        fontSize: '12px',
                        opacity: updatingFeedback === fb.id ? 0.6 : 1
                      }}
                    >
                      {updatingFeedback === fb.id ? 'Updating...' : 'Update'}
                    </button>
                  </div>
                ) : (
                  <span className={`status-badge ${(fb.status || 'open').toLowerCase()}`}>
                    {(fb.status || 'open').charAt(0).toUpperCase() + (fb.status || 'open').slice(1).toLowerCase()}
                  </span>
                )}
              </div>
              <div>
                {(() => {
                  console.log('Rendering closed_date for feedback:', fb.id, 'closed_date:', fb.closed_date);
                  if (fb.closed_date) {
                    try {
                      const date = new Date(fb.closed_date);
                      // Use toLocaleDateString with timezone options for better display
                      return date.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        timeZone: 'UTC'
                      });
                    } catch (e) {
                      console.error('Error parsing closed_date:', fb.closed_date, e);
                      return fb.closed_date;
                    }
                  }
                  return '-';
                })()}
              </div>
              <div>{fb.app_identifier || '-'}</div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button className="view-workflow-btn" onClick={() => viewScreenshot(fb.id)}>Screenshot</button>
                {editingFeedback === fb.id ? (
                  <button 
                    className="view-workflow-btn" 
                    onClick={() => {
                      setEditingFeedback(null);
                      setTempStatus('');
                    }}
                    style={{ background: '#dc3545', minWidth: '60px' }}
                  >
                    Cancel
                  </button>
                ) : (
                  <button 
                    className="view-workflow-btn" 
                    onClick={() => {
                      console.log('Setting editing feedback to:', fb.id);
                      setTempStatus(fb.status || 'open');
                      setEditingFeedback(fb.id);
                    }}
                    style={{ background: '#28a745', minWidth: '80px' }}
                  >
                    Edit
                  </button>
                )}
                <button 
                  className="view-workflow-btn" 
                  onClick={() => deleteFeedback(fb.id)}
                  style={{ background: '#dc3545', minWidth: '80px' }}
                  title="Delete feedback and screenshot"
                >
                  🗑️ Delete
                </button>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="table-row"><div>No feedback found.</div></div>
          )}
        </div>
      </div>
    );
  };

  const renderUsers = () => {
    return (
      <div className="monitoring-section users-table">
        <div className="section-header">
          <div className="section-title">Users</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button 
              className={`refresh-button ${usersLoading ? 'refreshing' : ''}`} 
              onClick={fetchUsers} 
              disabled={usersLoading}
              title="Refresh Users"
            >
              {usersLoading ? '⏳' : '🔄'}
            </button>
            <button 
              className="view-workflow-btn" 
              style={{ background: '#ff9800' }} 
              onClick={markUsersForDeletion} 
              disabled={selectedUserIds.size === 0}
              title="Deactivate accounts but keep data"
            >
              Mark for Deletion
            </button>
            <button 
              className="view-workflow-btn" 
              style={{ background: '#dc3545' }} 
              onClick={permanentlyDeleteUsers} 
              disabled={selectedUserIds.size === 0}
              title="⚠️ Permanently delete users and ALL data (irreversible)"
            >
              Delete Permanently
            </button>
          </div>
        </div>

        <div className="workflow-table">
          <div className="table-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={selectAllUsers} onChange={toggleSelectAllUsers} />
              <span>Select All</span>
            </div>
            <div>ID</div>
            <div>Email</div>
            <div>Name</div>
            <div>Status</div>
            <div>Delete Date</div>
            <div>Created</div>
          </div>
          {users.map((u: any) => (
            <div key={u.id} className="table-row">
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <input type="checkbox" checked={selectedUserIds.has(u.id)} onChange={() => toggleSelectUser(u.id)} />
              </div>
              <div>{u.id}</div>
              <div>{u.email}</div>
              <div>{u.full_name || [u.first_name, u.middle_name, u.last_name].filter(Boolean).join(' ') || '-'}</div>
              <div>
                <span className={`status-badge ${u.is_active ? 'success' : 'pending'}`}>{u.is_active ? 'active' : 'inactive'}</span>
                {u.is_tobe_deleted && <span className="status-badge error" style={{ marginLeft: 6 }}>to be deleted</span>}
              </div>
              <div>{u.delete_date ? new Date(u.delete_date).toLocaleString() : '-'}</div>
              <div>{u.created_at ? new Date(u.created_at).toLocaleString() : '-'}</div>
            </div>
          ))}
          {users.length === 0 && (
            <div className="table-row"><div>No users found.</div></div>
          )}
        </div>
      </div>
    );
  };





  // Password Reset component (if token is present in URL)
  if (showPasswordReset && resetToken) {
    return (
      <AdminPasswordReset 
        token={resetToken} 
        onSuccess={() => {
          setShowPasswordReset(false);
          // Clear token from URL
          window.history.replaceState({}, document.title, window.location.pathname);
        }} 
      />
    );
  }

  // Login component
  if (!auth.isAuthenticated) {
    return (
      <div className="login-container">
        <div className="login-form">
          <h2>🏥 ZivoHealth Dashboard</h2>
          <p>Please login to access the admin dashboard</p>
          
          {/* Password Login Mode */}
          {loginMode === 'password' && (
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
              
              {loginError && (
                <div className="error-message">
                  {loginError}
                </div>
              )}
              
              <button type="submit" className="login-button">
                Login
              </button>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#6c757d', width: '48%' }} onClick={() => setLoginMode('otp')}>
                  Login with OTP
                </button>
                <button type="button" className="login-button" style={{ background: '#17a2b8', width: '48%' }} onClick={() => setLoginMode('forgot-password')}>
                  Forgot Password
                </button>
              </div>
            </form>
          )}

          {/* OTP Email Entry Mode */}
          {loginMode === 'otp' && (
            <form onSubmit={(e) => {
              e.preventDefault();
              requestOtp(otpEmail);
            }}>
              <div className="form-group">
                <label>Email Address:</label>
                <input
                  type="email"
                  value={otpEmail}
                  onChange={(e) => setOtpEmail(e.target.value)}
                  placeholder="Enter your email"
                  required
                />
              </div>
              
              {loginError && (
                <div className="error-message">
                  {loginError}
                </div>
              )}
              
              <button type="submit" className="login-button">
                Send OTP
              </button>

              <div style={{ marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#6c757d' }} onClick={() => {
                  setLoginMode('password');
                  setOtpEmail('');
                  setLoginError('');
                }}>
                  Back to Password Login
                </button>
              </div>
            </form>
          )}

          {/* OTP Code Entry Mode */}
          {loginMode === 'otp-enter' && (
            <form onSubmit={(e) => {
              e.preventDefault();
              // Set username to the email used for OTP
              setLoginForm({...loginForm, username: otpEmail});
              login(e);
            }}>
              <div className="demo-credentials" style={{ marginBottom: 15, background: '#d4edda', color: '#155724' }}>
                <p>✅ OTP has been sent to <strong>{otpEmail}</strong></p>
              </div>

              <div className="form-group">
                <label>One-Time Password (OTP):</label>
                <input
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="Enter the 6-digit OTP"
                  required
                  maxLength={6}
                />
              </div>
              
              {loginError && (
                <div className="error-message">
                  {loginError}
                </div>
              )}
              
              <button type="submit" className="login-button">
                Verify OTP
              </button>

              <div style={{ marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#17a2b8' }} onClick={() => requestOtp(otpEmail)}>
                  Resend OTP
                </button>
              </div>

              <div style={{ marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#6c757d' }} onClick={() => {
                  setLoginMode('password');
                  setOtpEmail('');
                  setOtpCode('');
                  setLoginError('');
                }}>
                  Back to Password Login
                </button>
              </div>
            </form>
          )}

          {/* Forgot Password Mode */}
          {loginMode === 'forgot-password' && (
            <form onSubmit={(e) => {
              e.preventDefault();
              requestPasswordReset(forgotPasswordEmail);
            }}>
              <div className="form-group">
                <label>Email Address:</label>
                <input
                  type="email"
                  value={forgotPasswordEmail}
                  onChange={(e) => setForgotPasswordEmail(e.target.value)}
                  placeholder="Enter your email"
                  required
                />
              </div>
              
              {loginError && (
                <div className="error-message">
                  {loginError}
                </div>
              )}

              {forgotPasswordMessage && (
                <div className="demo-credentials" style={{ background: '#d4edda', color: '#155724' }}>
                  <p>{forgotPasswordMessage}</p>
                </div>
              )}
              
              <button type="submit" className="login-button">
                Send Reset Link
              </button>

              <div style={{ marginTop: 10 }}>
                <button type="button" className="login-button" style={{ background: '#6c757d' }} onClick={() => {
                  setLoginMode('password');
                  setForgotPasswordEmail('');
                  setForgotPasswordMessage('');
                  setLoginError('');
                }}>
                  Back to Password Login
                </button>
              </div>
            </form>
          )}
          
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
              className={`nav-item ${activeTab === 'feedback' ? 'active' : ''}`}
              onClick={() => setActiveTab('feedback')}
            >
              <span className="nav-icon">🖼️</span>
              <span className="nav-label">Feedback</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <span className="nav-icon">👥</span>
              <span className="nav-label">Users</span>
            </button>
            <button 
              className={`nav-item ${activeTab === 'healthscore' ? 'active' : ''}`}
              onClick={() => setActiveTab('healthscore')}
            >
              <span className="nav-icon">❤️</span>
              <span className="nav-label">Health Score Ops</span>
            </button>
            {auth.isSuperAdmin && (
              <button 
                className={`nav-item ${activeTab === 'admins' ? 'active' : ''}`}
                onClick={() => setActiveTab('admins')}
              >
                <span className="nav-icon">🔐</span>
                <span className="nav-label">Admin Management</span>
              </button>
            )}
          </div>
        </nav>

        <main className="app-main">
          {activeTab === 'system' && renderSystemMonitoring()}
          {activeTab === 'app' && renderAppMonitoring()}
          {activeTab === 'feedback' && renderFeedback()}
          {activeTab === 'users' && renderUsers()}
          {activeTab === 'healthscore' && <HealthScoreOps />}
          {activeTab === 'admins' && auth.isSuperAdmin && <AdminManagement apiUrl={apiUrl} getAuthHeaders={getAuthHeaders} />}
        </main>
      </div>
    </div>
  );
}

export default App;
