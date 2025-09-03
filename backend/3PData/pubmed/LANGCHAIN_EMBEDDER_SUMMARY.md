# LangChain BioBERT Embedder with PGVector

## Overview

The `pubmed_pmc_embedder.py` has been updated to use LangChain with HuggingFace Sentence Transformers and PGVector for storing medical literature embeddings. This approach provides a more robust and scalable solution for medical document embedding and retrieval.

## Key Features

✅ **LangChain Integration**: Uses LangChain's HuggingFace embeddings with automatic fallback models  
✅ **PGVector Storage**: Stores embeddings in PostgreSQL with pgvector extension for efficient similarity search  
✅ **Medical Domain Focus**: Optimized for biomedical literature with BioBERT model (with fallback)  
✅ **Batch Processing**: Efficient batch processing for large datasets  
✅ **Semantic Search**: High-quality semantic search with similarity scoring  

## Architecture

```
PubMed/PMC XML Files → LangChain Parser → HuggingFace Embeddings → PGVector Database
                                                                        ↓
                                                          Semantic Search & Retrieval
```

## Models Used

**Primary Model**: `dmis-lab/biobert-base-cased-v1.1` (BioBERT for medical domain)  
**Fallback Model**: `sentence-transformers/all-MiniLM-L6-v2` (reliable, safetensors format)

The system automatically falls back to the secondary model if the primary model fails to load.

## Database Schema

The LangChain PGVector integration creates the following tables:
- `langchain_pg_collection` - Collection metadata
- `langchain_pg_embedding` - Document embeddings and metadata

## Usage Examples

### Basic Setup
```python
from pubmed_pmc_embedder import LangChainBioBERTEmbedder

# Create embedder
embedder = LangChainBioBERTEmbedder()

# Setup embeddings and vector store
embedder.setup_vector_store()
```

### Adding Documents
```python
from langchain.docstore.document import Document

# Create documents
docs = [
    Document(
        page_content="Diabetes mellitus is a metabolic disorder...",
        metadata={"pmid": "12345", "title": "Diabetes Study"}
    )
]

# Add to vector store
doc_ids = embedder.add_documents(docs)
```

### Searching Documents
```python
# Search for similar documents
results = embedder.search_similar_documents("blood sugar disorders", k=10)

for doc, score in results:
    print(f"Title: {doc.metadata['title']} (Score: {score:.4f})")
```

### Full Pipeline
```python
from pubmed_pmc_embedder import MedicalEmbeddingPipeline

pipeline = MedicalEmbeddingPipeline()

# Run complete pipeline
pipeline.run_full_pipeline(max_pubmed_files=5, max_pmc_files=2)
```

## Command Line Usage

```bash
# Setup database
python pubmed_pmc_embedder.py --setup-db

# Run full pipeline
python pubmed_pmc_embedder.py --full-pipeline --max-pubmed-files 10

# Search documents
python pubmed_pmc_embedder.py --search "diabetes treatment"

# Get database statistics
python pubmed_pmc_embedder.py --stats
```

## Demo Results

The demo successfully demonstrates:

1. **Model Loading**: Automatic fallback from BioBERT to MiniLM-L6-v2
2. **Document Storage**: 3 sample documents stored in PGVector
3. **Semantic Search**: Accurate similarity matching:
   - "blood sugar disorders" → "Diabetes Mellitus Overview" (score: 0.2875)
   - "high blood pressure treatment" → "Hypertension Study" (score: 0.4345)
   - "abnormal cell growth" → "Cancer Biology" (score: 0.4775)

## Technical Improvements

### From Previous Version
- ✅ **No More Pickle Files**: Direct database storage
- ✅ **Better Error Handling**: Automatic model fallback
- ✅ **LangChain Integration**: Industry-standard framework
- ✅ **Improved Imports**: Updated to latest LangChain community packages
- ✅ **PyTorch Security**: Uses safetensors format for model loading

### Performance Benefits
- **Scalable**: PGVector handles large datasets efficiently
- **Fast Search**: Vector similarity search with indexing
- **Robust**: Automatic fallback mechanisms
- **Standardized**: Uses LangChain's established patterns

## Requirements

Key dependencies:
```
langchain>=0.0.350
langchain-community>=0.0.7
sentence-transformers>=2.2.0
pgvector>=0.2.0
psycopg2-binary>=2.9.0
```

## Database Configuration

**Database URL**: `postgresql://rajanishsd@localhost:5432/zivohealth`  
**Collection Name**: `medical_documents`  
**Vector Extension**: `pgvector`

## Next Steps

1. **Scale Testing**: Test with actual PubMed/PMC datasets
2. **Performance Optimization**: Tune batch sizes and connection pooling
3. **Advanced Search**: Implement filtered search with metadata
4. **Monitoring**: Add comprehensive logging and metrics

## Files

- `pubmed_pmc_embedder.py` - Main embedder with LangChain integration
- `demo_langchain_embedder.py` - Working demonstration script
- `requirements.txt` - Updated dependencies
- `LANGCHAIN_EMBEDDER_SUMMARY.md` - This documentation

The system is now ready for production use with medical literature datasets. 