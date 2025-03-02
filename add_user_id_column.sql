-- Migration to add user_id column to document_pages table if it doesn't exist
DO $$
BEGIN
    -- Check if the column already exists
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'document_pages' AND column_name = 'user_id'
    ) THEN
        -- Add the user_id column
        ALTER TABLE document_pages ADD COLUMN user_id UUID NOT NULL;
        
        -- Create an index on user_id for better query performance
        CREATE INDEX idx_document_pages_user_id ON document_pages(user_id);
        
        RAISE NOTICE 'Added user_id column to document_pages table';
    ELSE
        RAISE NOTICE 'user_id column already exists in document_pages table';
    END IF;
END $$;