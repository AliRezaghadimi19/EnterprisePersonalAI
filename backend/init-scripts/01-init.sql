-- ==============================================================================
-- Enterprise AI Platform - PostgreSQL Initial Setup
-- Enables pgvector extension for RAG semantic search embeddings.
-- Note: Application tables are created automatically by the backend seeder
--       on first startup (app/services/seeder.py).
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension installed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension enabled successfully';
    ELSE
        RAISE WARNING 'pgvector extension NOT available';
    END IF;
END
$$;
