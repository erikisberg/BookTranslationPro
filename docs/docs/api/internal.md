# Internal API

BookTranslationPro implements several internal API endpoints for frontend-backend communication. This document outlines these endpoints, their parameters, and response formats.

## API Overview

The internal API provides endpoints for:

1. Document management
2. Translation operations
3. Glossary and translation memory management
4. User settings and preferences
5. Export functionality

## Authentication

All API endpoints require authentication, which is handled through Flask sessions. The `@login_required` decorator enforces this requirement.

```python
@app.route('/api/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    # This endpoint requires authentication
    user_id = session.get('user_id')
    # ...
```

## Common Response Format

All API endpoints follow a common JSON response format:

```json
{
  "success": true|false,
  "data": { ... },  // Present on success
  "error": "Error message"  // Present on failure
}
```

## Document Management API

### Get Documents List

Retrieves a list of documents for the current user, with optional filtering.

**Endpoint:** `GET /api/documents`

**Query Parameters:**
- `folder` (optional): Filter by folder name
- `language` (optional): Filter by source language
- `status` (optional): Filter by document status

**Response:**
```json
{
  "success": true,
  "data": {
    "documents": [
      {
        "id": "doc-uuid",
        "title": "Document Title",
        "folder": "Folder Name",
        "language": "en",
        "target_lang": "fr",
        "status": "in_progress",
        "created_at": "2023-03-15T12:00:00Z",
        "updated_at": "2023-03-16T10:00:00Z",
        "page_count": 5,
        "completion_percentage": 60
      },
      // Additional documents...
    ]
  }
}
```

### Get Document Details

Retrieves detailed information about a specific document.

**Endpoint:** `GET /api/documents/<document_id>`

**Response:**
```json
{
  "success": true,
  "data": {
    "document": {
      "id": "doc-uuid",
      "title": "Document Title",
      "folder": "Folder Name",
      "language": "en",
      "target_lang": "fr",
      "status": "in_progress",
      "created_at": "2023-03-15T12:00:00Z",
      "updated_at": "2023-03-16T10:00:00Z",
      "user_id": "user-uuid"
    },
    "pages": [
      {
        "id": "page-uuid",
        "page_number": 1,
        "status": "translated",
        "has_content": true
      },
      // Additional pages...
    ],
    "versions": [
      {
        "version": 1,
        "created_at": "2023-03-15T12:00:00Z"
      },
      // Additional versions...
    ]
  }
}
```

### Create Document

Creates a new document from an uploaded file.

**Endpoint:** `POST /api/documents`

**Content Type:** `multipart/form-data`

**Form Parameters:**
- `file`: Document file
- `title`: Document title
- `language`: Source language code
- `target_lang`: Target language code
- `folder` (optional): Folder/category name

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "title": "Document Title",
    "page_count": 5,
    "status": "processing"
  }
}
```

### Update Document

Updates document metadata.

**Endpoint:** `PUT /api/documents/<document_id>`

**Request Body:**
```json
{
  "title": "Updated Title",
  "folder": "New Folder",
  "target_lang": "es"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "updated_fields": ["title", "folder", "target_lang"]
  }
}
```

### Delete Document

Deletes a document and all its pages.

**Endpoint:** `DELETE /api/documents/<document_id>`

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Document deleted successfully"
  }
}
```

## Document Pages API

### Get Document Page

Retrieves content for a specific page of a document.

**Endpoint:** `GET /api/documents/<document_id>/pages/<page_number>`

**Response:**
```json
{
  "success": true,
  "data": {
    "page": {
      "id": "page-uuid",
      "document_id": "doc-uuid",
      "page_number": 1,
      "source_text": "Original text content",
      "translated_text": "Translated text content",
      "status": "translated",
      "created_at": "2023-03-15T12:00:00Z",
      "updated_at": "2023-03-16T10:00:00Z"
    }
  }
}
```

### Update Page Translation

Updates the translation for a document page.

**Endpoint:** `PUT /api/documents/<document_id>/pages/<page_number>`

**Request Body:**
```json
{
  "translated_text": "Updated translation content",
  "status": "translated"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "page_id": "page-uuid",
    "document_id": "doc-uuid",
    "page_number": 1,
    "updated_at": "2023-03-16T12:00:00Z"
  }
}
```

## Translation API

### Translate Document

Initiates machine translation for a document.

**Endpoint:** `POST /api/translate/document/<document_id>`

**Request Body:**
```json
{
  "use_glossary": true,
  "use_translation_memory": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "job_id": "job-uuid",
    "status": "processing",
    "message": "Translation started"
  }
}
```

### Translate Page

Translates a specific page using machine translation.

**Endpoint:** `POST /api/translate/page/<page_id>`

**Request Body:**
```json
{
  "use_glossary": true,
  "use_translation_memory": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "page_id": "page-uuid",
    "document_id": "doc-uuid",
    "page_number": 1,
    "translated_text": "Translated content",
    "status": "machine_translated"
  }
}
```

### Review Translation

Requests AI review of a translation.

**Endpoint:** `POST /api/translate/review/<page_id>`

**Response:**
```json
{
  "success": true,
  "data": {
    "review": {
      "page_id": "page-uuid",
      "accuracy": "The translation accurately captures the original meaning.",
      "style": "Consider using more idiomatic expressions in the target language.",
      "terminology": "Several technical terms could be improved for consistency.",
      "suggestions": [
        {
          "original": "technical approach",
          "suggestion": "approche technique"
        },
        // Additional suggestions...
      ],
      "overall_score": 8.5
    }
  }
}
```

## Glossary API

### Get Glossaries

Retrieves the user's glossaries.

**Endpoint:** `GET /api/glossaries`

