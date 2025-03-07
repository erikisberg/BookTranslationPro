# Tech Stack

BookTranslationPro is built on a modern technology stack designed for scalability, maintainability, and developer productivity. This document outlines the core technologies used in the application.

## Overview

The application uses a Python-based backend with Flask, PostgreSQL database via Supabase, and a server-rendered frontend with modern JavaScript enhancements.

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│    Frontend      │ │     Backend      │ │     Storage      │
├──────────────────┤ ├──────────────────┤ ├──────────────────┤
│ HTML/CSS/JS      │ │ Python 3.9+      │ │ PostgreSQL       │
│ Bootstrap 5      │ │ Flask            │ │ Supabase Storage │
│ jQuery           │ │ Supabase Client  │ │ File System      │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## Backend Technologies

### Core Framework

- **Python 3.9+**: Modern Python version with type hints support
- **Flask**: Lightweight WSGI web application framework
- **Gunicorn**: WSGI HTTP Server for production deployment

### Database & Authentication

- **Supabase**: Backend-as-a-Service platform providing:
  - PostgreSQL database
  - Authentication services
  - Storage capabilities
- **PostgreSQL**: Relational database for structured data storage

### Document Processing

- **PyPDF2/pdfplumber**: PDF text extraction libraries
- **python-docx**: Word document processing
- **textract**: Text extraction from various file formats
- **striprtf**: Rich Text Format processing
- **odfpy**: OpenDocument Format processing

### Translation & AI

- **DeepL API Client**: Machine translation integration
- **OpenAI API Client**: AI-assisted translation review
- **fuzzy-wuzzy**: Fuzzy string matching for translation memory

### Export & Document Generation

- **python-docx**: Word document generation
- **weasyprint**: HTML to PDF conversion
- **jinja2**: Templating for HTML exports

### Security & Validation

- **Flask-WTF**: Form validation and CSRF protection
- **python-dotenv**: Environment variable management
- **bleach**: HTML sanitization

### Monitoring & Analytics

- **PostHog**: User analytics
- **Logging**: Standard library logging with custom formatters

## Frontend Technologies

### UI Framework

- **Bootstrap 5**: Responsive CSS framework
- **Flask Templates (Jinja2)**: Server-side rendering
- **Custom CSS**: Application-specific styling

### JavaScript Libraries

- **jQuery**: DOM manipulation and AJAX requests
- **Summernote**: Rich text editor for translation workspace
- **mark.js**: Text highlighting for search and glossary terms
- **SortableJS**: Drag-and-drop reordering

### Asset Management

- **Flask Static Files**: Static file serving
- **SVG Icons**: Vector icons for UI elements

## DevOps & Infrastructure

### Development Tools

- **pip**: Python package manager
- **pytest**: Testing framework
- **flake8**: Linting
- **black**: Code formatting

### Deployment

- **Gunicorn**: Production WSGI server
- **dotenv**: Environment configuration
- **Docker** (optional): Containerization for deployment

### Version Control

- **Git**: Source code version control

## External Services

### Translation Services

- **DeepL API**: Machine translation provider
  - Features: High-quality translation, glossary support
  - Pricing: Based on character count
  - Documentation: [DeepL API Documentation](https://www.deepl.com/docs-api)

### AI Services

- **OpenAI API**: AI-powered translation review
  - Features: Contextual understanding, quality assessment
  - Models: GPT-4, Assistant API
  - Documentation: [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)

### Analytics

- **PostHog**: User behavior tracking
  - Features: Event tracking, funnels, retention
  - Documentation: [PostHog Documentation](https://posthog.com/docs)

### Database & Auth

- **Supabase**: Backend-as-a-Service
  - Features: PostgreSQL, Auth, Storage
  - Documentation: [Supabase Documentation](https://supabase.com/docs)

## Dependencies Management

Dependencies are managed through `requirements.txt` with pinned versions:

```
# Web Framework
flask==2.2.3
Werkzeug==2.2.3
gunicorn==20.1.0
python-dotenv==1.0.0

# Supabase
supabase==1.0.3
postgrest==0.10.6

# Document Processing
PyPDF2==3.0.1
pdfplumber==0.9.0
python-docx==0.8.11
textract==1.6.5
striprtf==0.0.22
odfpy==1.4.1

# Translation & AI
openai==0.27.8
deepl==1.14.0
fuzzywuzzy==0.18.0
python-Levenshtein==0.21.1

# Export
weasyprint==59.0
markdown==3.4.3

# Security & Validation
Flask-WTF==1.1.1
bleach==6.0.0
email-validator==2.0.0

# Utilities
python-slugify==8.0.1
posthog==2.4.0
```

## Development Environment

### Recommended Setup

- **IDE**: VS Code with Python extension
- **Python Environment**: Virtual environment (venv)
- **Database**: Local Supabase or PostgreSQL instance
- **Environment Variables**: Local .env file

### Environment Configuration

Example `.env` file for development:

```
# Flask
FLASK_APP=app.py
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key-change-in-production

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

# API Keys
DEEPL_API_KEY=your-deepl-api-key
OPENAI_API_KEY=your-openai-api-key
POSTHOG_API_KEY=your-posthog-api-key
```

## Performance Considerations

The tech stack is optimized for performance in several ways:

1. **Supabase PostgreSQL**: Efficient database queries with proper indexing
2. **Translation Memory**: Reduces expensive API calls by caching translations
3. **Static File Serving**: CSS/JS assets are minified and cached
4. **Lazy Loading**: Document pages are loaded on-demand as needed
5. **Connection Pooling**: Database connections are pooled for efficiency

## Security Considerations

Security measures implemented in the tech stack:

1. **Authentication**: Supabase Auth with session management
2. **CSRF Protection**: Flask-WTF for form protection
3. **Input Sanitization**: Bleach for HTML sanitization
4. **Parameterized Queries**: All database queries use parameterization
5. **Environment Variables**: Sensitive credentials stored in environment variables
6. **Content Security Policy**: Restrictive CSP headers in production

## Internationalization

The application supports multiple languages through:

1. **DeepL API**: Support for numerous language pairs
2. **Unicode Handling**: Proper UTF-8 encoding throughout
3. **Locale-Aware Processing**: Date and number formatting based on locale

## Monitoring & Logging

The tech stack includes comprehensive monitoring capabilities:

1. **Structured Logging**: JSON-formatted logs with severity levels
2. **PostHog Events**: User actions tracked as events
3. **Error Tracking**: Detailed error reporting with context
4. **API Usage Monitoring**: Tracking of external API consumption