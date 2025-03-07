# Translation Module

The translation module is at the core of BookTranslationPro, providing the functionality for translating documents, managing translation memory, and integrating with AI services.

## Architecture

```
┌───────────────────────────────────────────────────┐
│                Translation Module                 │
├─────────────┬───────────────┬────────────────────┤
│ Translation │  Translation  │  AI Review         │
│ Engine      │  Memory       │  Integration       │
├─────────────┼───────────────┼────────────────────┤
│ Glossary    │  Segment      │  Progress          │
│ Management  │  Management   │  Tracking          │
└─────────────┴───────────────┴────────────────────┘
```

## Key Components

### Translation Engine

The translation engine manages the core translation process:

```python
def translate_text(text, source_lang, target_lang, glossary_id=None):
    """
    Translates text using DeepL API with optional glossary application
    
    Args:
        text (str): Text to translate
        source_lang (str): Source language code
        target_lang (str): Target language code
        glossary_id (str, optional): ID of glossary to apply
        
    Returns:
        str: Translated text
    """
    # Implementation with retry mechanism and error handling
```

Key features:
- Integration with DeepL API
- Error handling and retry mechanism
- Glossary application
- Rate limiting management

### Translation Memory

Translation memory stores previously translated segments to improve consistency and reduce API calls:

```python
def check_translation_memory(text, source_lang, target_lang):
    """
    Checks if a translation exists in the translation memory
    
    Args:
        text (str): Text to look up
        source_lang (str): Source language code
        target_lang (str): Target language code
        
    Returns:
        str or None: Existing translation or None if not found
    """
    # Implementation with fuzzy matching capability
```

Key features:
- Exact and fuzzy matching
- Database-backed storage
- User-specific and global memory options

### AI Review Integration

The AI review system provides quality assessment and improvement suggestions:

```python
def review_translation(source_text, translated_text, source_lang, target_lang):
    """
    Reviews a translation using OpenAI API
    
    Args:
        source_text (str): Original text
        translated_text (str): Translated text
        source_lang (str): Source language code
        target_lang (str): Target language code
        
    Returns:
        dict: Review results including suggestions and quality score
    """
    # Implementation using OpenAI assistants
```

Key features:
- Integration with OpenAI Assistants API
- Contextual review based on document type
- Suggestion categorization (style, accuracy, grammar)

### Glossary Management

The glossary system maintains consistent terminology across translations:

```python
def apply_glossary(text, glossary_entries):
    """
    Applies glossary entries to text
    
    Args:
        text (str): Text to process
        glossary_entries (list): List of term pairs
        
    Returns:
        str: Text with glossary terms applied
    """
    # Implementation with term recognition
```

Key features:
- Term pair management
- DeepL glossary integration
- Local glossary application for non-DeepL languages

## Data Flow

1. **Initial Translation Process**:
   - Document text → Check translation memory → If not found, send to DeepL API → Apply glossary → Store in database

2. **Translation Update Process**:
   - User edits translation → Update in database → Update translation memory

3. **AI Review Process**:
   - User requests review → Send source and translation to OpenAI → Process suggestions → Present to user

## Integration Points

- **DeepL API**: Primary machine translation provider
- **OpenAI API**: For AI-assisted review and suggestions
- **Database**: Storage for translations and translation memory
- **UI Layer**: Translation workspace interface

## Error Handling

The translation module implements robust error handling:

- API timeouts and rate limit handling
- Graceful degradation when services are unavailable
- Logging of translation errors for analysis
- User feedback for failed operations

## Performance Considerations

To maintain good performance:

- Translation memory reduces API calls
- Batch translation for efficiency
- Caching of frequently accessed translations
- Asynchronous processing for large documents