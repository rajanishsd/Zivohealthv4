# RxNorm Embedder

This module processes RxNorm CONCEPT CSV data and creates embeddings using the BioBERT model from Hugging Face, storing them in PostgreSQL with PGVector for semantic search capabilities.

## Features

- **BioBERT Model**: Uses `pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb` for medical text embeddings
- **Custom Tables**: Separate PostgreSQL tables to avoid conflicts with existing data
- **Batch Processing**: Efficient processing of large RxNorm datasets
- **Semantic Search**: Vector similarity search for drug terminology
- **Filtering**: Automatically filters for standard RxNorm drugs only

## Requirements

- Python 3.8+
- PostgreSQL with PGVector extension
- RxNorm CONCEPT.csv file

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure PostgreSQL is running with PGVector extension:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Usage

### Setup Database

First, create the necessary database tables:

```bash
python rxnorm_embedder.py --setup-db
```

### Process RxNorm Data

Process the entire RxNorm dataset:

```bash
python rxnorm_embedder.py --process-rxnorm
```

Or process a limited number of codes:

```bash
python rxnorm_embedder.py --process-rxnorm --max-codes 10000
```

### Search RxNorm Codes

Search for drug terminology:

```bash
python rxnorm_embedder.py --search "aspirin"
python rxnorm_embedder.py --search "blood pressure medication"
```

### Get Statistics

View processing statistics:

```bash
python rxnorm_embedder.py --stats
```

## Data Filtering

The embedder automatically filters RxNorm records using these criteria:
- `vocabulary_id == 'RxNorm'`
- `domain_id == 'Drug'`
- `standard_concept == 'S'`

This ensures only standard RxNorm drug concepts are processed.

## Database Schema

### Custom Tables

- `rxnorm_pg_collection`: Collection metadata
- `rxnorm_pg_embedding`: Embedding vectors and metadata

### Embedding Dimensions

- **Model**: BioBERT (768 dimensions)
- **Index**: HNSW for fast similarity search
- **Distance**: Cosine similarity

## Configuration

Edit `config.py` to modify:
- Database connection settings
- Processing batch sizes
- Model parameters
- File paths

## Performance

- **Batch Size**: 5000 records per batch
- **Embedding Batch**: 64 documents per embedding call
- **Rate Limiting**: 0.1 second delay between batches
- **Memory**: Optimized for CPU processing

## Logging

Logs are written to `rxnorm_embedder.log` with detailed progress information.

## Example Output

```
2024-01-15 10:30:00 - INFO - Processing RxNorm CSV: ../data/rxnorm/CONCEPT.csv
2024-01-15 10:30:05 - INFO - Processing batch: 5000 records (Total filtered: 5000)
2024-01-15 10:30:10 - INFO - ✅ Added 5000 documents to RxNorm collection
2024-01-15 10:30:15 - INFO - Processed 5000 RxNorm codes (500.00 codes/sec)
```

## Troubleshooting

### Common Issues

1. **Memory Issues**: Reduce batch size in config.py
2. **Database Connection**: Check DATABASE_URL in config.py
3. **Model Download**: Ensure internet connection for first run
4. **CSV File**: Verify CONCEPT.csv path is correct

### Performance Tips

- Use GPU if available (modify model_kwargs in code)
- Increase batch size for faster processing
- Monitor memory usage during large datasets

## Integration

This embedder can be integrated with the main application for:
- Drug name normalization
- Medication search functionality
- Clinical decision support
- Pharmacovigilance applications 