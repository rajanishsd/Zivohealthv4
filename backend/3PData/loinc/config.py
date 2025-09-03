"""
Configuration for LOINC Embedder
===============================

This file contains all configuration settings for the LOINC embedder
including database settings, OpenAI configuration, and processing parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Database Configuration
DATABASE_HOST = os.getenv('POSTGRES_SERVER', 'localhost')
DATABASE_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
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

# Lab Aggregation Agent Configuration
LAB_AGGREGATION_AGENT_MODEL = os.getenv('LAB_AGGREGATION_AGENT_MODEL', 'o4-mini')
LAB_AGGREGATION_AGENT_TEMPERATURE = float(os.getenv('LAB_AGGREGATION_AGENT_TEMPERATURE', '1'))

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Custom Table Names (to avoid conflicts with existing PubMed tables)
LOINC_COLLECTION_TABLE = "loinc_pg_collection"
LOINC_EMBEDDING_TABLE = "loinc_pg_embedding"
LAB_TEST_MAPPINGS_TABLE = "lab_test_mappings"

# Collection Settings
COLLECTION_NAME = "loinc_terminology"

# File Paths
LOINC_DATA_DIR = Path(__file__).parent / ".." / "data" / "lonic"
LOINC_CSV_FILE = LOINC_DATA_DIR / "Loinc.csv"
LOINC_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "lonic", "Loinc.csv")
LOG_FILE = LOINC_DATA_DIR / "loinc_embedder.log"

# Processing Settings
BATCH_SIZE = 100  # Number of LOINC codes to process at once
LOINC_EMBEDDER_BATCH_SIZE = 5000  # Process 5000 LOINC codes at a time (for loinc_embedder.py)
LAB_MAPPER_BATCH_SIZE = 50  # Process tests in batches (for lab_test_loinc_mapper.py)
EMBEDDING_BATCH_SIZE = 64  # Batch size for embeddings
OPENAI_BATCH_SIZE = 50  # Batch size for OpenAI API calls
RATE_LIMIT_DELAY = 1.0  # Delay between API calls (seconds)
LOINC_EMBEDDER_RATE_LIMIT_DELAY = 0.1  # Reduced delay since we're not using OpenAI API
LAB_MAPPER_RATE_LIMIT_DELAY = 1.0  # Delay between ChatGPT API calls
MAX_CONCURRENT_REQUESTS = 5  # Maximum concurrent OpenAI requests

# Cost Estimation (approximate costs in USD)
COST_PER_1K_TOKENS = 0.00013  # Cost for text-embedding-3-large
AVERAGE_TOKENS_PER_LOINC = 50  # Estimated tokens per LOINC code

# Progress Tracking
PROGRESS_UPDATE_INTERVAL = 1000  # Update progress every N records
CHECKPOINT_INTERVAL = 5000  # Save progress every N records

# Search Settings
DEFAULT_SEARCH_RESULTS = 10
MIN_SIMILARITY_SCORE = 0.0
MAX_SIMILARITY_SCORE = 1.0

# Validation Settings
REQUIRED_LOINC_FIELDS = ['LOINC_NUM', 'LONG_COMMON_NAME']
VALID_LOINC_STATUSES = ['ACTIVE', 'TRIAL', 'DISCOURAGED', 'DEPRECATED']

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def validate_config():
    """Validate configuration settings"""
    errors = []
    
    # Check LOINC CSV file exists
    if not LOINC_CSV_FILE.exists():
        errors.append(f"LOINC CSV file not found: {LOINC_CSV_FILE}")
    
    # Check database URL
    if not DATABASE_URL:
        errors.append("DATABASE_URL is not configured")
    
    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")
    
    return True

def get_estimated_cost(num_loinc_codes: int) -> float:
    """Estimate the cost of processing LOINC codes"""
    total_tokens = num_loinc_codes * AVERAGE_TOKENS_PER_LOINC
    return (total_tokens / 1000) * COST_PER_1K_TOKENS

