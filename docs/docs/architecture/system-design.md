# System Design

This document outlines the system architecture and design of BookTranslationPro, explaining how components interact and how the application is structured.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Client Layer                               │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Web Browser │  │  Translation │  │   Document  │  │  Settings   │ │
│  │  Interface  │  │  Workspace   │  │ Management  │  │ & Profile   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Application Layer                          │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │    Auth     │  │  Document    │  │ Translation │  │   Export    │ │
│  │   Module    │  │  Processing  │  │   Engine    │  │   Engine    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Glossary   │  │ Translation  │  │ Version     │  │  Analytics  │ │
│  │  Manager    │  │   Memory     │  │ Control     │  │   Module    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Integration Layer                           │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Supabase   │  │    DeepL    │  │   OpenAI    │  │   PostHog   │ │
│  │  Client     │  │     API     │  │     API     │  │     API     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Storage Layer                              │
│                                                                      │
│  ┌─────────────────────────┐        ┌─────────────────────────────┐ │
│  │    PostgreSQL Database  │        │      File Storage           │ │
│  │    (Supabase)           │        │      (Supabase Storage)     │ │
│  └─────────────────────────┘        └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Layer Descriptions

### 1. Client Layer

The client layer consists of browser-based interfaces that interact with the Flask backend:

- **Web Browser Interface**: General navigation and user interface
- **Translation Workspace**: Interactive interface for editing translations
- **Document Management**: Upload, organization, and version control of documents
- **Settings & Profile**: User profile, API settings, and preferences

This layer is built with:
- HTML templates with Jinja2 templating
- Bootstrap 5 for responsive layouts
- JavaScript for interactive features
- CSS for custom styling

### 2. Application Layer

The application layer contains the core business logic implemented as Flask routes and Python modules:

- **Auth Module**: User authentication, authorization, and session management
- **Document Processing**: Text extraction, segmentation, and format handling
- **Translation Engine**: Core translation functionality with memory and AI capabilities
- **Export Engine**: Document format conversion and download generation
- **Glossary Manager**: Terminology management and application
- **Translation Memory**: Storage and retrieval of previous translations
- **Version Control**: Document and page version tracking
- **Analytics Module**: Usage tracking and reporting

This layer is built with:
- Flask web framework for routing and request handling
- Python business logic organized by module
- SQLAlchemy for ORM (limited usage)
- Custom utilities for specialized processing

### 3. Integration Layer

The integration layer connects the application to external services:

- **Supabase Client**: Authentication and database operations
- **DeepL API**: Machine translation services
- **OpenAI API**: AI-assisted translation review
- **PostHog API**: User analytics and tracking

This layer is built with:
- API client libraries for each service
- Abstraction layers to handle API-specific details
- Retry mechanisms and error handling
- Rate limiting and quota management

### 4. Storage Layer

The storage layer manages data persistence:

- **PostgreSQL Database**: Relational database (via Supabase)
- **File Storage**: Document storage and exports (via Supabase Storage)

## Request Flow

To illustrate how the system works, here's a typical request flow for document translation:

```
1. User uploads document in Web UI
   │
2. Document Processing module extracts text
   │
3. Text is segmented into pages and stored in database
   │
4. DeepL API is called to provide initial translation
   │
5. User edits translations in Translation Workspace
   │
6. Changes are saved to database
   │
7. Translation Memory is updated
   │
8. User requests AI review
   │
9. OpenAI API is called to review translation
   │
10. User exports document
    │
11. Export Engine generates document in selected format
```

## Stateless Architecture

BookTranslationPro is designed as a primarily stateless application:

- **User state** is maintained through Flask sessions
- **Document state** is stored in the database
- **Workflow state** is stored in the database
- **API connections** are stateless and created per request

This architecture allows for future horizontal scaling, as application servers can be added without shared state requirements.

## Data Flow

### Document Upload Flow

```
┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│   Browser │     │   Flask   │     │ Document  │     │  Supabase │
│           │     │   App     │     │ Processing│     │           │
└─────┬─────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
      │                 │                 │                 │
      │ Upload File     │                 │                 │
      │────────────────►│                 │                 │
      │                 │                 │                 │
      │                 │ Process File    │                 │
      │                 │────────────────►│                 │
      │                 │                 │                 │
      │                 │                 │ Extract Text    │
      │                 │                 │◄───────────────►│
      │                 │                 │                 │
      │                 │                 │ Store Document  │
      │                 │                 │────────────────►│
      │                 │                 │                 │
      │                 │ Document ID     │                 │
      │                 │◄────────────────│                 │
      │                 │                 │                 │
      │ Redirect to     │                 │                 │
      │ Document View   │                 │                 │
      │◄────────────────│                 │                 │
      │                 │                 │                 │
```

