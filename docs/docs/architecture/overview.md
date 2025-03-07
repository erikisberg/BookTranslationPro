# Architecture Overview

## System Architecture

BookTranslationPro follows a classic web application architecture with some specific components to handle document processing and AI integrations:

```
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│   Frontend    │      │    Backend    │      │   Database    │
│  (Templates,  │◄────►│  (Flask App)  │◄────►│  (Supabase)   │
│   Bootstrap)  │      │               │      │               │
└───────────────┘      └───────┬───────┘      └───────────────┘
                               │
                               ▼
        ┌─────────────────────┬─────────────────────┐
        │                     │                     │
┌───────────────┐    ┌────────┴────────┐    ┌───────────────┐
│  Document     │    │  Translation    │    │  External     │
│  Processing   │    │  Engine         │    │  APIs         │
│  Pipeline     │    │                 │    │  (DeepL,      │
│               │    │                 │    │   OpenAI)     │
└───────────────┘    └─────────────────┘    └───────────────┘
```

## Core Components

### Web Layer (Flask Application)

The Flask application handles HTTP requests, session management, and serves web pages. It's organized into routes that correspond to different functionalities:

- Authentication routes
- Document management routes
- Translation workspace routes
- Administration routes
- API endpoints

### Persistence Layer (Supabase)

Supabase provides both database and authentication services:

- PostgreSQL database for storing all application data
- Authentication services for user management
- Storage capabilities for document files and exports

### Document Processing Pipeline

Responsible for:
- Extracting text from various file formats (PDF, DOCX, TXT, etc.)
- Segmenting text into pages for translation
- Creating document versions and tracking changes

### Translation Engine

Handles the core translation functionality:
- Integration with DeepL API for machine translation
- Translation memory management
- Glossary application
- AI review process via OpenAI

## Data Flow

1. **Document Upload Flow**:
   - User uploads document → Document processing extracts text → Text is segmented → Machine translation is applied → Document is ready for human translation

2. **Translation Workflow**:
   - User selects document → Loads translation workspace → Edits translations → Saves progress → System tracks changes and versions

3. **Export Flow**:
   - User selects export format → System retrieves translated content → Formats according to export requirements → Generates downloadable file

## Design Principles

The architecture follows these key principles:

1. **Separation of Concerns**: Clear boundaries between document processing, translation, and web presentation
2. **Fail-safe Operations**: Graceful handling of API failures with retry mechanisms
3. **Caching for Performance**: Translation memory and caching to reduce API calls
4. **Progressive Enhancement**: Core functionality works without JavaScript, but enhanced with JS
5. **Security First**: Authentication required for all sensitive operations, API keys secured