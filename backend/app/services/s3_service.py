import os
from typing import Optional, Tuple

from app.core.config import settings

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import BotoCoreError, ClientError
    _BOTO_AVAILABLE = True
except Exception:
    _BOTO_AVAILABLE = False


def _get_s3_client():
    if not _BOTO_AVAILABLE:
        raise RuntimeError("boto3 is not available; install boto3 to use S3 uploads")
    client_kwargs = {}
    if settings.AWS_REGION:
        client_kwargs["region_name"] = settings.AWS_REGION
    elif settings.AWS_DEFAULT_REGION:
        client_kwargs["region_name"] = settings.AWS_DEFAULT_REGION
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **client_kwargs)


def upload_bytes_and_get_uri(bucket: str, key: str, data: bytes, content_type: Optional[str] = None) -> str:
    """
    Upload raw bytes to S3 and return an s3:// URI.
    """
    if not bucket or str(bucket).strip() == "":
        raise RuntimeError("S3 bucket is empty. Set AWS_S3_BUCKET or disable USE_S3_UPLOADS.")
    s3 = _get_s3_client()
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=data, **extra_args)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Failed to upload to S3 s3://{bucket}/{key}: {e}")
    return f"s3://{bucket}/{key}"


def is_s3_uri(path: str) -> bool:
    return path.startswith("s3://")


def download_to_temp(s3_uri: str) -> str:
    """
    Download an s3://bucket/key object to a temporary local file and return the path.
    """
    assert s3_uri.startswith("s3://"), "download_to_temp expects an s3:// URI"
    import tempfile
    from urllib.parse import urlparse
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    s3 = _get_s3_client()
    fd, temp_path = tempfile.mkstemp(prefix="s3_", suffix=os.path.splitext(key)[1] or "")
    os.close(fd)
    try:
        with open(temp_path, "wb") as f_out:
            s3.download_fileobj(bucket, key, f_out)
    except (BotoCoreError, ClientError) as e:
        try:
            os.remove(temp_path)
        except Exception:
            pass
        raise RuntimeError(f"Failed to download {s3_uri} to temp file: {e}")
    return temp_path



def generate_presigned_get_url(s3_uri: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned GET URL for an s3://bucket/key URI.
    """
    if not s3_uri or not s3_uri.startswith("s3://"):
        raise RuntimeError("generate_presigned_get_url expects an s3:// URI")
    from urllib.parse import urlparse
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    if not bucket or not key:
        raise RuntimeError("Invalid S3 URI; missing bucket or key")
    s3 = _get_s3_client()
    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in
        )
        return url
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Failed to generate presigned URL for {s3_uri}: {e}")

def delete_file_from_s3(s3_uri: str) -> bool:
    """
    Delete a file from S3 given an s3://bucket/key URI.
    Returns True if successful, False otherwise.
    """
    if not s3_uri or not s3_uri.startswith("s3://"):
        raise RuntimeError("delete_file_from_s3 expects an s3:// URI")
    
    from urllib.parse import urlparse
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    
    if not bucket or not key:
        raise RuntimeError("Invalid S3 URI; missing bucket or key")
    
    s3 = _get_s3_client()
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        return True
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Failed to delete {s3_uri} from S3: {e}")


def verify_s3_configuration(require_write: bool = False) -> Tuple[bool, str]:
    """
    Verify S3 configuration and access at startup.
    - Returns (ok, message)
    - If uploads are disabled, returns (True, "S3 uploads disabled")
    - Checks bucket presence and HeadBucket permissions
    - Optionally attempts a write+delete roundtrip when require_write=True
    """
    try:
        if not getattr(settings, "USE_S3_UPLOADS", False):
            return True, "S3 uploads disabled"

        bucket = getattr(settings, "AWS_S3_BUCKET", None)
        if not bucket or str(bucket).strip() == "":
            # Config root validator should have already disabled, but double-guard here
            try:
                settings.USE_S3_UPLOADS = False  # degrade gracefully
            except Exception:
                pass
            return False, "AWS_S3_BUCKET is blank; disabled S3 uploads"

        s3 = _get_s3_client()

        # Verify bucket exists and is accessible
        try:
            s3.head_bucket(Bucket=bucket)
        except (BotoCoreError, ClientError) as e:
            try:
                settings.USE_S3_UPLOADS = False
            except Exception:
                pass
            return False, f"HeadBucket failed for '{bucket}': {e}"

        if require_write:
            # Optionally test write permissions with a short-lived object
            import uuid
            test_key = f"healthchecks/startup_{uuid.uuid4().hex}.txt"
            try:
                s3.put_object(Bucket=bucket, Key=test_key, Body=b"ok")
                # Best-effort delete (ignore delete failures)
                try:
                    s3.delete_object(Bucket=bucket, Key=test_key)
                except Exception:
                    pass
            except (BotoCoreError, ClientError) as e:
                try:
                    settings.USE_S3_UPLOADS = False
                except Exception:
                    pass
                return False, f"Write test failed for s3://{bucket}/{test_key}: {e}"

        return True, f"S3 verified (bucket={bucket}, write_test={'on' if require_write else 'off'})"
    except Exception as e:
        try:
            settings.USE_S3_UPLOADS = False
        except Exception:
            pass
        return False, f"Unexpected S3 verification error: {e}"

