# LOINC Embedder with OpenAI text-embedding-3-large

This system processes LOINC (Logical Observation Identifiers Names and Codes) terminology and creates semantic embeddings using OpenAI's `text-embedding-3-large` model, storing them in PostgreSQL with pgvector for efficient similarity search.

## ✨ Features

- **OpenAI Integration**: Uses `text-embedding-3-large` model (3072 dimensions)
- **Custom Tables**: Separate tables to avoid conflicts with existing PubMed data
- **Semantic Search**: High-quality medical terminology search
- **Batch Processing**: Efficient processing of 104K+ LOINC codes
- **Cost Tracking**: Built-in cost estimation and monitoring
- **Interactive Search**: Command-line search interface
- **Progress Tracking**: Resumable processing with progress monitoring

## 🗂️ Custom Database Schema

The system uses **custom table names** to completely separate LOINC data from existing PubMed embeddings:

### Custom Tables Created:

- `loinc_pg_collection` - LOINC collection metadata
- `loinc_pg_embedding` - LOINC embeddings and metadata

### Existing Tables (Untouched):

- `langchain_pg_collection` - PubMed collection metadata
- `langchain_pg_embedding` - PubMed embeddings

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
export OPENAI_API_KEY="your_openai_api_key_here"

# Ensure PostgreSQL is running on port 5433
# Ensure pgvector extension is available
```

### 2. Setup Database

```bash
# Create custom tables and setup database
python loinc_embedder.py --setup-db
```

### 3. Process LOINC Codes

```bash
# Process all LOINC codes (104K+ codes, ~$130 estimated cost)
python loinc_embedder.py --process-loinc

# Process first 1000 codes for testing
python loinc_embedder.py --process-loinc --max-codes 1000

# Check progress/stats
python loinc_embedder.py --stats
```

### 4. Search LOINC Codes

```bash
# Single search
python loinc_embedder.py --search "blood glucose"

# Interactive search mode
python loinc_search.py --interactive

# Search by specific LOINC code
python loinc_search.py --code "33747-0"
```

## 📊 Data Processing

### LOINC CSV Structure

The system processes `LoincTableCore.csv` with the following key fields:

- `LOINC_NUM`: Unique identifier (e.g., "33747-0")
- `LONG_COMMON_NAME`: Full description
- `SHORTNAME`: Short display name
- `COMPONENT`: What is being measured
- `SYSTEM`: System/specimen type
- `CLASS`: Classification category
- `STATUS`: Active/inactive status

### Text Preparation for Embeddings

Each LOINC code is converted to rich text for embedding:

```
LOINC: 33747-0
Name: Glucose [Mass/volume] in Blood
Short Name: Glucose SerPl-mCnc
Component: Glucose
Property: MCnc
System: Serum or Plasma
Class: Chemistry
Status: ACTIVE
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
export OPENAI_API_KEY="your_api_key"

# Optional
export LOINC_BATCH_SIZE=100
export LOINC_RATE_LIMIT_DELAY=1.0
```

### Configuration Files

- `config.py`: Main configuration settings
- `requirements.txt`: Python dependencies
- `loinc_embedder.py`: Main processing script
- `loinc_search.py`: Search interface

## 🔍 Search Capabilities

### 1. Command Line Search

```bash
# Basic search
python loinc_search.py "blood glucose"

# Search with custom number of results
python loinc_search.py "blood pressure" -k 5

# Search by LOINC code
python loinc_search.py --code "33747-0"
```

### 2. Interactive Mode

```bash
python loinc_search.py --interactive

# Commands in interactive mode:
# - Type search query to search
# - 'code <LOINC_CODE>' to search by code
# - 'stats' to show database statistics
# - 'help' to show commands
# - 'exit' to quit
```

### 3. Batch Search

```bash
# Create queries.txt with one query per line
echo "blood glucose" > queries.txt
echo "blood pressure" >> queries.txt
echo "cholesterol" >> queries.txt

# Run batch search
python loinc_search.py --batch-search queries.txt --export results.json
```

### 4. Programmatic Search

```python
from loinc_embedder import LOINCEmbeddingPipeline

pipeline = LOINCEmbeddingPipeline()
results = pipeline.search_loinc_codes("blood glucose", k=10)

