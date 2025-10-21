import React, { useState, useEffect } from 'react';
import { hmacGenerator } from '../utils/hmac';

const API_BASE = (process.env.REACT_APP_API_BASE_URL || '');
const API_KEY = (process.env.REACT_APP_API_KEY || '');
const apiUrl = (path: string) => `${API_BASE}${path}`;

interface AdminPasswordResetProps {
  token: string;
  onSuccess: () => void;
}

const AdminPasswordReset: React.FC<AdminPasswordResetProps> = ({ token, onSuccess }) => {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);

  useEffect(() => {
    // Verify token on mount
    verifyToken();
  }, [token]);

  const verifyToken = async () => {
    try {
      const response = await fetch(apiUrl(`/api/v1/auth/admin/password/verify-token/${token}`), {
        method: 'GET',
        headers: {
          ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
        }
      });

      if (response.ok) {
        const data = await response.json();
        setTokenValid(data.valid);
        if (!data.valid) {
          setError('This password reset link is invalid or has expired. Please request a new one.');
        }
      } else {
        setTokenValid(false);
        setError('Failed to verify reset token.');
      }
    } catch (e) {
      setTokenValid(false);
      setError('Network error. Please check your connection.');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Validation
    if (!newPassword || !confirmPassword) {
      setError('Please fill in all fields');
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const payload = {
        token: token,
        new_password: newPassword
      };
      const hmacHeaders = hmacGenerator.generateJSONHeaders(payload);

      const response = await fetch(apiUrl('/api/v1/auth/admin/password/reset'), {
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
        setSuccess(data.message || 'Password reset successful! Redirecting to login...');
        setNewPassword('');
        setConfirmPassword('');
        
        // Redirect to login after 2 seconds
        setTimeout(() => {
          onSuccess();
        }, 2000);
      } else {
        const errorData = await response.json().catch(() => ({}));
        let errorMessage = 'Failed to reset password';
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail[0]?.msg || errorMessage;
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          }
        }
        setError(errorMessage);
      }
    } catch (e) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (tokenValid === null) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h2>🔐 Admin Password Reset</h2>
          <p>Verifying reset link...</p>
        </div>
      </div>
    );
  }

  if (tokenValid === false) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h2>🔐 Admin Password Reset</h2>
          <div style={{ color: '#dc3545', marginBottom: 20 }}>
            <p>{error}</p>
          </div>
          <button 
            className="login-button" 
            onClick={onSuccess}
            style={{ marginTop: 10 }}
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>🔐 Reset Admin Password</h2>
        <p style={{ marginBottom: 20, color: '#666' }}>
          Enter your new password below
        </p>

        {error && (
          <div style={{ 
            color: '#dc3545', 
            marginBottom: 15, 
            padding: 10, 
            background: '#f8d7da', 
            borderRadius: 4,
            border: '1px solid #f5c6cb'
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{ 
            color: '#155724', 
            marginBottom: 15, 
            padding: 10, 
            background: '#d4edda', 
            borderRadius: 4,
            border: '1px solid #c3e6cb'
          }}>
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="newPassword">New Password</label>
            <input
              type="password"
              id="newPassword"
              className="form-control"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
              disabled={loading}
              minLength={8}
              required
            />
            <small style={{ color: '#666', fontSize: 12 }}>
              Minimum 8 characters
            </small>
          </div>

          <div className="form-group" style={{ marginTop: 15 }}>
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              className="form-control"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              disabled={loading}
              required
            />
          </div>

          <button 
            type="submit" 
            className="login-button" 
            disabled={loading}
            style={{ marginTop: 20 }}
          >
            {loading ? 'Resetting Password...' : 'Reset Password'}
          </button>

          <button 
            type="button" 
            className="login-button" 
            onClick={onSuccess}
            disabled={loading}
            style={{ 
              marginTop: 10, 
              background: '#6c757d' 
            }}
          >
            Back to Login
          </button>
        </form>
      </div>
    </div>
  );
};

export default AdminPasswordReset;