**Response:**
```json
{
  "success": true,
  "data": {
    "glossaries": [
      {
        "id": "glossary-uuid",
        "name": "Technical Terms",
        "source_lang": "en",
        "target_lang": "fr",
        "entry_count": 25,
        "created_at": "2023-03-10T12:00:00Z"
      },
      // Additional glossaries...
    ]
  }
}
```

### Get Glossary Entries

Retrieves entries for a specific glossary.

**Endpoint:** `GET /api/glossaries/<glossary_id>/entries`

**Response:**
```json
{
  "success": true,
  "data": {
    "glossary": {
      "id": "glossary-uuid",
      "name": "Technical Terms",
      "source_lang": "en",
      "target_lang": "fr"
    },
    "entries": [
      {
        "id": "entry-uuid",
        "source_term": "API",
        "target_term": "API",
        "created_at": "2023-03-10T12:00:00Z"
      },
      // Additional entries...
    ]
  }
}
```

### Create Glossary

Creates a new glossary.

**Endpoint:** `POST /api/glossaries`

**Request Body:**
```json
{
  "name": "Literary Terms",
  "source_lang": "en",
  "target_lang": "es"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "glossary_id": "glossary-uuid",
    "name": "Literary Terms",
    "source_lang": "en",
    "target_lang": "es",
    "created_at": "2023-03-18T12:00:00Z"
  }
}
```

### Add Glossary Entry

Adds a new entry to a glossary.

**Endpoint:** `POST /api/glossaries/<glossary_id>/entries`

**Request Body:**
```json
{
  "source_term": "protagonist",
  "target_term": "protagonista"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "entry_id": "entry-uuid",
    "glossary_id": "glossary-uuid",
    "source_term": "protagonist",
    "target_term": "protagonista"
  }
}
```

## Translation Memory API

### Search Translation Memory

Searches the translation memory for similar segments.

**Endpoint:** `GET /api/translation-memory/search`

**Query Parameters:**
- `text`: Text to search for
- `source_lang`: Source language code
- `target_lang`: Target language code
- `min_similarity` (optional): Minimum similarity score (0-100)

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "tm-uuid",
        "source_text": "Original text segment",
        "translated_text": "Translated text segment",
        "similarity": 95,
        "created_at": "2023-03-10T12:00:00Z"
      },
      // Additional results...
    ]
  }
}
```

### Add to Translation Memory

Adds an entry to the translation memory.

**Endpoint:** `POST /api/translation-memory/entries`

**Request Body:**
```json
{
  "source_text": "This is a sample text.",
  "translated_text": "Ceci est un exemple de texte.",
  "source_lang": "en",
  "target_lang": "fr"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "entry_id": "tm-uuid",
    "created_at": "2023-03-18T12:00:00Z"
  }
}
```

## Export API

### Export Document

Exports a document in the specified format.

**Endpoint:** `POST /api/export/<document_id>`

**Request Body:**
```json
{
  "format": "docx",
  "include_original": false,
  "include_notes": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "export_url": "/download/exports/document-name.docx",
    "format": "docx",
    "expires_at": "2023-03-18T14:00:00Z"
  }
}
```

## Error Handling

When an error occurs, the API returns a JSON response with `success: false` and an error message:

```json
{
  "success": false,
  "error": "Document not found",
  "code": "NOT_FOUND"
}
```

Common error codes:

| Code | Description |
|------|-------------|
| `UNAUTHORIZED` | User is not authenticated |
| `FORBIDDEN` | User is not authorized to access the resource |
| `NOT_FOUND` | Requested resource not found |
| `BAD_REQUEST` | Invalid request parameters |
| `VALIDATION_ERROR` | Request validation failed |
| `API_ERROR` | Error from external API (DeepL, OpenAI) |
| `SERVER_ERROR` | Internal server error |

## Rate Limiting

API endpoints implement rate limiting to prevent abuse:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1678987789
```

When rate limit is exceeded, the API returns status code 429 with an error response:

```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "code": "RATE_LIMITED",
  "retry_after": 60
}
```

## API Implementation

The API is implemented in Flask routes, typically organized in the main `app.py` file or in modular blueprint files:

```python
@app.route('/api/documents', methods=['GET'])
@login_required
def get_documents():
    """API endpoint to list documents"""
    user_id = session.get('user_id')
    folder = request.args.get('folder')
    language = request.args.get('language')
    status = request.args.get('status')
    
    try:
        # Query documents based on filters
        documents = get_user_documents(user_id, folder, language, status)
        
        # Return success response
        return jsonify({
            "success": True,
            "data": {
                "documents": documents
            }
        })
    except Exception as e:
        # Log error
        logger.error(f"Error fetching documents: {e}")
        
        # Return error response
        return jsonify({
            "success": False,
            "error": "Failed to retrieve documents",
            "code": "SERVER_ERROR"
        }), 500
```

## Using the API in Frontend

Example of using the API from frontend JavaScript:

```javascript
// Fetch document list
async function getDocuments(folder = null) {
    try {
        let url = '/api/documents';
        if (folder) {
            url += `?folder=${encodeURIComponent(folder)}`;
        }
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            },
            credentials: 'same-origin'
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Unknown error');
        }
        
        return result.data.documents;
    } catch (error) {
        console.error('Error fetching documents:', error);
        showErrorMessage('Failed to load documents');
        return [];
    }
}

// Update page translation
async function saveTranslation(documentId, pageNumber, translatedText) {
    try {
        const response = await fetch(`/api/documents/${documentId}/pages/${pageNumber}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                translated_text: translatedText,
                status: 'translated'
            })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Unknown error');
        }
        
        showSuccessMessage('Translation saved successfully');
        return true;
    } catch (error) {
        console.error('Error saving translation:', error);
        showErrorMessage('Failed to save translation');
        return false;
    }
}
```