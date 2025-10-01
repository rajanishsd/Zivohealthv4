from typing import Dict, Any, List, Optional
import os
import requests

from app.core.config import settings


def _resolve_base_url() -> str:
    """Resolve Reminders service base URL from env variables.
    Tries REMINDER_SERVICE_URL, then REMINDER_SERVICE_HOST/REMINDER_SERVICE_PORT.
    Raises RuntimeError if not configured.
    """
    base_url = os.getenv("REMINDER_SERVICE_URL")
    if not base_url:
        host = os.getenv("REMINDER_SERVICE_HOST")
        port = os.getenv("REMINDER_SERVICE_PORT")
        if host and port:
            base_url = f"http://{host}:{port}"
    if not base_url:
        raise RuntimeError("REMINDER_SERVICE_URL/host:port not configured")
    return base_url.rstrip("/")


def _build_headers() -> Dict[str, str]:
    """Build headers including X-API-Key if available."""
    api_key: Optional[str] = None
    try:
        keys = getattr(settings, "VALID_API_KEYS", []) or []
        if isinstance(keys, list) and keys:
            api_key = keys[0]
        elif isinstance(keys, str) and keys:
            api_key = keys
    except Exception:
        api_key = None

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def push_create_reminder(payload: Dict[str, Any], timeout: int = 10) -> requests.Response:
    """POST a reminder create payload to the Reminders service."""
    base_url = _resolve_base_url()
    headers = _build_headers()
    url = f"{base_url}/api/v1/reminders"
    return requests.post(url, json=payload, headers=headers, timeout=timeout)


def push_list_reminders(user_id: str, status: Optional[str] = None, timeout: int = 10) -> List[Dict[str, Any]]:
    """GET reminders list for a user (optionally filter by status)."""
    base_url = _resolve_base_url()
    headers = _build_headers()
    params: Dict[str, Any] = {"user_id": user_id}
    if status:
        params["status"] = status
    url = f"{base_url}/api/v1/reminders"
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    try:
        return list(r.json())
    except Exception:
        return []


def push_update_reminder(reminder_id: str, payload: Dict[str, Any], timeout: int = 10) -> requests.Response:
    """PATCH an existing reminder with the given payload."""
    base_url = _resolve_base_url()
    headers = _build_headers()
    url = f"{base_url}/api/v1/reminders/{reminder_id}"
    return requests.patch(url, json=payload, headers=headers, timeout=timeout)


def push_delete_reminder(reminder_id: str, timeout: int = 10) -> requests.Response:
    """DELETE a reminder by ID."""
    base_url = _resolve_base_url()
    headers = _build_headers()
    url = f"{base_url}/api/v1/reminders/{reminder_id}"
    return requests.delete(url, headers=headers, timeout=timeout)

