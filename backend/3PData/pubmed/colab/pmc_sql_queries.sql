-- PMC Document Extraction SQL Queries
-- =====================================

-- 1. GET ALL CHUNKS FOR A SPECIFIC PMC ID
-- Returns all chunks for a document, ordered by chunk index
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    cmetadata->>'filename' as filename,
    cmetadata->>'source_archive' as source_archive,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    CAST(cmetadata->>'chunk_start' AS INTEGER) as chunk_start,
    CAST(cmetadata->>'chunk_end' AS INTEGER) as chunk_end,
    LENGTH(document) as chunk_length,
    document as content
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
ORDER BY CAST(cmetadata->>'chunk_index' AS INTEGER);

-- 2. RECONSTRUCT FULL DOCUMENT (Concatenated)
-- Combines all chunks back into the original document
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    cmetadata->>'filename' as filename,
    COUNT(*) as total_chunks,
    SUM(LENGTH(document)) as total_length,
    STRING_AGG(document, '' ORDER BY CAST(cmetadata->>'chunk_index' AS INTEGER)) as full_document
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
GROUP BY 
    cmetadata->>'pmc_id',
    cmetadata->>'title', 
    cmetadata->>'filename';

-- 3. GET DOCUMENT METADATA ONLY
-- Returns just the metadata without content
SELECT DISTINCT
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    cmetadata->>'filename' as filename,
    cmetadata->>'source_archive' as source_archive,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    cmetadata->>'processed_date' as processed_date
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
LIMIT 1;

-- 4. GET SPECIFIC CHUNK BY INDEX
-- Returns a specific chunk from a document
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    document as content
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
  AND CAST(cmetadata->>'chunk_index' AS INTEGER) = 0;  -- First chunk (0-indexed)

-- 5. SEARCH PMC IDs BY PATTERN
-- Find PMC IDs that match a pattern
SELECT DISTINCT
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    COUNT(*) as chunk_count
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' LIKE 'PMC122%'  -- PMC IDs starting with PMC122
GROUP BY cmetadata->>'pmc_id', cmetadata->>'title'
ORDER BY cmetadata->>'pmc_id';

-- 6. GET MULTIPLE DOCUMENTS BY PMC ID LIST
-- Extract several documents at once
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    document as content
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' IN ('PMC12205352', 'PMC12226897', 'PMC11039563')
ORDER BY cmetadata->>'pmc_id', CAST(cmetadata->>'chunk_index' AS INTEGER);

-- 7. GET DOCUMENT STATISTICS
-- Show chunk distribution for a PMC ID
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    COUNT(*) as total_chunks,
    MIN(LENGTH(document)) as min_chunk_size,
    MAX(LENGTH(document)) as max_chunk_size,
    AVG(LENGTH(document))::INTEGER as avg_chunk_size,
    SUM(LENGTH(document)) as total_document_size
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
GROUP BY cmetadata->>'pmc_id', cmetadata->>'title';

-- 8. FULL TEXT SEARCH WITHIN A SPECIFIC PMC ID
-- Search for content within a specific document
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    SUBSTRING(document, 1, 200) as preview,
    LENGTH(document) as chunk_length
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
  AND document ILIKE '%diabetes%'  -- Search for specific content
ORDER BY CAST(cmetadata->>'chunk_index' AS INTEGER);

-- 9. GET FIRST AND LAST CHUNKS (Abstract & Conclusion)
-- Useful for getting document summary
(SELECT 
    'First Chunk' as chunk_type,
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    document as content
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
  AND CAST(cmetadata->>'chunk_index' AS INTEGER) = 0)

UNION ALL

(SELECT 
    'Last Chunk' as chunk_type,
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    document as content
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
  AND CAST(cmetadata->>'chunk_index' AS INTEGER) = (
    SELECT MAX(CAST(cmetadata->>'chunk_index' AS INTEGER))
    FROM langchain_pg_embedding 
    WHERE cmetadata->>'pmc_id' = 'PMC12205352'
  ));

-- 10. EXPORT DOCUMENT TO CSV-READY FORMAT
-- Format suitable for export or analysis
SELECT 
    cmetadata->>'pmc_id' as pmc_id,
    cmetadata->>'title' as title,
    cmetadata->>'filename' as filename,
    cmetadata->>'source_archive' as source_archive,
    CAST(cmetadata->>'chunk_index' AS INTEGER) as chunk_index,
    CAST(cmetadata->>'total_chunks' AS INTEGER) as total_chunks,
    LENGTH(document) as chunk_length,
    REPLACE(REPLACE(document, E'\n', ' '), E'\r', '') as clean_content  -- Remove newlines
FROM langchain_pg_embedding 
WHERE cmetadata->>'pmc_id' = 'PMC12205352'  -- Replace with your PMC ID
ORDER BY CAST(cmetadata->>'chunk_index' AS INTEGER); 