for doc, score in results:
    metadata = doc.metadata
    print(f"LOINC: {metadata['loinc_num']} (Score: {score:.4f})")
    print(f"Name: {metadata['long_common_name']}")
```

## 💰 Cost Estimation

### OpenAI API Costs

- **Model**: text-embedding-3-large
- **Cost**: $0.13 per 1M tokens
- **Estimated tokens per LOINC**: ~50 tokens
- **Total LOINC codes**: ~104,673
- **Estimated total cost**: ~$130

### Cost Tracking

The system tracks costs in real-time:

```bash
# Check cost estimates
python -c "from config import get_estimated_cost; print(f'Estimated cost: ${get_estimated_cost(104673):.2f}')"
```

## 📈 Performance Metrics

### Processing Speed

- **Batch size**: 100 codes per batch
- **Rate limiting**: 1 second delay between batches
- **Expected rate**: ~60 codes per minute
- **Total time**: ~29 hours for all codes

### Storage Requirements

- **Embeddings**: 3072 dimensions × 4 bytes = 12.3KB per code
- **Metadata**: ~1KB per code
- **Total storage**: ~1.3GB for all LOINC codes

## 🛠️ Advanced Usage

### Custom Embedding Function

```python
from loinc_embedder import CustomLOINCPGVector
from langchain_openai import OpenAIEmbeddings

# Create custom embeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    dimensions=3072,
    chunk_size=50
)

# Use custom vector store
vector_store = CustomLOINCPGVector(
    connection_string="postgresql://user@localhost:5433/db",
    embedding_function=embeddings,
    collection_name="loinc_terminology"
)
```

### Database Queries

```sql
-- Check custom tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('loinc_pg_collection', 'loinc_pg_embedding');

-- Count LOINC codes
SELECT COUNT(*) FROM loinc_pg_embedding;

-- Search by LOINC code directly
SELECT * FROM loinc_pg_embedding 
WHERE cmetadata->>'loinc_num' = '33747-0';
```

## 🔧 Troubleshooting

### Common Issues

1. **OpenAI API Key Error**

   ```bash
   export OPENAI_API_KEY="your_key_here"
   python loinc_embedder.py --process-loinc
   ```
2. **Database Connection Error**

   ```bash
   # Check PostgreSQL is running
   psql -h localhost -p 5433 -U rajanishsd -d zivohealth -c "SELECT 1;"
   ```
3. **Table Already Exists Error**

   ```bash
   # Check if custom tables exist
   python loinc_embedder.py --stats
   ```
4. **CSV File Not Found**

   ```bash
   # Ensure LoincTableCore.csv is in the loinc directory
   ls -la backend/3PData/loinc/LoincTableCore.csv
   ```

### Verification

```bash
# Verify custom tables are being used
python -c "
from loinc_embedder import LOINCEmbeddingPipeline
pipeline = LOINCEmbeddingPipeline()
stats = pipeline.get_stats()
print('Custom tables:', stats.get('custom_tables'))
"
```

## 🧪 Testing

### Test Processing

```bash
# Process first 10 codes for testing
python loinc_embedder.py --process-loinc --max-codes 10

# Test search
python loinc_embedder.py --search "test"

# Check stats
python loinc_embedder.py --stats
```

### Validate Results

```bash
# Search for known LOINC codes
python loinc_search.py --code "33747-0"  # Blood glucose
python loinc_search.py --code "8480-6"   # Systolic blood pressure
python loinc_search.py --code "8462-4"   # Diastolic blood pressure
```

## 🔒 Security

### API Key Management

- Store API key in environment variable
- Never commit API keys to version control
- Use `.env` file for local development

### Database Security

- Use dedicated database user for LOINC operations
- Restrict permissions to necessary tables only
- Enable SSL for database connections in production

## 📚 References

- [LOINC Official Website](https://loinc.org/)
- [OpenAI Embeddings Documentation](https://platform.openai.com/docs/guides/embeddings)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction.html)

## 🆘 Support

For issues or questions:

1. Check the troubleshooting section above
2. Verify configuration settings in `config.py`
3. Check log files (`loinc_embedder.log`)
4. Ensure all dependencies are installed

## 📝 License

This project follows the same license as the main zivohealth project.