### Translation Flow

```
┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│   Browser │     │   Flask   │     │ Translation│     │  DeepL    │
│           │     │   App     │     │   Engine   │     │   API     │
└─────┬─────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
      │                 │                 │                 │
      │ Request         │                 │                 │
      │ Translation     │                 │                 │
      │────────────────►│                 │                 │
      │                 │                 │                 │
      │                 │ Translate Doc   │                 │
      │                 │────────────────►│                 │
      │                 │                 │                 │
      │                 │                 │ Check TM Cache  │
      │                 │                 │─────┐          │
      │                 │                 │     │          │
      │                 │                 │◄────┘          │
      │                 │                 │                │
      │                 │                 │ API Request    │
      │                 │                 │───────────────►│
      │                 │                 │                │
      │                 │                 │ API Response   │
      │                 │                 │◄───────────────│
      │                 │                 │                │
      │                 │                 │ Update TM Cache│
      │                 │                 │─────┐          │
      │                 │                 │     │          │
      │                 │                 │◄────┘          │
      │                 │                 │                │
      │                 │ Translated Doc  │                │
      │                 │◄────────────────│                │
      │                 │                 │                │
      │ View Translation│                 │                │
      │◄────────────────│                 │                │
      │                 │                 │                │
```

## Key Design Patterns

BookTranslationPro implements several design patterns:

### Repository Pattern

Database access is abstracted into repository-like functions:

```python
# Example repository pattern
def get_document_by_id(document_id):
    """Retrieves document by ID"""
    return supabase.table("documents").select("*").eq("id", document_id).single().execute().data

def update_document_status(document_id, status):
    """Updates document status"""
    return supabase.table("documents").update({"status": status}).eq("id", document_id).execute()
```

### Strategy Pattern

Various strategies are used for text extraction based on file type:

```python
# Strategy pattern for text extraction
extractors = {
    'pdf': extract_text_from_pdf,
    'docx': extract_text_from_docx,
    'txt': extract_text_from_txt,
    # more strategies...
}

def extract_text(file_path, file_type):
    """Extracts text using appropriate strategy"""
    extractor = extractors.get(file_type)
    if not extractor:
        raise UnsupportedFormatError(f"No extractor for {file_type}")
    return extractor(file_path)
```

### Decorator Pattern

Authentication and logging are implemented using decorators:

```python
# Decorator pattern for authentication
@login_required
def protected_route():
    # Only accessible when logged in
    return "Protected content"

# Decorator pattern for logging
@log_function_call
def important_function():
    # Function call will be logged
    return perform_operation()
```

### Factory Method Pattern

Creating document exporters based on format type:

```python
# Factory method for exporters
def create_exporter(format_type):
    """Creates appropriate exporter based on format"""
    if format_type == 'pdf':
        return PDFExporter()
    elif format_type == 'docx':
        return DocxExporter()
    elif format_type == 'txt':
        return TextExporter()
    else:
        raise ValueError(f"Unsupported format: {format_type}")
```

## Scalability Considerations

The application is designed with potential scaling in mind:

1. **Database Scaling**:
   - Implemented through Supabase (PostgreSQL)
   - Indexing for common queries
   - Connection pooling for efficiency

2. **Stateless Design**:
   - Application servers can be added horizontally
   - No shared memory requirements between instances

3. **Background Processing**:
   - Long-running tasks (like translation of large documents) can be moved to background workers
   - Progress tracking implementation for user feedback

4. **Caching Strategy**:
   - Translation memory to reduce API calls
   - Document caching for frequently accessed content

## Security Architecture

Security measures implemented within the architecture:

1. **Authentication**:
   - Session-based authentication via Supabase
   - Role-based access control
   - CSRF protection for forms

2. **Data Protection**:
   - API keys stored in environment variables
   - Sensitive operations require authentication
   - Database access through parameterized queries

3. **External API Security**:
   - Rate limiting for API calls
   - Quota monitoring and alerts
   - Secure storage of API credentials

4. **Input Validation**:
   - Form validation on both client and server
   - File type verification
   - Size limitations for uploads