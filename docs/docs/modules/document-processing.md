# Document Processing Module

The document processing module in BookTranslationPro is responsible for extracting, segmenting, and managing text from various document formats.

## Architecture

```
┌───────────────────────────────────────────────────┐
│             Document Processing Module             │
├─────────────┬───────────────┬────────────────────┤
│ Format      │  Text         │  Document          │
│ Conversion  │  Extraction   │  Segmentation      │
├─────────────┼───────────────┼────────────────────┤
│ Version     │  Storage      │  Export            │
│ Management  │  Management   │  Generation        │
└─────────────┴───────────────┴────────────────────┘
```

## Supported Formats

The module supports multiple document formats:

| Format | Extensions | Processing Method |
|--------|------------|-------------------|
| PDF    | .pdf       | PyPDF2, pdfplumber |
| Word   | .docx, .doc | python-docx, textract |
| Text   | .txt       | Direct text reading |
| Rich Text | .rtf    | striprtf |
| OpenDocument | .odt | odfpy |

## Implementation

### Format Detection

```python
def detect_file_format(filename):
    """
    Detects the format of a file based on its extension
    
    Args:
        filename (str): Name of the file
        
    Returns:
        str: Format type or None if unsupported
    """
    extension = os.path.splitext(filename)[1].lower()
    
    format_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.doc': 'doc',
        '.txt': 'text',
        '.rtf': 'rtf',
        '.odt': 'odt'
    }
    
    return format_map.get(extension)
```

### Text Extraction

The module implements a multi-strategy approach to text extraction:

```python
def extract_text_from_file(file_path, file_type=None):
    """
    Extracts text from various file formats
    
    Args:
        file_path (str): Path to the file
        file_type (str, optional): Format type (auto-detected if None)
        
    Returns:
        str: Extracted text content
    """
    if file_type is None:
        file_type = detect_file_format(file_path)
        
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type in ('docx', 'doc'):
        return extract_text_from_word(file_path, file_type)
    elif file_type == 'text':
        return extract_text_from_txt(file_path)
    elif file_type == 'rtf':
        return extract_text_from_rtf(file_path)
    elif file_type == 'odt':
        return extract_text_from_odt(file_path)
    else:
        raise UnsupportedFormatError(f"Unsupported file format: {file_type}")
```

#### PDF Extraction

```python
def extract_text_from_pdf(file_path):
    """
    Extracts text from PDF using multiple strategies
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text
    """
    text = ""
    
    # Try with PyPDF2 first
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n\n"
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {e}")
    
    # If PyPDF2 returned empty or failed, try pdfplumber
    if not text.strip():
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n\n"
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
    
    # If all methods failed, raise exception
    if not text.strip():
        raise ExtractionError("Failed to extract text from PDF")
        
    return text
```

### Document Segmentation

Once text is extracted, it needs to be segmented into manageable chunks:

```python
def segment_text(text, max_length=1000, preserve_paragraphs=True):
    """
    Segments text into pages of manageable size
    
    Args:
        text (str): Text to segment
        max_length (int): Maximum length per segment
        preserve_paragraphs (bool): Try to keep paragraphs intact
        
    Returns:
        list: List of text segments
    """
    if not text:
        return []
        
    # Split text into paragraphs
    paragraphs = text.split('\n\n')
    
    segments = []
    current_segment = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed max_length
        if len(current_segment) + len(paragraph) > max_length and current_segment:
            # Add current segment to results and start a new one
            segments.append(current_segment.strip())
            current_segment = paragraph
        else:
            # Add paragraph to current segment
            if current_segment:
                current_segment += "\n\n" + paragraph
            else:
                current_segment = paragraph
    
    # Add the last segment if not empty
    if current_segment:
        segments.append(current_segment.strip())
    
    return segments
```

### Document Storage

Processed documents and segments are stored in the database:

```python
def store_document(user_id, title, file_path, language, target_lang, folder=None):
    """
    Processes and stores a document
    
    Args:
        user_id (str): ID of the user uploading the document
        title (str): Document title
        file_path (str): Path to the uploaded file
        language (str): Source language code
        target_lang (str): Target language code
        folder (str, optional): Folder/series for organization
        
    Returns:
        str: Document ID
    """
    try:
        # Detect file format
        file_format = detect_file_format(file_path)
        
        # Extract text
        text = extract_text_from_file(file_path, file_format)
        
        # Segment text
        segments = segment_text(text)
        
        # Create document record
        document_data = {
            "user_id": user_id,
            "title": title,
            "language": language,
            "target_lang": target_lang,
            "folder": folder,
            "status": "processing",
            "created_at": datetime.now().isoformat()
        }
        
        # Insert document in database
        document = supabase.table("documents").insert(document_data).execute()
        document_id = document.data[0]['id']
        
        # Store segments as pages
        for i, segment in enumerate(segments):
            page_data = {
                "document_id": document_id,
                "page_number": i + 1,
                "source_text": segment,
                "translated_text": "",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            supabase.table("document_pages").insert(page_data).execute()
        
        # Update document status
        supabase.table("documents").update(
            {"status": "ready"}
        ).eq("id", document_id).execute()
        
        return document_id
        
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise
```

