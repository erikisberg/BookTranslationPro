-- Glossary Management Tables
CREATE TABLE IF NOT EXISTS glossaries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    source_language TEXT,
    target_language TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS glossary_entries (
    id UUID PRIMARY KEY,
    glossary_id UUID NOT NULL REFERENCES glossaries(id) ON DELETE CASCADE,
    source_term TEXT NOT NULL,
    target_term TEXT NOT NULL,
    context TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Management Tables
CREATE TABLE IF NOT EXISTS document_folders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#3498db',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    folder_id UUID REFERENCES document_folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    original_filename TEXT,
    file_type TEXT,
    source_language TEXT,
    target_language TEXT,
    word_count INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    version_notes TEXT,
    tags TEXT[],
    status TEXT DEFAULT 'completed',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    folder_id UUID,
    title TEXT NOT NULL,
    description TEXT,
    original_filename TEXT,
    file_type TEXT,
    source_language TEXT,
    target_language TEXT,
    word_count INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    version_notes TEXT,
    tags TEXT[],
    status TEXT DEFAULT 'completed',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fix users table if needed (you might have a constraint issue)
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;

-- Create storage buckets if they don't exist
-- Note: This needs to be done through the Supabase interface or API
-- Create a bucket called 'documents' for storing document content