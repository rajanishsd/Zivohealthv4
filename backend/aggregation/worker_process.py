#!/usr/bin/env python3
"""
Separate Background Worker Process
Runs independently from the main FastAPI server to prevent database connection conflicts
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to Python path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up two levels to backend
sys.path.insert(0, backend_dir)

# Load environment variables from .env file before importing app modules
from dotenv import load_dotenv
env_file = os.path.join(backend_dir, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  No .env file found at {env_file}")

# Now import app modules after environment is loaded
from app.core.background_worker import run_worker_process
from app.utils.timezone import now_local

# Configure logging for separate process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('worker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for worker process"""
    logger.info("🚀 Starting ZivoHealth Background Worker Process")
    logger.info(f"📅 Started at: {now_local()}")
    
    try:
        # Run the async worker process (process all domains by default)
        asyncio.run(run_worker_process())
    except KeyboardInterrupt:
        logger.info("🛑 Worker process shutdown requested")
    except Exception as e:
        logger.error(f"❌ Worker process error: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Worker process terminated")

if __name__ == "__main__":
    main() 