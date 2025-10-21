import React, { useState, useEffect } from 'react';
import '../App.css';

interface AdminUser {
  id: number;
  email: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  full_name: string | null;
  is_superadmin: boolean;
  is_active: boolean;
}

interface AdminManagementProps {
  apiUrl: (path: string) => string;
  getAuthHeaders: (payload?: any) => Record<string, string>;
}

const AdminManagement: React.FC<AdminManagementProps> = ({ apiUrl, getAuthHeaders }) => {
  const [admins, setAdmins] = useState<AdminUser[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [selectedAdminId, setSelectedAdminId] = useState<number | null>(null);

  // Create admin form
  const [createForm, setCreateForm] = useState({
    email: '',
    password: '',
    first_name: '',
    middle_name: '',
    last_name: ''
  });

  // Change password form
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });

  // Fetch admins list
  const fetchAdmins = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(apiUrl('/api/v1/admin/admins'), {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setAdmins(data);
      } else {
        alert('Failed to fetch admins');
      }
    } catch (e) {
      console.error('Failed to fetch admins', e);
      alert('Failed to fetch admins');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAdmins();
  }, []);

  // Create admin
  const handleCreateAdmin = async () => {
    if (!createForm.email || !createForm.password || !createForm.first_name || !createForm.last_name) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      const payload = {
        email: createForm.email,
        password: createForm.password,
        first_name: createForm.first_name,
        middle_name: createForm.middle_name || null,
        last_name: createForm.last_name,
        full_name: null
      };

      const response = await fetch(apiUrl('/api/v1/admin/admins/create'), {
        method: 'POST',
        headers: getAuthHeaders(payload),
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const result = await response.json();
        alert(result.message || 'Admin created successfully');
        setShowCreateModal(false);
        setCreateForm({ email: '', password: '', first_name: '', middle_name: '', last_name: '' });
        fetchAdmins();
      } else {
        const error = await response.json().catch(() => ({ detail: 'Failed to create admin' }));
        console.error('Create admin error:', error);
        alert(error.detail || 'Failed to create admin');
      }
    } catch (e) {
      console.error('Failed to create admin', e);
      alert('Network error: Failed to create admin');
    }
  };

  // Change password
  const handleChangePassword = async () => {
    if (!selectedAdminId) return;

    const selectedAdmin = admins.find(a => a.id === selectedAdminId);
    const isSuperAdmin = selectedAdmin?.is_superadmin || false;

    // Validate current password for super admin
    if (isSuperAdmin && !passwordForm.current_password) {
      alert('Current password is required to change super admin password');
      return;
    }

    if (!passwordForm.new_password || !passwordForm.confirm_password) {
      alert('Please fill in all password fields');
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('Passwords do not match');
      return;
    }

    if (passwordForm.new_password.length < 8) {
      alert('Password must be at least 8 characters long');
      return;
    }

    try {
      const payload: any = {
        admin_id: selectedAdminId,
        new_password: passwordForm.new_password
      };

      // Include current password if changing super admin password
      if (isSuperAdmin) {
        payload.current_password = passwordForm.current_password;
      }

      const response = await fetch(apiUrl('/api/v1/admin/admins/change-password'), {
        method: 'POST',
        headers: getAuthHeaders(payload),
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const result = await response.json();
        alert(result.message || 'Password changed successfully');
        setShowPasswordModal(false);
        setSelectedAdminId(null);
        setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
      } else {
        // Robust error extraction: try JSON, then text, then status
        let message = 'Failed to change password';
        try {
          const text = await response.text();
          try {
            const data = JSON.parse(text);
            const detail = (typeof data.detail === 'string'
              ? data.detail
              : (data.detail && JSON.stringify(data.detail))) || '';
            message = detail || data.message || message;
            console.error('Password change error (json):', data);
          } catch {
            // Not JSON
            if (text && text.trim().length > 0) {
              message = text;
            }
            console.error('Password change error (text):', text);
          }
        } catch (err) {
          console.error('Password change error (unknown):', err);
        }
        alert(message);
      }
    } catch (e) {
      console.error('Failed to change password', e);
      alert('Network error: Failed to change password');
    }
  };

  // Delete admin
  const handleDeleteAdmin = async (adminId: number, adminEmail: string, isSuperAdmin: boolean) => {
    if (isSuperAdmin) {
      alert('Cannot delete super admin. Super admin is protected and cannot be removed.');
      return;
    }

    const confirm = window.confirm(
      `Are you sure you want to delete admin:\n${adminEmail}?\n\nThis action cannot be undone.`
    );

    if (!confirm) return;

    try {
      const response = await fetch(apiUrl(`/api/v1/admin/admins/${adminId}`), {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (response.ok) {
        const result = await response.json();
        alert(result.message || 'Admin deleted successfully');
        fetchAdmins();
      } else {
        const error = await response.json().catch(() => ({ detail: 'Failed to delete admin' }));
        console.error('Delete admin error:', error);
        alert(error.detail || 'Failed to delete admin');
      }
    } catch (e) {
      console.error('Failed to delete admin', e);
      alert('Network error: Failed to delete admin');
    }
  };

  // Open password modal
  const openPasswordModal = (adminId: number) => {
    setSelectedAdminId(adminId);
    setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    setShowPasswordModal(true);
  };

  return (
    <div className="monitoring-section">
      <div className="section-header">
        <div className="section-title">Admin Management</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className={`refresh-button ${isLoading ? 'refreshing' : ''}`}
            onClick={fetchAdmins}
            disabled={isLoading}
            title="Refresh Admins"
          >
            {isLoading ? '⏳' : '🔄'}
          </button>
          <button
            className="view-workflow-btn"
            style={{ background: '#4caf50' }}
            onClick={() => setShowCreateModal(true)}
          >
            + Create Admin
          </button>
        </div>
      </div>

      {/* Admins Table */}
      <div className="workflow-table">
        <div className="table-header" style={{ gridTemplateColumns: '80px 1.5fr 1.2fr 1fr 200px' }}>
          <div>ID</div>
          <div>Email</div>
          <div>Full Name</div>
          <div>Type</div>
          <div>Actions</div>
        </div>
        {admins.map((admin) => (
          <div key={admin.id} className="table-row" style={{ gridTemplateColumns: '80px 1.5fr 1.2fr 1fr 200px' }}>
            <div>{admin.id}</div>
            <div>{admin.email}</div>
            <div>{admin.full_name || '-'}</div>
            <div>
              {admin.is_superadmin ? (
                <span className="status-badge" style={{ background: '#ffd700', color: '#333', border: '1px solid #ffaa00' }}>
                  Super Admin
                </span>
              ) : (
                <span className="status-badge" style={{ background: '#e3f2fd', color: '#1976d2', border: '1px solid #90caf9' }}>
                  Admin
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                className="view-workflow-btn"
                style={{ background: '#ff9800', minWidth: 'auto', padding: '4px 8px' }}
                onClick={() => openPasswordModal(admin.id)}
                title="Change Password"
              >
                🔑 Password
              </button>
              {!admin.is_superadmin && (
                <button
                  className="view-workflow-btn"
                  style={{ background: '#dc3545', minWidth: 'auto', padding: '4px 8px' }}
                  onClick={() => handleDeleteAdmin(admin.id, admin.email, admin.is_superadmin)}
                  title="Delete Admin"
                >
                  🗑️ Delete
                </button>
              )}
            </div>
          </div>
        ))}
        {admins.length === 0 && !isLoading && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
            No admins found
          </div>
        )}
      </div>

      {/* Create Admin Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Admin</h2>
            <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
              Note: Super admin cannot be created. Only regular admins can be created.
            </p>
            <div className="form-group">
              <label>Email *</label>
              <input
                type="email"
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                placeholder="admin@example.com"
              />
            </div>
            <div className="form-group">
              <label>Password * (min 8 characters)</label>
              <input
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                placeholder="Enter password"
              />
            </div>
            <div className="form-group">
              <label>First Name *</label>
              <input
                type="text"
                value={createForm.first_name}
                onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })}
                placeholder="Enter first name"
              />
            </div>
            <div className="form-group">
              <label>Middle Name</label>
              <input
                type="text"
                value={createForm.middle_name}
                onChange={(e) => setCreateForm({ ...createForm, middle_name: e.target.value })}
                placeholder="Enter middle name (optional)"
              />
            </div>
            <div className="form-group">
              <label>Last Name *</label>
              <input
                type="text"
                value={createForm.last_name}
                onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })}
                placeholder="Enter last name"
              />
            </div>
            <div className="modal-actions">
              <button onClick={() => setShowCreateModal(false)} className="modal-button cancel">
                Cancel
              </button>
              <button onClick={handleCreateAdmin} className="modal-button confirm">
                Create Admin
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {showPasswordModal && (
        <div className="modal-overlay" onClick={() => setShowPasswordModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Change Admin Password</h2>
            <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
              {admins.find(a => a.id === selectedAdminId)?.is_superadmin
                ? 'Changing password for Super Admin (requires current password)'
                : 'Changing password for Admin'}
            </p>
            {admins.find(a => a.id === selectedAdminId)?.is_superadmin && (
              <div className="form-group">
                <label>Current Password *</label>
                <input
                  type="password"
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                  placeholder="Enter current password"
                  autoComplete="current-password"
                />
              </div>
            )}
            <div className="form-group">
              <label>New Password * (min 8 characters)</label>
              <input
                type="password"
                value={passwordForm.new_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                placeholder="Enter new password"
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>Confirm Password *</label>
              <input
                type="password"
                value={passwordForm.confirm_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                placeholder="Confirm new password"
              />
            </div>
            {passwordForm.new_password && passwordForm.new_password.length < 8 && (
              <p style={{ color: '#dc3545', fontSize: '12px', marginTop: '-10px' }}>
                Password must be at least 8 characters long
              </p>
            )}
            {passwordForm.new_password && passwordForm.confirm_password && 
             passwordForm.new_password !== passwordForm.confirm_password && (
              <p style={{ color: '#dc3545', fontSize: '12px', marginTop: '-10px' }}>
                Passwords do not match
              </p>
            )}
            <div className="modal-actions">
              <button onClick={() => setShowPasswordModal(false)} className="modal-button cancel">
                Cancel
              </button>
              <button onClick={handleChangePassword} className="modal-button confirm">
                Change Password
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminManagement;

