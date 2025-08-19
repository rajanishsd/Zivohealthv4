"""
Configuration for SNOMED CT Embedder
====================================

This file contains all configuration settings for the SNOMED CT embedder,
including database settings, embedding model, PySpark, and processing parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Database Configuration
DATABASE_HOST = os.getenv('POSTGRES_SERVER', 'localhost')
DATABASE_PORT = int(os.getenv('POSTGRES_PORT', '5433'))
DATABASE_USER = os.getenv('POSTGRES_USER', 'rajanishsd')
DATABASE_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
DATABASE_NAME = os.getenv('POSTGRES_DB', 'zivohealth')

# Construct DATABASE_URL from environment variables
if DATABASE_PASSWORD:
    DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
else:
    DATABASE_URL = f"postgresql://{DATABASE_USER}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

# Embedding Model Configuration
EMBEDDING_MODEL = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
EMBEDDING_DIMENSIONS = 768

# Custom Table Names
SNOMED_COLLECTION_TABLE = "snomed_pg_collection"
SNOMED_EMBEDDING_TABLE = "snomed_pg_embedding"

# Collection Settings
COLLECTION_NAME = "snomed_terminology"

# File Paths
SNOMED_DATA_DIR = Path("/Users/rajanishsd/Documents/zivohealth-1/backend/3PData/data/snomedct")
# Update this path to your SNOMED CT concepts file (e.g., sct2_Concept_Full_INT_*.txt)
SNOMED_CONCEPTS_FILE = SNOMED_DATA_DIR / "CONCEPT.csv"
LOG_FILE = SNOMED_DATA_DIR / "snomed_embedder.log"

# PySpark Settings
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
SPARK_APP_NAME = "SNOMEDCT_Embedder"
SPARK_NUM_EXECUTORS = int(os.getenv("SPARK_NUM_EXECUTORS", "4"))
SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "8g")
SPARK_DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "8g")

# Processing Settings
BATCH_SIZE = 10000  # Number of SNOMED codes to process at once
EMBEDDING_BATCH_SIZE = 1024  # Batch size for embeddings
RATE_LIMIT_DELAY = 0.1  # Delay between batches (seconds)
MAX_DB_CONNECTIONS = 8  # Limit concurrent DB writes to avoid overloading PostgreSQL

# Progress Tracking
PROGRESS_UPDATE_INTERVAL = 1000  # Update progress every N records
CHECKPOINT_INTERVAL = 5000  # Save progress every N records

# Search Settings
DEFAULT_SEARCH_RESULTS = 10
MIN_SIMILARITY_SCORE = 0.0
MAX_SIMILARITY_SCORE = 1.0

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def validate_config():
    """Validate configuration settings"""
    errors = []
    if not SNOMED_CONCEPTS_FILE.exists():
        errors.append(f"SNOMED CT concepts file not found: {SNOMED_CONCEPTS_FILE}")
    if not DATABASE_URL:
        errors.append("DATABASE_URL is not configured")
    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")
    return True

def get_config_summary() -> dict:
    """Get a summary of current configuration"""
    return {
        "database_url": DATABASE_URL,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "batch_size": BATCH_SIZE,
        "collection_name": COLLECTION_NAME,
        "custom_tables": {
            "collection_table": SNOMED_COLLECTION_TABLE,
            "embedding_table": SNOMED_EMBEDDING_TABLE
        },
        "snomed_concepts_file": str(SNOMED_CONCEPTS_FILE),
        "log_file": str(LOG_FILE),
        "spark": {
            "master": SPARK_MASTER,
            "app_name": SPARK_APP_NAME,
            "num_executors": SPARK_NUM_EXECUTORS,
            "executor_memory": SPARK_EXECUTOR_MEMORY,
            "driver_memory": SPARK_DRIVER_MEMORY
        }
    } 