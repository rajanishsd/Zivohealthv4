from typing import Dict, Any, Optional
import json
import os
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from firebase_admin import messaging, credentials, initialize_app, _apps  # type: ignore

from .config import settings
from .repository import get_latest_token_for_user
from .metrics import reminders_dispatch_success_total, reminders_dispatch_failed_total
from .repository import mark_processed, mark_failed
from app.db.session import SessionLocal
from sqlalchemy import text


def _ensure_firebase_initialized() -> None:
    if _apps:
        return

    proj = getattr(settings, "FCM_PROJECT_ID", None)
    env_gac_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    env_gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cfg_val = getattr(settings, "FCM_CREDENTIALS_JSON", None)

    print(f"🔍 [FCM] Initializing Firebase | project_id={proj}")
    print(
        "🔍 [FCM] Creds sources | REMINDER_FCM_CREDENTIALS_JSON set="
        f"{bool(cfg_val)}, GOOGLE_APPLICATION_CREDENTIALS_JSON set={bool(env_gac_json)}, "
        f"GOOGLE_APPLICATION_CREDENTIALS set={bool(env_gac)}"
    )

    creds_json: Optional[str] = cfg_val or env_gac_json or env_gac

    # Check if credentials are available
    if not creds_json or creds_json.strip() == "":
        print("⚠️  [FCM] No credentials provided - FCM push notifications will be disabled")
        return
    
    if creds_json and creds_json.strip().startswith("{"):
        print(f"🔍 [FCM] Using inline JSON credentials")
        try:
            cred = credentials.Certificate(json.loads(creds_json))
            initialize_app(cred, options={"projectId": proj} if proj else None)
            print(f"✅ [FCM] Firebase app initialized (inline JSON). apps={len(_apps)}")
        except Exception as e:
            print(f"❌ [FCM] Failed to initialize with inline credentials: {e!r}")
            return
    else:
        print(f"🔍 [FCM] Using file-based credentials: {creds_json}")
        # Use file-based credentials with explicit project ID
        if creds_json and os.path.exists(creds_json):
            try:
                cred = credentials.Certificate(creds_json)
                initialize_app(cred, options={"projectId": proj} if proj else None)
                print(f"✅ [FCM] Firebase app initialized (file). apps={len(_apps)}")
            except Exception as e:
                print(f"❌ [FCM] Failed to initialize with file credentials: {e!r}")
                return
        elif proj:
            try:
                initialize_app(options={"projectId": proj})
                print(f"✅ [FCM] Firebase app initialized (projectId only). apps={len(_apps)}")
            except Exception as e:
                print(f"❌ [FCM] Failed to initialize with project ID only: {e!r}")
                return
        else:
            try:
                initialize_app()
                print(f"✅ [FCM] Firebase app initialized (default). apps={len(_apps)}")
            except Exception as e:
                print(f"❌ [FCM] Failed to initialize Firebase: {e!r}")
                return


