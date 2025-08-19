# PMC Document Search Tool

A comprehensive search tool for your chunked PMC documents with semantic search capabilities.

## Features

✅ **Semantic Search** - Find documents by meaning, not just keywords  
✅ **Chunk Relationships** - Track and reconstruct multi-chunk documents  
✅ **Context Expansion** - Get surrounding chunks for better context  
✅ **PMC ID Search** - Find all chunks for a specific PMC document  
✅ **Document Reconstruction** - Rebuild full documents from chunks  
✅ **Interactive Mode** - Command-line interface for exploration  
✅ **Source Filtering** - Search within specific archives  

## Quick Start

### 1. Basic Search
```bash
python pmc_search.py "diabetes treatment"
```

### 2. Interactive Mode
```bash
python pmc_search.py --interactive
```

### 3. Search by PMC ID
```bash
python pmc_search.py --pmc PMC123456
```

### 4. Reconstruct Full Document
```bash
python pmc_search.py --reconstruct PMC123456
```

## Command Line Options

```bash
python pmc_search.py [options] "query"

Options:
  --interactive, -i     Interactive search mode
  --pmc PMC_ID         Search by PMC ID
  --reconstruct PMC_ID  Reconstruct full document
  --context N          Include N surrounding chunks (default: 1)
  --count N, -k N      Number of results (default: 5)
  --min-score X        Minimum similarity score (default: 0.0)
```

## Interactive Commands

When in interactive mode (`--interactive`):

```
> search diabetes treatment     # Semantic search
> pmc PMC123456                # Get all chunks for PMC
> reconstruct PMC123456        # Rebuild full document
> context diabetes treatment   # Search with context chunks
> source archive_name          # Search in specific source
> stats                        # Database statistics
> quit                         # Exit
```

## Python API Usage

```python
from pmc_search import PMCSearcher

# Initialize
searcher = PMCSearcher()

# Basic search
results = searcher.search("diabetes treatment", k=5)

# Search by PMC ID
chunks = searcher.search_by_pmc_id("PMC123456")

# Reconstruct document
full_text = searcher.reconstruct_document("PMC123456")

# Search with context
context_results = searcher.search_with_context("diabetes", context_chunks=2)

# Get database stats
stats = searcher.get_database_stats()
```

## Search Result Format

Each search result includes:
- **Document content** (chunk text)
- **Similarity score** (0.0 to 1.0)
- **PMC ID** (document identifier)
- **Chunk information** (chunk 2/5, etc.)
- **Source archive** (which file it came from)
- **Title** (document title)

## Chunk Relationships

Documents are automatically chunked and related:
- **Same PMC ID** = Same original document
- **Chunk index** = Position within document
- **Overlap** = 1000 characters between chunks
- **Metadata** = Preserves relationships

## Examples

### Search for Cancer Research
```bash
python pmc_search.py "cancer immunotherapy clinical trial"
```

### Find All Diabetes Papers
```bash
python pmc_search.py "diabetes" --count 10
```

### High-Precision Search
```bash
python pmc_search.py "CRISPR gene editing" --min-score 0.8
```

### Interactive Exploration
```bash
python pmc_search.py --interactive
> search machine learning healthcare
> pmc PMC123456  # From results above
> reconstruct PMC123456  # Get full paper
```

## Database Statistics

Check your collection size:
```bash
python pmc_search.py --interactive
> stats
```

Shows:
- Total chunks stored
- Unique documents
- Source archives processed

## Troubleshooting

**No results found:**
- Try broader search terms
- Lower the `--min-score` threshold
- Check database connection

**Slow searches:**
- Reduce `--count` parameter
- Use more specific queries
- Check GPU availability for embeddings

**Memory issues:**
- Reduce batch sizes in searches
- Use `--min-score` to filter results
- Close other applications 