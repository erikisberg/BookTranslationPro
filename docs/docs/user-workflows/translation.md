# Translation Workflow

This document describes the technical implementation of the translation workflow in BookTranslationPro, from initial machine translation to final review and export.

## Workflow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Document    │     │ Machine     │     │ Human       │     │ AI Review   │
│ Upload      │────►│ Translation │────►│ Translation │────►│ & Export    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │                   │
      ▼                    ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Extract     │     │ Apply       │     │ Update      │     │ Generate    │
│ Content     │     │ Glossary    │     │ Translation │     │ Export      │
│ & Segment   │     │ & Memory    │     │ Memory      │     │ Files       │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## 1. Document Processing

### Technical Implementation

The document processing flow is handled by the following functions in `utils.py`:

```python
def extract_text_from_file(file_path, file_type):
    # Extracts text from various file formats
    # Uses multiple extraction methods with fallbacks
    
def segment_text(text, max_length=1000):
    # Segments text into manageable pages
    # Tries to maintain paragraph integrity
```

When a document is uploaded:

1. The file is stored in Supabase storage
2. Text extraction is performed based on file type
3. The extracted text is segmented into pages
4. Pages are stored in the `document_pages` table
5. Initial document metadata is created in the `documents` table

### Key Classes and Functions

- `app.py`: Contains route handlers for document upload
- `utils.py`: Contains text extraction and processing functions
- Database tables: `documents`, `document_pages`

## 2. Machine Translation

### Technical Implementation

Machine translation is performed via the DeepL API:

```python
def translate_document(document_id, user_id):
    # 1. Retrieves all pages for the document
    # 2. For each page, performs machine translation
    # 3. Updates the database with translations
    # 4. Marks document as machine-translated
```

The translation process:

1. Each page is sent to the DeepL API with target language
2. Translation memory is checked first to avoid redundant translations
3. If glossary exists, it's applied to the translation
4. Translated text is stored in the `document_pages` table
5. Document status is updated to reflect machine translation completion

### Key Classes and Functions

- `utils.py`: Contains the DeepL API integration
- `app.py`: Contains route handlers for initiating translation
- Database tables: `document_pages`, `translation_memory`

## 3. Human Translation

### Technical Implementation

The translation workspace is implemented as an interactive web interface:

```python
@app.route('/translation-workspace/<document_id>/<page_number>', methods=['GET', 'POST'])
def translation_workspace(document_id, page_number):
    # Renders the translation workspace for a specific page
    # Handles saving of user edits
```

When users edit translations:

1. Changes are saved to the `document_pages` table
2. Page status is updated to reflect human review
3. Page versions are tracked in the `page_versions` table
4. Translation memory is updated with the new translations

### Key Classes and Functions

- `app.py`: Contains route handlers for the translation workspace
- `templates/translation_workspace.html`: The UI for translation editing
- Database tables: `document_pages`, `page_versions`, `translation_memory`

## 4. AI Review and Export

### Technical Implementation

AI review uses OpenAI Assistant API:

```python
def review_translation(page_id, user_id):
    # 1. Retrieves page content
    # 2. Sends to OpenAI Assistant with appropriate instructions
    # 3. Processes suggestions and feedback
    # 4. Returns AI review results
```

Export functionality converts translations to various formats:

```python
def export_document(document_id, format, user_id):
    # 1. Retrieves all translated pages
    # 2. Formats content according to chosen format
    # 3. Generates output file
```

### Key Classes and Functions

- `create_assistant.py`: Contains OpenAI Assistant setup
- `app.py`: Contains route handlers for review and export
- `utils.py`: Contains export formatting functions
- Database tables: `document_pages`, `assistants`

## Data Flow Between Components

### Translation Memory Integration

```python
def update_translation_memory(source_text, translated_text, source_lang, target_lang, user_id):
    # Adds or updates translation memory entries
```

Translation memory is:
1. Checked before machine translation to avoid redundancy
2. Updated when users edit translations
3. Used to suggest translations for similar text

### Glossary Integration

```python
def apply_glossary(text, glossary_id, source_lang, target_lang):
    # Applies glossary terms to translations
```

Glossaries are:
1. Applied during machine translation
2. Highlighted in the translation workspace
3. Can be managed through the glossary interface

### Version Control System

```python
def create_page_version(page_id):
    # Creates a new version record for a page
```

Version control:
1. Tracks all changes to translations
2. Enables rollback to previous versions
3. Stores version history for audit purposes

## Error Handling and Recovery

The workflow implements several error handling mechanisms:

1. Failed API calls (DeepL, OpenAI) are retried with exponential backoff
2. Partial failures during batch operations are logged and reported
3. Auto-save functionality prevents data loss during translation
4. Database transactions ensure data consistency

## Performance Considerations

To maintain good performance for large documents:

1. Pages are processed asynchronously for machine translation
2. Translation memory reduces redundant API calls
3. UI optimizations in the translation workspace for smooth editing
4. Background processing for export of large documents