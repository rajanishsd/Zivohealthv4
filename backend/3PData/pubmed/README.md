# PubMed & PMC Medical Literature Embedder

This system downloads, parses, and embeds PubMed and PMC medical literature using BioBERT, storing documents and embeddings directly in PostgreSQL with pgvector.

## Features

- **Download**: Automated download of PubMed baseline files and PMC Open Access articles
- **Parse**: XML parsing of medical literature with metadata extraction
- **Embed**: BioBERT-based sentence embeddings for semantic search
- **Database Storage**: Direct storage in PostgreSQL with pgvector for vector similarity search
- **Batch Processing**: Memory-efficient processing of large datasets
- **Progress Tracking**: Real-time progress monitoring with batch tracking

## Prerequisites

1. **PostgreSQL** with pgvector extension
2. **Python 3.8+**
3. **8GB+ RAM** (16GB+ recommended)
4. **500GB+ storage** for full dataset

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Database**:
   ```bash
   # First, enable pgvector in your PostgreSQL
   psql -h localhost -p 5433 -U your_user -d your_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
   
   # Then setup tables
   python pubmed_pmc_embedder.py --setup-db
   ```

3. **Run Full Pipeline**:
   ```bash
   python pubmed_pmc_embedder.py --full-pipeline
   ```

4. **Limited Test Run**:
   ```bash
   python pubmed_pmc_embedder.py --full-pipeline --max-pubmed-files 5 --max-pmc-files 2
   ```

## Usage Options

### Setup Database Only
```bash
python pubmed_pmc_embedder.py --setup-db
```

### Download Only
```bash
python pubmed_pmc_embedder.py --download --max-pubmed-files 10
```

### Parse and Embed Existing Files
```bash
python pubmed_pmc_embedder.py --parse --embed
```

### Search Documents
```bash
python pubmed_pmc_embedder.py --search "diabetes treatment"
```

### Check Database Statistics
```bash
python pubmed_pmc_embedder.py --stats
```

## File Structure

```
3PData/
├── pubmed_pmc_embedder.py    # Main processing script (LangChain + PGVector)
├── LANGCHAIN_EMBEDDER_SUMMARY.md # Technical summary
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── medical_data/            # Downloaded data
    ├── pubmed/              # PubMed XML files
    └── pmc/                 # PMC archive files
```

## Database Schema

The system uses LangChain's PGVector integration with the following PostgreSQL tables:

### `langchain_pg_collection`
- Stores collection metadata
- Collection name: "medical_documents"
- UUID-based collection identification

### `langchain_pg_embedding`
- `uuid`: Primary key
- `collection_id`: Foreign key to collection
- `embedding`: Vector embedding (768 dimensions)
- `document`: Full text content
- `cmetadata`: JSON metadata including:
  - `pmid`: PubMed ID
  - `pmc_id`: PMC ID (if applicable)
  - `title`: Article title
  - `journal`: Journal name
  - `authors`: Array of author names
  - `document_type`: 'pubmed' or 'pmc'
  - `mesh_terms`: Array of MeSH terms
  - `doi`: DOI identifier
  - `pub_date`: Publication date

## Data Sources

### PubMed
- **Source**: ftp.ncbi.nlm.nih.gov/pubmed/baseline/
- **Content**: Article metadata, abstracts, MeSH terms
- **Format**: XML files (compressed)
- **Size**: ~1000 files, ~35GB compressed

### PMC Open Access
- **Source**: ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/
- **Content**: Full-text articles
- **Format**: TAR archives containing XML files
- **Size**: Multiple archives, ~100GB+ total

## BioBERT Model

**Primary Model**: `dmis-lab/biobert-base-cased-v1.1`
**Fallback Model**: `sentence-transformers/all-MiniLM-L6-v2`
- Pre-trained on biomedical literature
- Fine-tuned for medical text understanding
- 768-dimensional embeddings
- Optimized for semantic similarity
- Automatic fallback for PyTorch security issues

## Processing Flow

1. **Download**: XML files from NCBI FTP servers
2. **Parse**: Extract text, metadata, and structure from XML
3. **Embed**: Generate BioBERT embeddings using LangChain HuggingFace integration
4. **Store**: Save documents and embeddings to PostgreSQL via PGVector
5. **Index**: pgvector automatically indexes embeddings for fast search

## Vector Search

The system uses LangChain's PGVector for efficient similarity search:

```python
from pubmed_pmc_embedder import MedicalEmbeddingPipeline

pipeline = MedicalEmbeddingPipeline()

# Search similar documents
results = pipeline.search_documents("diabetes treatment", k=10)

for doc, score in results:
    print(f"Title: {doc.metadata.get('title', 'No title')}")
    print(f"Score: {score:.4f}")
    print(f"Journal: {doc.metadata.get('journal', 'Unknown')}")
    print("---")
```

## Performance

- **Embedding Speed**: ~100-500 articles/minute (depends on hardware)
- **Search Speed**: <100ms for similarity search with pgvector
- **Storage**: ~2KB per document + ~3KB per embedding
- **Memory**: Processes in batches to manage memory usage

## Configuration

Configuration is now handled directly in `pubmed_pmc_embedder.py`:
- Database URL
- Collection name
- Batch sizes
- File limits
- Directory paths
- Model settings

You can modify these settings by editing the constants at the top of the main script.

## Performance Tips

1. **Use SSD storage** for faster I/O
2. **Increase batch sizes** if you have more RAM
3. **Use GPU** for faster embeddings (install torch-gpu)
4. **Tune PostgreSQL** for better performance
5. **Monitor database connections** during processing

## Database Integration

The system integrates with your existing PostgreSQL database using LangChain:

```python
from pubmed_pmc_embedder import LangChainBioBERTEmbedder

embedder = LangChainBioBERTEmbedder()

# Search documents
results = embedder.search_similar_documents("medical query", k=10)

# Get statistics
stats = embedder.get_stats()
```

## Error Handling

The system handles:
- Network interruptions (resume downloads)
- Corrupted files (skip and log)
- Database connection issues (retry with backoff)
- Memory issues (batch processing)
- XML parsing errors (skip invalid articles)
- Model loading failures (automatic fallback)

## Monitoring

- **Logs**: Detailed logging in `pubmed_pmc_embedder.log`
- **Statistics**: Real-time database statistics via `--stats` command
- **Search Analytics**: Track search performance and results

## Troubleshooting

### Common Issues

1. **pgvector not installed**:
   ```bash
   # Install pgvector
   brew install pgvector  # macOS
   # or compile from source
   ```

2. **Database connection failed**:
   - Check PostgreSQL is running
   - Verify connection settings in pubmed_pmc_embedder.py
   - Ensure user has necessary permissions

3. **Out of Memory**: 
   - Reduce batch sizes in processing functions
   - Monitor memory usage during processing

4. **Model loading issues**:
   - System automatically falls back to alternative model
   - Check PyTorch version for security compliance

### Logs
Check `pubmed_pmc_embedder.log` for detailed processing information.

## License & Citation

This tool processes public domain medical literature. Please cite original sources:
- PubMed: https://pubmed.ncbi.nlm.nih.gov/
- PMC: https://www.ncbi.nlm.nih.gov/pmc/
- BioBERT: https://huggingface.co/dmis-lab/biobert-base-cased-v1.1

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify database connectivity
3. Test with smaller datasets first
4. Monitor system resources during processing 