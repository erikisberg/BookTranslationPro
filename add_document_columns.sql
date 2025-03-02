-- Migration to add progress tracking columns to documents table
DO $$
BEGIN
    -- Add total_pages column if it doesn't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'total_pages'
    ) THEN
        ALTER TABLE documents ADD COLUMN total_pages INTEGER DEFAULT 0;
        RAISE NOTICE 'Added total_pages column to documents table';
    ELSE
        RAISE NOTICE 'total_pages column already exists in documents table';
    END IF;

    -- Add completed_pages column if it doesn't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'completed_pages'
    ) THEN
        ALTER TABLE documents ADD COLUMN completed_pages INTEGER DEFAULT 0;
        RAISE NOTICE 'Added completed_pages column to documents table';
    ELSE
        RAISE NOTICE 'completed_pages column already exists in documents table';
    END IF;

    -- Add overall_progress column if it doesn't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'overall_progress'
    ) THEN
        ALTER TABLE documents ADD COLUMN overall_progress INTEGER DEFAULT 0;
        RAISE NOTICE 'Added overall_progress column to documents table';
    ELSE
        RAISE NOTICE 'overall_progress column already exists in documents table';
    END IF;
END $$;