def send_push_via_fcm(event: Dict[str, Any]) -> None:
    """Send push notification via FCM using APNs for iOS through FCM.
    Expected event contains:
      - user_id
      - reminder_id
      - reminder_type
      - payload (must include either 'fcm_token' or we expect backend to resolve and include it)
      - timestamp
    """
    print(f"🔍 [FCM] Dispatch event: {event}")
    
    # Ensure Firebase is initialized (attempt initialization if not already done)
    _ensure_firebase_initialized()

    # If still not initialized after attempt, skip sending
    if not _apps:
        print(
            "⚠️  [FCM] Firebase not initialized - skipping push notification | "
            f"project_id={getattr(settings, 'FCM_PROJECT_ID', None)}, "
            f"REMINDER_FCM_CREDENTIALS_JSON set={bool(getattr(settings, 'FCM_CREDENTIALS_JSON', None))}, "
            f"GOOGLE_APPLICATION_CREDENTIALS={bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))}"
        )
        return
    
    token = event.get("payload", {}).get("fcm_token")
    if not token:
        # Try lookup by user_id (ios by default)
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            user_id = str(event.get("user_id", ""))
            print(f"🔍 [FCM] Looking up token for user_id: {user_id}")
            token = get_latest_token_for_user(db, user_id=user_id, platform="ios") if user_id else None
            print(f"🔍 [FCM] Found token: {token[:20] if token else 'None'}...")
        finally:
            db.close()
        if not token:
            print("❌ [FCM] No FCM token found for user")
            reminders_dispatch_failed_total.inc()
            return

    # Default if missing or None
    notification_title = event.get("payload", {}).get("title") or "Reminder"
    notification_body = event.get("payload", {}).get("message") or "It's time!"

    # Build timestamps for payload: both utc and user-local
    utc_ts = None
    try:
        ts = event.get("timestamp")
        if isinstance(ts, datetime):
            utc_ts = (ts if ts.tzinfo else ts.replace(tzinfo=dt_timezone.utc)).astimezone(dt_timezone.utc).isoformat()
        elif isinstance(ts, str) and ts:
            # Accept both Z and +00:00
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            utc_ts = (dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)).astimezone(dt_timezone.utc).isoformat()
    except Exception:
        utc_ts = None

    local_ts = utc_ts or ""
    # Look up user timezone from user_profiles, fallback to DEFAULT_TIMEZONE via core settings
    user_tz_name = None
    try:
        uid = event.get("user_id")
        if uid:
            db = SessionLocal()
            row = db.execute(text("SELECT timezone FROM user_profiles WHERE user_id = :uid"), {"uid": int(uid)}).first()
            if row and row[0]:
                user_tz_name = str(row[0])
            db.close()
    except Exception:
        user_tz_name = None

    try:
        if utc_ts and user_tz_name:
            dt = datetime.fromisoformat(utc_ts.replace("Z", "+00:00"))
            local_ts = dt.astimezone(ZoneInfo(user_tz_name)).isoformat()
    except Exception:
        pass

    # Generate unique notification ID to prevent iOS suppression
    import uuid
    notification_id = str(uuid.uuid4())
    
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=notification_title, body=notification_body),
        data={
            "reminder_id": str(event.get("reminder_id")),
            "reminder_type": str(event.get("reminder_type")),
            "timestamp_utc": utc_ts or "",
            "timestamp_local": local_ts,
            "notification_id": notification_id,
        },
        apns=messaging.APNSConfig(
            headers={
                "apns-push-type": "alert",
                "apns-priority": "10",
                "apns-collapse-id": notification_id,  # Prevent iOS from collapsing similar notifications
            }
        ),
    )

    try:
        print(f"🚀 [FCM] Sending notification to token: {token[:20]}...")
        print(f"🚀 [FCM] Title: {notification_title}")
        print(f"🚀 [FCM] Body: {notification_body}")
        result = messaging.send(message, dry_run=False)
        print(f"✅ [FCM] Notification sent successfully: {result}")
        reminders_dispatch_success_total.inc()
        
        # Update rate limiting timestamp
        current_time = datetime.now(dt_timezone.utc)
        send_push_via_fcm._last_notification_time = current_time
    except Exception as e:
        import traceback
        print(f"❌ [FCM] Failed to send notification: {e!r}")
        tb = ''.join(traceback.format_exc().splitlines()[-3:])
        print(f"❌ [FCM] Traceback tail: {tb}")
        reminders_dispatch_failed_total.inc()
        # We intentionally do not raise to avoid Celery retry storms for now
        # Mark reminder as Failed for observability
        try:
            from app.db.session import SessionLocal
            db = SessionLocal()
            try:
                rid = str(event.get("reminder_id"))
                if rid:
                    mark_failed(db, rid, reason=str(e))
            finally:
                db.close()
        except Exception:
            pass
        return
    else:
        # Mark reminder as Processed on success
        try:
            from app.db.session import SessionLocal
            db = SessionLocal()
            try:
                rid = str(event.get("reminder_id"))
                if rid:
                    mark_processed(db, rid)
            finally:
                db.close()
        except Exception:
            pass


