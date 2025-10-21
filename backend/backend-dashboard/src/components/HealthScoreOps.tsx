import React, { useState } from 'react';
import { hmacGenerator } from '../utils/hmac';

// Keep env vars consistent with App.tsx
const API_BASE = process.env.REACT_APP_API_BASE_URL || '';
const API_KEY = process.env.REACT_APP_API_KEY || '';

export const HealthScoreOps: React.FC = () => {
  const [output, setOutput] = useState<string>('');
  const [userId, setUserId] = useState<string>('1');
  const [dateStr, setDateStr] = useState<string>('');
  const [rangeStart, setRangeStart] = useState<string>('');
  const [rangeEnd, setRangeEnd] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [token, setToken] = useState<string>('');
  const [authError, setAuthError] = useState<string>('');

  async function callEndpoint(method: string, path: string, payload: any = null, isJSON = false, token?: string) {
    const url = `${API_BASE}${path}`;
    const body = isJSON ? JSON.stringify(payload ?? {}) : (payload ?? '');
    const headers: Record<string, string> = {
      'X-API-Key': API_KEY,
    };
    const hmacHeaders = isJSON ? hmacGenerator.generateJSONHeaders(payload ?? {}) : hmacGenerator.generateHeaders(body);
    headers['X-Timestamp'] = hmacHeaders['X-Timestamp'];
    headers['X-App-Signature'] = hmacHeaders['X-App-Signature'];
    if (isJSON) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(url, { method, headers, body: method === 'GET' ? undefined : body });
    const text = await res.text();
    return { status: res.status, text };
  }

  async function login(email: string, password: string) {
    // Use admin login route (JSON + HMAC) to obtain admin token
    const payload = { email, password };
    const url = `${API_BASE}/api/v1/auth/admin/login`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...hmacGenerator.generateJSONHeaders(payload),
    };
    const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload) });
    const text = await res.text();
    if (res.ok) {
      try { const j = JSON.parse(text); return j.access_token as string; } catch { /* fallthrough */ }
    }
    throw new Error(`Login failed: ${res.status} ${text}`);
  }

  async function ensureAuth() {
    if (token) return token;
    setAuthError('');
    try {
      const t = await login('rajanish@zivohealth.ai', 'pass@123');
      setToken(t);
      return t;
    } catch (e: any) {
      setAuthError(e.message || String(e));
      throw e;
    }
  }

  async function onSyncAnchors() {
    setLoading(true); setOutput('');
    try {
      const tok = await ensureAuth();
      const res = await callEndpoint('POST', '/api/v1/internal/health-score/sync-anchors-from-loinc', '', false, tok);
      setOutput(`Status ${res.status}: ${res.text}`);
    } catch (e: any) {
      setOutput(e.message || String(e));
    } finally { setLoading(false); }
  }

  async function onRecompute() {
    setLoading(true); setOutput('');
    try {
      const tok = await ensureAuth();
      const qs = new URLSearchParams({ user_id: userId, date_str: dateStr || new Date().toISOString().slice(0,10) });
      const res = await callEndpoint('POST', `/api/v1/internal/health-score/recompute?${qs.toString()}`, '', false, tok);
      setOutput(`Status ${res.status}: ${res.text}`);
    } catch (e: any) {
      setOutput(e.message || String(e));
    } finally { setLoading(false); }
  }

  async function onRecomputeRange() {
    setLoading(true); setOutput('');
    try {
      if (!rangeStart || !rangeEnd) throw new Error('Select start and end dates');
      const start = new Date(rangeStart + 'T00:00:00Z');
      const end = new Date(rangeEnd + 'T00:00:00Z');
      if (isNaN(start.getTime()) || isNaN(end.getTime())) throw new Error('Invalid dates');
      if (end < start) throw new Error('End date must be after start date');
      const tok = await ensureAuth();
      let log = '';
      const d = new Date(start);
      while (d <= end) {
        const ds = d.toISOString().slice(0,10);
        const qs = new URLSearchParams({ user_id: userId, date_str: ds });
        const res = await callEndpoint('POST', `/api/v1/internal/health-score/recompute?${qs.toString()}`, '', false, tok);
        log += `\n${ds}: ${res.status}`;
        d.setDate(d.getDate() + 1);
      }
      setOutput(`Recompute complete:${log}`);
    } catch (e: any) {
      setOutput(e.message || String(e));
    } finally { setLoading(false); }
  }

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginBottom: 8 }}>Health Score Ops</h2>

      {/* Auth status */}
      <div style={{ marginBottom: 12, fontSize: 13, color: token ? '#198754' : '#6c757d' }}>
        Auth: {token ? 'Authenticated' : 'Not authenticated'} {authError && `• ${authError}`}
      </div>

      {/* Card: Sync Anchors */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Anchors</div>
        <button onClick={onSyncAnchors} disabled={loading} style={{ padding: '6px 12px' }}>
          {loading ? 'Working…' : 'Sync Anchors from LOINC'}
        </button>
      </div>

      {/* Card: Recompute Single Date */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Recompute (Single Date)</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label>User ID</label>
          <input placeholder="User ID" value={userId} onChange={e => setUserId(e.target.value)} style={{ width: 100 }} />
          <label>Date</label>
          <input type="date" value={dateStr} onChange={e => setDateStr(e.target.value)} />
          <button onClick={onRecompute} disabled={loading} style={{ padding: '6px 12px' }}>Recompute</button>
        </div>
      </div>

      {/* Card: Recompute Range */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Recompute (Range)</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label>Start</label>
          <input type="date" value={rangeStart} onChange={e => setRangeStart(e.target.value)} />
          <label>End</label>
          <input type="date" value={rangeEnd} onChange={e => setRangeEnd(e.target.value)} />
          <button onClick={onRecomputeRange} disabled={loading} style={{ padding: '6px 12px' }}>Recompute Range</button>
        </div>
      </div>

      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Output</div>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{output || '—'}</pre>
      </div>
    </div>
  );
};

export default HealthScoreOps;


