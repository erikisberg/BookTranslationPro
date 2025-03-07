# Database Schema

BookTranslationPro uses PostgreSQL via Supabase as its primary database. This document outlines the database schema and relationships between tables.

## Schema Diagram

```
┌─────────────┐       ┌────────────┐       ┌─────────────────┐
│   users     │       │ documents  │       │ document_pages  │
├─────────────┤       ├────────────┤       ├─────────────────┤
│ id          │◄──┐   │ id         │◄─┐    │ id              │
│ email       │   └───┤ user_id    │  └────┤ document_id     │
│ created_at  │       │ title      │       │ page_number     │
│ updated_at  │       │ folder     │       │ source_text     │
└─────────────┘       │ language   │       │ translated_text │
                      │ status     │       │ status          │
                      │ created_at │       │ created_at      │
                      │ updated_at │       │ updated_at      │
                      └────────────┘       └─────────────────┘
                             ▲                      ▲
                             │                      │
                      ┌──────┴───────┐     ┌───────┴────────┐
                      │ doc_versions │     │ page_versions  │
                      ├──────────────┤     ├────────────────┤
                      │ id           │     │ id             │
                      │ document_id  │     │ page_id        │
                      │ version      │     │ version        │
                      │ created_at   │     │ source_text    │
                      └──────────────┘     │ translated_text│
                                           └────────────────┘
┌─────────────┐       ┌────────────┐       ┌─────────────────┐
│  glossaries │       │glossary_   │       │  translation    │
├─────────────┤       │entries     │       │  memory         │
│ id          │◄──┐   ├────────────┤       ├─────────────────┤
│ user_id     │   └───┤ glossary_id│       │ id              │
│ name        │       │ source_term│       │ user_id         │
│ source_lang │       │ target_term│       │ source_text     │
│ target_lang │       │ created_at │       │ translated_text │
│ created_at  │       │            │       │ source_lang     │
└─────────────┘       └────────────┘       │ target_lang     │
                                           │ created_at      │
                                           └─────────────────┘
┌─────────────┐
│ assistants  │
├─────────────┤
│ id          │
│ user_id     │
│ name        │
│ assistant_id│
│ instructions│
│ created_at  │
└─────────────┘
```

## Tables

### users

Stores user account information.

| Column      | Type      | Description                      |
|-------------|-----------|----------------------------------|
| id          | UUID      | Primary key                      |
| email       | VARCHAR   | User's email address             |
| created_at  | TIMESTAMP | Account creation timestamp       |
| updated_at  | TIMESTAMP | Account last updated timestamp   |

### documents

Stores document metadata.

| Column      | Type      | Description                        |
|-------------|-----------|------------------------------------|
| id          | UUID      | Primary key                        |
| user_id     | UUID      | Reference to users.id              |
| title       | VARCHAR   | Document title                     |
| folder      | VARCHAR   | Folder/series name                 |
| language    | VARCHAR   | Source language code               |
| target_lang | VARCHAR   | Target language code               |
| status      | VARCHAR   | Document status                    |
| created_at  | TIMESTAMP | Document creation timestamp        |
| updated_at  | TIMESTAMP | Document last updated timestamp    |

### document_pages

Stores individual pages of documents.

| Column          | Type      | Description                     |
|-----------------|-----------|---------------------------------|
| id              | UUID      | Primary key                     |
| document_id     | UUID      | Reference to documents.id       |
| page_number     | INTEGER   | Page number within document     |
| source_text     | TEXT      | Original text content           |
| translated_text | TEXT      | Translated text content         |
| status          | VARCHAR   | Translation status              |
| created_at      | TIMESTAMP | Page creation timestamp         |
| updated_at      | TIMESTAMP | Page last updated timestamp     |

### doc_versions

Tracks document versions for change management.

| Column      | Type      | Description                     |
|-------------|-----------|---------------------------------|
| id          | UUID      | Primary key                     |
| document_id | UUID      | Reference to documents.id       |
| version     | INTEGER   | Version number                  |
| created_at  | TIMESTAMP | Version creation timestamp      |

### page_versions

Stores version history of page translations.

| Column          | Type      | Description                      |
|-----------------|-----------|----------------------------------|
| id              | UUID      | Primary key                      |
| page_id         | UUID      | Reference to document_pages.id   |
| version         | INTEGER   | Version number                   |
| source_text     | TEXT      | Original text at this version    |
| translated_text | TEXT      | Translated text at this version  |
| created_at      | TIMESTAMP | Version creation timestamp       |

### glossaries

Stores glossary metadata.

| Column      | Type      | Description                     |
|-------------|-----------|---------------------------------|
| id          | UUID      | Primary key                     |
| user_id     | UUID      | Reference to users.id           |
| name        | VARCHAR   | Glossary name                   |
| source_lang | VARCHAR   | Source language code            |
| target_lang | VARCHAR   | Target language code            |
| created_at  | TIMESTAMP | Glossary creation timestamp     |

### glossary_entries

Stores individual glossary term pairs.

| Column      | Type      | Description                      |
|-------------|-----------|----------------------------------|
| id          | UUID      | Primary key                      |
| glossary_id | UUID      | Reference to glossaries.id       |
| source_term | VARCHAR   | Term in source language          |
| target_term | VARCHAR   | Term in target language          |
| created_at  | TIMESTAMP | Entry creation timestamp         |

### translation_memory

Stores previously translated segments.

| Column          | Type      | Description                     |
|-----------------|-----------|---------------------------------|
| id              | UUID      | Primary key                     |
| user_id         | UUID      | Reference to users.id           |
| source_text     | TEXT      | Original text segment           |
| translated_text | TEXT      | Translated text segment         |
| source_lang     | VARCHAR   | Source language code            |
| target_lang     | VARCHAR   | Target language code            |
| created_at      | TIMESTAMP | Entry creation timestamp        |

### assistants

Stores OpenAI assistant configurations.

| Column       | Type      | Description                     |
|--------------|-----------|---------------------------------|
| id           | UUID      | Primary key                     |
| user_id      | UUID      | Reference to users.id           |
| name         | VARCHAR   | Assistant name                  |
| assistant_id | VARCHAR   | OpenAI assistant ID             |
| instructions | TEXT      | Assistant instructions          |
| created_at   | TIMESTAMP | Assistant creation timestamp    |

## Relationships

- One user can have many documents (1:N)
- One document can have many pages (1:N)
- One document can have many versions (1:N)
- One page can have many versions (1:N)
- One user can have many glossaries (1:N)
- One glossary can have many entries (1:N)
- One user can have many translation memory entries (1:N)
- One user can have many assistant configurations (1:N)

## Indexes

The following indexes are recommended for performance:

| Table             | Columns                            | Purpose                                 |
|-------------------|------------------------------------|-----------------------------------------|
| documents         | user_id, folder                    | Fast lookup of documents by folder      |
| document_pages    | document_id, page_number           | Fast lookup of pages by number          |
| document_pages    | document_id, status                | Fast lookup of pages by status          |
| doc_versions      | document_id, version               | Fast lookup of specific versions        |
| page_versions     | page_id, version                   | Fast lookup of specific page versions   |
| translation_memory| source_lang, target_lang, user_id  | Fast lookup of translation memories     |
| glossary_entries  | glossary_id                        | Fast lookup of terms in a glossary      |

## SQL Setup

The table creation scripts are available in `setup_tables.sql`.