## Version Control System

The module implements document versioning for tracking changes:

```python
def create_document_version(document_id):
    """
    Creates a new version of a document
    
    Args:
        document_id (str): ID of the document
        
    Returns:
        int: Version number
    """
    try:
        # Get latest version number
        versions = supabase.table("doc_versions").select("version") \
            .eq("document_id", document_id) \
            .order("version", desc=True) \
            .limit(1) \
            .execute()
            
        version_number = 1
        if versions.data:
            version_number = versions.data[0]['version'] + 1
            
        # Create new version record
        version_data = {
            "document_id": document_id,
            "version": version_number,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("doc_versions").insert(version_data).execute()
        
        # Create page versions
        pages = supabase.table("document_pages") \
            .select("id,source_text,translated_text") \
            .eq("document_id", document_id) \
            .execute()
            
        for page in pages.data:
            page_version = {
                "page_id": page['id'],
                "version": version_number,
                "source_text": page['source_text'],
                "translated_text": page['translated_text'],
                "created_at": datetime.now().isoformat()
            }
            supabase.table("page_versions").insert(page_version).execute()
            
        return version_number
        
    except Exception as e:
        logger.error(f"Error creating document version: {e}")
        raise
```

## Export System

The module handles exporting translations in various formats:

```python
def export_document(document_id, format="docx"):
    """
    Exports a translated document
    
    Args:
        document_id (str): ID of the document
        format (str): Export format ('docx', 'pdf', 'txt', 'html')
        
    Returns:
        str: Path to the exported file
    """
    # Get document info
    document = supabase.table("documents") \
        .select("title,language,target_lang") \
        .eq("id", document_id) \
        .single() \
        .execute()
        
    doc_info = document.data
    
    # Get translated pages in order
    pages = supabase.table("document_pages") \
        .select("translated_text") \
        .eq("document_id", document_id) \
        .order("page_number") \
        .execute()
        
    translated_text = "\n\n".join([p['translated_text'] for p in pages.data])
    
    # Create export file based on format
    if format == "docx":
        return export_to_docx(doc_info['title'], translated_text)
    elif format == "pdf":
        return export_to_pdf(doc_info['title'], translated_text)
    elif format == "txt":
        return export_to_txt(doc_info['title'], translated_text)
    elif format == "html":
        return export_to_html(doc_info['title'], translated_text)
    else:
        raise ValueError(f"Unsupported export format: {format}")
```

### Export Formatters

```python
def export_to_docx(title, text):
    """
    Exports text to DOCX format
    
    Args:
        title (str): Document title
        text (str): Translated text
        
    Returns:
        str: Path to the exported file
    """
    document = Document()
    document.add_heading(title, 0)
    
    # Split by paragraphs and add to document
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            document.add_paragraph(para.strip())
    
    # Save the document
    filename = f"{slugify(title)}.docx"
    output_path = os.path.join(TEMP_DIR, filename)
    document.save(output_path)
    
    return output_path
```

## Error Handling

The module implements comprehensive error handling for document processing:

```python
class DocumentProcessingError(Exception):
    """Base class for document processing errors"""
    pass

class UnsupportedFormatError(DocumentProcessingError):
    """Raised when file format is not supported"""
    pass
    
class ExtractionError(DocumentProcessingError):
    """Raised when text extraction fails"""
    pass
    
class SegmentationError(DocumentProcessingError):
    """Raised when text segmentation fails"""
    pass

def safe_process_document(user_id, title, file_path, language, target_lang, folder=None):
    """
    Safely processes a document with error handling
    
    Args:
        user_id (str): ID of the user uploading the document
        title (str): Document title
        file_path (str): Path to the uploaded file
        language (str): Source language code
        target_lang (str): Target language code
        folder (str, optional): Folder/series for organization
        
    Returns:
        dict: Result containing success status and document ID or error
    """
    try:
        document_id = store_document(user_id, title, file_path, language, target_lang, folder)
        return {"success": True, "document_id": document_id}
    except UnsupportedFormatError as e:
        logger.error(f"Unsupported file format: {e}")
        return {"success": False, "error": "This file format is not supported."}
    except ExtractionError as e:
        logger.error(f"Text extraction failed: {e}")
        return {"success": False, "error": "Could not extract text from this file."}
    except Exception as e:
        logger.error(f"Document processing error: {e}", exc_info=True)
        return {"success": False, "error": "An error occurred while processing the document."}
```

## Integration Points

The document processing module integrates with these components:

- **Upload Interface**: Handles file uploads from users
- **Database Layer**: Stores documents, pages, and versions
- **Translation Module**: Receives segmented text for translation
- **Export Interface**: Generates files in requested formats

## Performance Optimizations

For large documents, the module implements several optimizations:

1. **Chunked Processing**: Documents are processed in chunks to avoid memory issues
2. **Background Processing**: Long-running tasks are processed in background workers
3. **Progress Tracking**: Real-time progress updates for long-running operations
4. **Caching**: Commonly accessed documents are cached for faster access