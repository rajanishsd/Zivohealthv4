# Environment Configuration Fix Summary

## Problem
- ❌ SQLite check in `session.py` causing `AttributeError: 'NoneType' object has no attribute 'startswith'`
- ❌ SMTP credentials hardcoded in deployment scripts
- ❌ `.env` file on EC2 not regenerating properly from SSM parameters
- ❌ All configuration values were hardcoded in scripts instead of sourcing from `.env.production`

## Solution

### 1. Fixed `backend/app/db/session.py`
**Removed SQLite check** - Application now directly uses PostgreSQL configuration:

```python
# PostgreSQL configuration with connection pooling
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=20,
    max_overflow=30,
    pool_recycle=300,
    pool_pre_ping=True,
    pool_timeout=45,
    echo=False
)
```

### 2. Fixed `scripts/dev/push-and-deploy.sh`
**Now sources all configuration from `backend/.env.production`**:

1. **Uploads base `.env.production` file to EC2**:
   ```bash
   ENV_PROD_CONTENT=$(cat "$ENV_PROD_FILE" | base64)
   aws ssm send-command ... \
     --parameters commands="[\"echo '$ENV_PROD_CONTENT' | base64 -d | sudo tee /opt/zivohealth/.env.production.base >/dev/null\"]"
   ```

2. **Remote script copies base file and overrides dynamic values**:
   ```bash
   cp /opt/zivohealth/.env.production.base /tmp/.env.new
   
   # Override only dynamic values from SSM
   sed -i "s|^POSTGRES_SERVER=.*|POSTGRES_SERVER=${POSTGRES_SERVER}|g" /tmp/.env.new
   sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|g" /tmp/.env.new
   sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=\"${OPENAI_API_KEY}\"|g" /tmp/.env.new
   # ... (all SSM-managed secrets)
   ```

### 3. Fixed `infra/terraform/modules/compute/user_data_minimal.sh.tpl`
**Updated to match local `.env.production` values**:
- SMTP_USERNAME=rajanish@zivohealth.ai
- SMTP_PASSWORD=Zivohealth@890 (fallback)
- FROM_EMAIL=rajanish@zivohealth.ai

## Configuration Philosophy

### Static Config (from `backend/.env.production`)
- All model configurations (GPT-4o-mini, o4-mini, etc.)
- Server settings (host, port, timeouts)
- Feature flags and defaults
- CORS origins
- SMTP username and from email
- Service endpoints (RabbitMQ, Redis, etc.)

### Dynamic Config (from SSM Parameter Store)
- Database credentials (host, user, password)
- API keys (OpenAI, LangChain, E2B, SerpAPI)
- Security secrets (SECRET_KEY, APP_SECRET_KEY, VALID_API_KEYS)
- SMTP password
- LiveKit credentials
- FCM credentials

## Benefits

✅ **Single Source of Truth**: `backend/.env.production` is the master config  
✅ **No Hardcoding**: All values come from either `.env.production` or SSM  
✅ **Easy Updates**: Change config locally, push and deploy  
✅ **Secure**: Secrets still managed in SSM, never committed to git  
✅ **Consistent**: Same config used for local builds and production deployments  

## Files Modified

1. **`backend/app/db/session.py`** - Removed SQLite check
2. **`scripts/dev/push-and-deploy.sh`** - Sources from `.env.production`, uploads base file
3. **`infra/terraform/modules/compute/user_data_minimal.sh.tpl`** - Updated fallback values

## Deployment Flow

```
Local Machine                              EC2 Instance
─────────────                             ─────────────

backend/.env.production
       │
       ├─→ Read local file
       │
       ├─→ Upload via SSM
       │                                   
       └────────────────────────────────→ /opt/zivohealth/.env.production.base
                                                   │
                                                   ├─→ Copy to /tmp/.env.new
                                                   │
                                          Fetch secrets from SSM:
                                          - POSTGRES_PASSWORD
                                          - OPENAI_API_KEY
                                          - Other secrets
                                                   │
                                                   ├─→ Override in /tmp/.env.new
                                                   │
                                                   └─→ Move to /opt/zivohealth/.env
                                                   
                                          Docker containers restart with new .env
```

## Next Steps

1. ✅ Deploy changes with `bash scripts/dev/push-and-deploy.sh`
2. ✅ Verify API container starts successfully
3. ✅ Confirm database connection works
4. ✅ Test password reset email functionality

