"""
Configuration for RxNorm Embedder
================================

This file contains all configuration settings for the RxNorm embedder
including database settings, BioBERT configuration, and processing parameters.
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

# BioBERT Configuration
EMBEDDING_MODEL = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
EMBEDDING_DIMENSIONS = 768
MAX_RETRIES = 3

# Custom Table Names (to avoid conflicts with existing tables)
RXNORM_COLLECTION_TABLE = "rxnorm_pg_collection"
RXNORM_EMBEDDING_TABLE = "rxnorm_pg_embedding"

# Collection Settings
COLLECTION_NAME = "rxnorm_terminology"

# File Paths
RXNORM_DATA_DIR = Path(__file__).parent / ".." / "data" / "rxnorm"
RXNORM_CSV_FILE = RXNORM_DATA_DIR / "CONCEPT.csv"
LOG_FILE = RXNORM_DATA_DIR / "rxnorm_embedder.log"

# Processing Settings
BATCH_SIZE = 5000  # Number of RxNorm codes to process at once
EMBEDDING_BATCH_SIZE = 64  # Batch size for embeddings
RATE_LIMIT_DELAY = 0.1  # Delay between batches (seconds)

# Progress Tracking
PROGRESS_UPDATE_INTERVAL = 1000  # Update progress every N records
CHECKPOINT_INTERVAL = 5000  # Save progress every N records

# Search Settings
DEFAULT_SEARCH_RESULTS = 10
MIN_SIMILARITY_SCORE = 0.0
MAX_SIMILARITY_SCORE = 1.0

# Validation Settings
REQUIRED_RXNORM_FIELDS = ['concept_id', 'concept_name', 'concept_code']
VALID_RXNORM_DOMAINS = ['Drug']
VALID_RXNORM_VOCABULARIES = ['RxNorm']
VALID_RXNORM_STANDARD_CONCEPTS = ['S']

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def validate_config():
    """Validate configuration settings"""
    errors = []
    
    # Check RxNorm CSV file exists
    if not RXNORM_CSV_FILE.exists():
        errors.append(f"RxNorm CSV file not found: {RXNORM_CSV_FILE}")
    
    # Check database URL
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
            "collection_table": RXNORM_COLLECTION_TABLE,
            "embedding_table": RXNORM_EMBEDDING_TABLE
        },
        "rxnorm_csv_file": str(RXNORM_CSV_FILE),
        "log_file": str(LOG_FILE)
    } 