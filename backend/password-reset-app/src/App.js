import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useSearchParams } from 'react-router-dom';
import axios from 'axios';

// API configuration - use relative URLs since React app is served by the same backend
const API_BASE_URL = '/api/v1';

// Password Reset Form Component
function PasswordResetForm() {
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // Get token from URL parameters
    const tokenFromUrl = searchParams.get('token');
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
      // Verify token is valid
      verifyToken(tokenFromUrl);
    }
  }, [searchParams]);

  const verifyToken = async (tokenToVerify) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/auth/verify-reset-token/${tokenToVerify}`);
      if (!response.data.valid) {
        setMessage('Invalid or expired reset token.');
        setMessageType('error');
      }
    } catch (error) {
      setMessage('Error verifying reset token.');
      setMessageType('error');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!token) {
      setMessage('Reset token is required.');
      setMessageType('error');
      return;
    }

    if (newPassword.length < 8) {
      setMessage('Password must be at least 8 characters long.');
      setMessageType('error');
      return;
    }

    if (newPassword !== confirmPassword) {
      setMessage('Passwords do not match.');
      setMessageType('error');
      return;
    }

    setIsLoading(true);
    setMessage('');

    try {
      await axios.post(`${API_BASE_URL}/auth/reset-password`, {
        token: token,
        new_password: newPassword
      });

      setMessage('Password has been reset successfully! You can now log in with your new password.');
      setMessageType('success');
      
      // Clear form
      setNewPassword('');
      setConfirmPassword('');
      
    } catch (error) {
      if (error.response && error.response.data && error.response.data.detail) {
        setMessage(error.response.data.detail);
      } else {
        setMessage('An error occurred while resetting your password. Please try again.');
      }
      setMessageType('error');
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="container">
        <div className="card">
          <div className="header">
            <div className="logo">ZivoHealth</div>
            <h1 className="title">Reset Password</h1>
            <p className="subtitle">Invalid reset link</p>
          </div>
          <div className="message error">
            No reset token found in the URL. Please use the link from your email.
          </div>
          <div className="footer">
            <a href="/" className="link">Return to ZivoHealth</a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <div className="header">
          <div className="logo">ZivoHealth</div>
          <h1 className="title">Reset Password</h1>
          <p className="subtitle">Enter your new password below</p>
        </div>

        {message && (
          <div className={`message ${messageType}`}>
            {message}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="label" htmlFor="newPassword">
              New Password
            </label>
            <input
              type="password"
              id="newPassword"
              className="input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
              required
              minLength="8"
            />
          </div>

          <div className="form-group">
            <label className="label" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <input
              type="password"
              id="confirmPassword"
              className="input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              required
              minLength="8"
            />
          </div>

          <button
            type="submit"
            className="button"
            disabled={isLoading || !newPassword || !confirmPassword}
          >
            {isLoading && <span className="loading"></span>}
            {isLoading ? 'Resetting Password...' : 'Reset Password'}
          </button>
        </form>

        <div className="footer">
          <a href="/" className="link">Return to ZivoHealth</a>
        </div>
      </div>
    </div>
  );
}

// Main App Component
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/reset-password" element={<PasswordResetForm />} />
        <Route path="/" element={<PasswordResetForm />} />
      </Routes>
    </Router>
  );
}

export default App;
