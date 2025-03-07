# DeepL Integration

BookTranslationPro uses DeepL's API for high-quality machine translation of documents.

## Overview

The DeepL integration provides:

1. Initial machine translation of uploaded documents
2. Support for multiple language pairs
3. Glossary-enhanced translations for terminology consistency
4. Formality control for appropriate style

## API Configuration

### Required Environment Variables

```
DEEPL_API_KEY=your_deepl_api_key
```

### Supported Languages

The application supports all language pairs available through DeepL, which currently includes:

| Language Code | Language Name |
|--------------|---------------|
| EN | English |
| DE | German |
| FR | French |
| ES | Spanish |
| IT | Italian |
| NL | Dutch |
| PL | Polish |
| PT | Portuguese |
| RU | Russian |
| JA | Japanese |
| ZH | Chinese |
| ... | (and more) |

## Integration Implementation

### Translation Function

The core translation function manages DeepL API interactions:

```python
def translate_text_with_deepl(text, source_lang, target_lang, glossary_id=None, formality="default"):
    """
    Translates text using the DeepL API
    
    Args:
        text (str): Text to translate
        source_lang (str): Source language code
        target_lang (str): Target language code
        glossary_id (str, optional): DeepL glossary ID to use
        formality (str, optional): Formality level (default, more, less, prefer_more, prefer_less)
        
    Returns:
        str: Translated text
    """
    try:
        # Initialize DeepL API client
        translator = deepl.Translator(os.environ["DEEPL_API_KEY"])
        
        # Prepare translation parameters
        params = {
            "text": text,
            "source_lang": source_lang.upper(),
            "target_lang": target_lang.upper(),
            "formality": formality
        }
        
        # Add glossary if specified
        if glossary_id:
            params["glossary_id"] = glossary_id
            
        # Execute translation with retry mechanism
        result = execute_with_retry(
            lambda: translator.translate_text(**params),
            max_retries=3
        )
        
        return result.text if result else ""
        
    except deepl.exceptions.DeepLException as e:
        logger.error(f"DeepL translation error: {e}")
        # Handle specific error types
        if "quota" in str(e).lower():
            raise QuotaExceededException("DeepL API quota exceeded")
        raise TranslationException(f"DeepL translation failed: {e}")
```

### Batch Document Translation

For efficient document translation, we use batch processing:

```python
def translate_document_pages(document_id, batch_size=10):
    """
    Translates all pages of a document in batches
    
    Args:
        document_id (str): ID of document to translate
        batch_size (int): Number of pages to translate in each batch
        
    Returns:
        bool: True if translation completed successfully
    """
    # Get document details
    document = get_document_by_id(document_id)
    source_lang = document["language"]
    target_lang = document["target_lang"]
    
    # Get document pages
    pages = get_document_pages(document_id)
    
    # Process pages in batches
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i+batch_size]
        
        # Translate each page in the batch
        for page in batch:
            # Check if page already has a translation
            if page["translated_text"]:
                continue
                
            # Check translation memory first
            tm_result = check_translation_memory(page["source_text"], source_lang, target_lang)
            if tm_result:
                # Use translation memory result
                update_page_translation(page["id"], tm_result)
                continue
                
            # Translate with DeepL
            glossary_id = get_document_glossary_id(document_id)
            translated_text = translate_text_with_deepl(
                page["source_text"], 
                source_lang, 
                target_lang, 
                glossary_id=glossary_id
            )
            
            # Update page with translation
            update_page_translation(page["id"], translated_text)
            
            # Update translation memory
            add_to_translation_memory(
                page["source_text"], 
                translated_text, 
                source_lang, 
                target_lang,
                document["user_id"]
            )
            
    # Update document status
    update_document_status(document_id, "machine_translated")
    return True
```

## Glossary Management

The application integrates with DeepL's glossary feature:

```python
def create_deepl_glossary(name, source_lang, target_lang, entries):
    """
    Creates a glossary in DeepL
    
    Args:
        name (str): Glossary name
        source_lang (str): Source language code
        target_lang (str): Target language code
        entries (dict): Dictionary of source:target term pairs
        
    Returns:
        str: DeepL glossary ID
    """
    translator = deepl.Translator(os.environ["DEEPL_API_KEY"])
    
    # Format entries for DeepL
    entry_list = []
    for source, target in entries.items():
        entry_list.append(f"{source}\t{target}")
    
    # Create the glossary
    glossary = translator.create_glossary(
        name=name,
        source_lang=source_lang.upper(),
        target_lang=target_lang.upper(),
        entries="\n".join(entry_list)
    )
    
    return glossary.glossary_id
```

## Error Handling

The DeepL integration implements comprehensive error handling:

```python
def execute_with_retry(func, max_retries=3, initial_delay=1):
    """
    Execute a function with retry logic for API calls
    
    Args:
        func: Function to execute
        max_retries: Maximum retry attempts
        initial_delay: Initial delay between retries (seconds)
        
    Returns:
        Result from the function or None if all retries fail
    """
    retries = 0
    last_exception = None
    
    while retries <= max_retries:
        try:
            return func()
        except (deepl.exceptions.ConnectionException, 
                deepl.exceptions.TooManyRequestsException) as e:
            last_exception = e
            retries += 1
            
            if retries > max_retries:
                break
                
            # Exponential backoff with jitter
            delay = initial_delay * (2 ** (retries - 1)) * (0.5 + random.random())
            time.sleep(delay)
            
    logger.error(f"Failed after {max_retries} retries: {last_exception}")
    return None
```

## API Limits and Performance

The application manages DeepL API usage efficiently:

1. **Usage Tracking**: Monitors DeepL API usage to prevent quota overruns
2. **Translation Memory**: Reduces redundant translations by storing previous results
3. **Batch Processing**: Translates documents in parallel batches for efficiency
4. **Caching**: Implements response caching for frequently translated segments

```python
def get_deepl_usage():
    """
    Checks DeepL API usage statistics
    
    Returns:
        dict: Usage statistics including character count and limits
    """
    translator = deepl.Translator(os.environ["DEEPL_API_KEY"])
    usage = translator.get_usage()
    
    return {
        "character_count": usage.character_count,
        "character_limit": usage.character_limit,
        "percent_used": (usage.character_count / usage.character_limit) * 100 if usage.character_limit else 0
    }
```

## Related Components

- **Translation Module**: Core integration point for DeepL services
- **Glossary Management**: Creates and manages DeepL glossaries
- **Translation Memory**: Complements DeepL with stored translations