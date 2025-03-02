-- Function to execute SQL from application code
-- WARNING: This is for setup/admin purposes only and should be used with caution
-- You should implement proper security checks around this
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  EXECUTE query;
  RETURN 'Query executed successfully';
EXCEPTION
  WHEN OTHERS THEN
    RETURN 'Error: ' || SQLERRM;
END;
$$;

-- Make sure document_pages has the reviewed_by_ai column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'document_pages' AND column_name = 'reviewed_by_ai'
    ) THEN
        ALTER TABLE document_pages ADD COLUMN reviewed_by_ai BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added reviewed_by_ai column to document_pages table';
    ELSE
        RAISE NOTICE 'reviewed_by_ai column already exists in document_pages table';
    END IF;
END$$;