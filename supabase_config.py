import os
import uuid
import hashlib
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")

# Log Supabase configuration (without showing full key)
if SUPABASE_URL:
    logger.info(f"Supabase URL configured: {SUPABASE_URL}")
else:
    logger.warning("Supabase URL not configured!")

if SUPABASE_KEY:
    # Log only first few characters of the key to avoid security issues
    visible_part = SUPABASE_KEY[:4] + "..." if len(SUPABASE_KEY) > 4 else ""
    logger.info(f"Supabase API Key configured: {visible_part}")
else:
    logger.warning("Supabase API Key not configured!")

# Create Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    # Create a dummy client that will log errors but not crash
    class DummySupabase:
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                logger.error(f"Attempted to call Supabase.{name} but Supabase is not configured properly")
                return self
            return dummy_method
            
        def execute(self):
            logger.error("Attempted to execute Supabase query but Supabase is not configured properly")
            return type('obj', (object,), {'data': []})
            
    supabase = DummySupabase()

def get_user_data(user_id):
    """Fetch user data from Supabase"""
    try:
        logger.debug(f"Fetching user data for user_id: {user_id}")
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        if hasattr(response, 'data') and response.data and len(response.data) > 0:
            logger.debug(f"User data found for user_id: {user_id}")
            return response.data[0]
        logger.warning(f"No user data found for user_id: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        return None

def save_user_data(user_id, data):
    """Save or update user data in Supabase"""
    try:
        logger.debug(f"Saving user data for user_id: {user_id}")
        existing_user = get_user_data(user_id)
        if existing_user:
            # Update existing user
            logger.debug(f"Updating existing user: {user_id}")
            response = supabase.table('users').update(data).eq('id', user_id).execute()
        else:
            # Create new user entry
            logger.debug(f"Creating new user: {user_id}")
            data['id'] = user_id
            response = supabase.table('users').insert(data).execute()
        
        if hasattr(response, 'data'):
            logger.debug(f"User data saved successfully for: {user_id}")
            return response.data
        logger.warning(f"No data returned after saving user: {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return None

def get_user_translations(user_id, limit=20, offset=0):
    """Fetch user's translation history"""
    try:
        logger.debug(f"Fetching translations for user_id: {user_id}, limit: {limit}, offset: {offset}")
        response = supabase.table('translations').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(offset).execute()
        if hasattr(response, 'data'):
            logger.debug(f"Found {len(response.data)} translations for user_id: {user_id}")
            return response.data
        logger.warning(f"No data returned when fetching translations for user_id: {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error fetching translations: {e}")
        return []
        
def generate_text_hash(text, target_language=''):
    """Generate a hash for text caching based on content and target language"""
    if not text:
        return None
        
    # Create normalized text sample for hashing (first 1000 chars)
    text_sample = text[:1000].strip().lower()
    
    # Create hash of text + target language
    hash_content = f"{text_sample}_{target_language}"
    hash_obj = hashlib.md5(hash_content.encode('utf-8'))
    return hash_obj.hexdigest()
    
def check_translation_cache(text, target_language):
    """Check if a translation exists in the cache"""
    try:
        if not text or not text.strip():
            return None
            
        # Generate hash for lookup
        text_hash = generate_text_hash(text, target_language)
        if not text_hash:
            return None
            
        # Look up in cache by hash
        logger.debug(f"Checking translation cache for hash: {text_hash[:10]}...")
        response = supabase.table('translation_cache').select('*').eq('source_hash', text_hash).eq('target_language', target_language).limit(1).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Cache hit for text with hash: {text_hash[:10]}...")
            return response.data[0]['translated_text']
            
        logger.debug(f"Cache miss for text with hash: {text_hash[:10]}...")
        return None
    except Exception as e:
        logger.error(f"Error checking translation cache: {str(e)}")
        return None

def save_translation(user_id, original_filename, translated_text, settings=None, source_text=None, source_hash=None, target_language=None):
    """Save a translation to the user's history and translation cache"""
    try:
        data = {
            'user_id': user_id,
            'original_filename': original_filename,
            'translation_summary': translated_text[:200] + '...' if len(translated_text) > 200 else translated_text,
            'settings': settings or {},
            'created_at': 'now()'
        }
        response = supabase.table('translations').insert(data).execute()
        
        # Save the full translation text to storage
        translation_id = response.data[0]['id']
        content = translated_text.encode('utf-8')
        storage_path = f"{user_id}/{translation_id}.txt"
        
        storage_response = supabase.storage.from_('translations').upload(
            storage_path,
            content
        )
        
        # If source text and hash are provided, save to translation cache
        if source_text and source_hash and target_language:
            try:
                # Check if entry already exists in cache by hash
                cache_data = {
                    'source_hash': source_hash,
                    'source_text': source_text,
                    'target_language': target_language,
                    'translated_text': translated_text,
                    'user_id': user_id,  # Track which user added this to cache
                    'created_at': 'now()',
                    'updated_at': 'now()'
                }
                
                # Add to translation cache
                cache_response = supabase.table('translation_cache').insert(cache_data).execute()
                logger.info(f"Added translation to cache with hash: {source_hash[:10]}...")
            except Exception as cache_error:
                # Don't fail the main operation if caching fails
                logger.error(f"Error saving to translation cache: {str(cache_error)}")
        
        return response.data[0]
    except Exception as e:
        logger.error(f"Error saving translation: {str(e)}")
        return None

def get_full_translation(user_id, translation_id):
    """Get the full text of a translation from storage"""
    try:
        storage_path = f"{user_id}/{translation_id}.txt"
        response = supabase.storage.from_('translations').download(storage_path)
        return response.decode('utf-8')
    except Exception as e:
        print(f"Error fetching full translation: {e}")
        return None

def delete_translation(user_id, translation_id):
    """Delete a translation from history and storage"""
    try:
        # Delete from database
        supabase.table('translations').delete().eq('id', translation_id).eq('user_id', user_id).execute()
        
        # Delete from storage
        storage_path = f"{user_id}/{translation_id}.txt"
        supabase.storage.from_('translations').remove([storage_path])
        
        return True
    except Exception as e:
        print(f"Error deleting translation: {e}")
        return False

def get_user_settings(user_id):
    """Get user's saved settings"""
    user = get_user_data(user_id)
    if user and 'settings' in user:
        return user['settings']
    return {}

def save_user_settings(user_id, settings):
    """Save user settings"""
    return save_user_data(user_id, {'settings': settings})
    
def get_user_assistants(user_id):
    """Get list of user's OpenAI assistants"""
    try:
        # First try to get from 'assistants' column
        user_data = get_user_data(user_id)
        if user_data and 'assistants' in user_data:
            return user_data['assistants']
            
        # Alternatively, check if stored in settings (more compatible approach)
        settings = get_user_settings(user_id)
        if settings and 'assistants' in settings:
            return settings['assistants']
            
        return []
    except Exception as e:
        logger.error(f"Error fetching user assistants: {e}")
        return []

def get_assistant(user_id, assistant_id):
    """Get a specific assistant by ID"""
    try:
        # First check if assistants are in the session (most reliable)
        from flask import session
        if 'user_assistants' in session:
            assistants = session['user_assistants']
            for assistant in assistants:
                if assistant.get('id') == assistant_id:
                    return assistant
        
        # If not found in session, try to get from database
        assistants = get_user_assistants(user_id)
        for assistant in assistants:
            if assistant.get('id') == assistant_id:
                return assistant
                
        return None
    except Exception as e:
        logger.error(f"Error fetching assistant: {e}")
        return None

def save_assistant(user_id, assistant_data):
    """Save or update an assistant configuration"""
    try:
        # Generate ID if not provided
        if not assistant_data.get('id'):
            assistant_data['id'] = str(uuid.uuid4())
            
        # Set timestamps
        current_time = datetime.now().isoformat()
        if not assistant_data.get('created_at'):
            assistant_data['created_at'] = current_time
        assistant_data['updated_at'] = current_time
        
        # Get current assistants from settings
        user_settings = get_user_settings(user_id) or {}
        assistants = user_settings.get('assistants', [])
        
        # Update existing or add new
        assistant_id = assistant_data.get('id')
        for i, assistant in enumerate(assistants):
            if assistant.get('id') == assistant_id:
                assistants[i] = assistant_data
                break
        else:
            assistants.append(assistant_data)
        
        # Save updated assistants list in settings
        user_settings['assistants'] = assistants
        save_user_settings(user_id, user_settings)
        
        return assistant_data
    except Exception as e:
        logger.error(f"Error saving assistant: {e}")
        return None

def delete_assistant(user_id, assistant_id):
    """Delete an assistant"""
    try:
        user_settings = get_user_settings(user_id) or {}
        assistants = user_settings.get('assistants', [])
        
        # Filter out the assistant to delete
        user_settings['assistants'] = [a for a in assistants if a.get('id') != assistant_id]
        save_user_settings(user_id, user_settings)
        
        return True
    except Exception as e:
        logger.error(f"Error deleting assistant: {e}")
        return False

# Glossary Management Functions

def get_user_glossaries(user_id, limit=20, offset=0):
    """Fetch user's glossaries"""
    try:
        logger.debug(f"Fetching glossaries for user_id: {user_id}")
        response = supabase.table('glossaries').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(offset).execute()
        if hasattr(response, 'data'):
            logger.debug(f"Found {len(response.data)} glossaries for user_id: {user_id}")
            return response.data
        logger.warning(f"No data returned when fetching glossaries for user_id: {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error fetching glossaries: {e}")
        return []

def get_glossary(user_id, glossary_id):
    """Fetch a specific glossary"""
    try:
        logger.debug(f"Fetching glossary {glossary_id} for user_id: {user_id}")
        response = supabase.table('glossaries').select('*').eq('id', glossary_id).eq('user_id', user_id).limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        logger.warning(f"No glossary found with id: {glossary_id} for user_id: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching glossary: {e}")
        return None

def create_glossary(user_id, glossary_data):
    """Create a new glossary"""
    try:
        # Ensure required fields
        if not glossary_data.get('name'):
            logger.error("Glossary name is required")
            return None
            
        data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': glossary_data.get('name'),
            'description': glossary_data.get('description', ''),
            'source_language': glossary_data.get('source_language', ''),
            'target_language': glossary_data.get('target_language', ''),
            'created_at': 'now()',
            'updated_at': 'now()'
        }
        
        logger.debug(f"Creating new glossary for user_id: {user_id}")
        response = supabase.table('glossaries').insert(data).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Glossary created successfully: {response.data[0]['id']}")
            return response.data[0]
        logger.warning("Failed to create glossary")
        return None
    except Exception as e:
        logger.error(f"Error creating glossary: {e}")
        return None

def update_glossary(user_id, glossary_id, glossary_data):
    """Update an existing glossary"""
    try:
        # Check if glossary exists
        if not get_glossary(user_id, glossary_id):
            logger.warning(f"Glossary not found: {glossary_id}")
            return None
            
        update_data = {
            'name': glossary_data.get('name'),
            'description': glossary_data.get('description'),
            'source_language': glossary_data.get('source_language'),
            'target_language': glossary_data.get('target_language'),
            'updated_at': 'now()'
        }
        
        # Remove any None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        logger.debug(f"Updating glossary {glossary_id} for user_id: {user_id}")
        response = supabase.table('glossaries').update(update_data).eq('id', glossary_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Glossary updated successfully: {glossary_id}")
            return response.data[0]
        logger.warning(f"Failed to update glossary: {glossary_id}")
        return None
    except Exception as e:
        logger.error(f"Error updating glossary: {e}")
        return None

def delete_glossary(user_id, glossary_id):
    """Delete a glossary and all its entries"""
    try:
        # First delete all entries
        logger.debug(f"Deleting entries for glossary {glossary_id}")
        supabase.table('glossary_entries').delete().eq('glossary_id', glossary_id).execute()
        
        # Then delete the glossary
        logger.debug(f"Deleting glossary {glossary_id} for user_id: {user_id}")
        response = supabase.table('glossaries').delete().eq('id', glossary_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data'):
            logger.info(f"Glossary deleted successfully: {glossary_id}")
            return True
        logger.warning(f"Failed to delete glossary: {glossary_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting glossary: {e}")
        return False

def get_glossary_entries(glossary_id, limit=100, offset=0):
    """Fetch entries for a specific glossary"""
    try:
        logger.debug(f"Fetching entries for glossary_id: {glossary_id}")
        response = supabase.table('glossary_entries').select('*').eq('glossary_id', glossary_id).order('source_term').limit(limit).offset(offset).execute()
        
        if hasattr(response, 'data'):
            logger.debug(f"Found {len(response.data)} entries for glossary_id: {glossary_id}")
            return response.data
        logger.warning(f"No data returned when fetching entries for glossary_id: {glossary_id}")
        return []
    except Exception as e:
        logger.error(f"Error fetching glossary entries: {e}")
        return []

def create_glossary_entry(glossary_id, entry_data):
    """Create a new glossary entry"""
    try:
        # Ensure required fields
        if not entry_data.get('source_term') or not entry_data.get('target_term'):
            logger.error("Source term and target term are required")
            return None
            
        data = {
            'id': str(uuid.uuid4()),
            'glossary_id': glossary_id,
            'source_term': entry_data.get('source_term'),
            'target_term': entry_data.get('target_term'),
            'context': entry_data.get('context', ''),
            'notes': entry_data.get('notes', ''),
            'created_at': 'now()',
            'updated_at': 'now()'
        }
        
        logger.debug(f"Creating new entry for glossary_id: {glossary_id}")
        response = supabase.table('glossary_entries').insert(data).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Glossary entry created successfully: {response.data[0]['id']}")
            return response.data[0]
        logger.warning("Failed to create glossary entry")
        return None
    except Exception as e:
        logger.error(f"Error creating glossary entry: {e}")
        return None

def update_glossary_entry(entry_id, entry_data):
    """Update an existing glossary entry"""
    try:
        update_data = {
            'source_term': entry_data.get('source_term'),
            'target_term': entry_data.get('target_term'),
            'context': entry_data.get('context'),
            'notes': entry_data.get('notes'),
            'updated_at': 'now()'
        }
        
        # Remove any None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        logger.debug(f"Updating glossary entry: {entry_id}")
        response = supabase.table('glossary_entries').update(update_data).eq('id', entry_id).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Glossary entry updated successfully: {entry_id}")
            return response.data[0]
        logger.warning(f"Failed to update glossary entry: {entry_id}")
        return None
    except Exception as e:
        logger.error(f"Error updating glossary entry: {e}")
        return None

def delete_glossary_entry(entry_id):
    """Delete a glossary entry"""
    try:
        logger.debug(f"Deleting glossary entry: {entry_id}")
        response = supabase.table('glossary_entries').delete().eq('id', entry_id).execute()
        
        if hasattr(response, 'data'):
            logger.info(f"Glossary entry deleted successfully: {entry_id}")
            return True
        logger.warning(f"Failed to delete glossary entry: {entry_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting glossary entry: {e}")
        return False

def apply_glossary_to_text(text, glossary_id):
    """Apply glossary terms to a text string"""
    if not text or not glossary_id:
        return text
        
    try:
        # Get all glossary entries
        entries = get_glossary_entries(glossary_id)
        if not entries:
            return text
            
        # Sort entries by length of source term (longest first)
        # This prevents shorter terms from replacing parts of longer terms
        entries.sort(key=lambda x: len(x.get('source_term', '')), reverse=True)
        
        # Apply replacements
        for entry in entries:
            source_term = entry.get('source_term', '')
            target_term = entry.get('target_term', '')
            
            if source_term and target_term:
                # Replace with word boundary check to avoid partial word replacements
                # This is a simple implementation - more sophisticated NLP might be needed
                text = text.replace(f" {source_term} ", f" {target_term} ")
                
                # Handle beginning of text
                if text.startswith(source_term + " "):
                    text = target_term + " " + text[len(source_term)+1:]
                    
                # Handle end of text
                if text.endswith(" " + source_term):
                    text = text[:-len(source_term)-1] + " " + target_term
                    
                # Handle standalone term (the entire text)
                if text == source_term:
                    text = target_term
                    
        return text
    except Exception as e:
        logger.error(f"Error applying glossary to text: {e}")
        return text
        
# Document Management Functions

def get_user_folders(user_id, limit=50, offset=0):
    """Fetch user's document folders"""
    try:
        logger.debug(f"Fetching folders for user_id: {user_id}")
        response = supabase.table('document_folders').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(offset).execute()
        if hasattr(response, 'data'):
            logger.debug(f"Found {len(response.data)} folders for user_id: {user_id}")
            return response.data
        logger.warning(f"No data returned when fetching folders for user_id: {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error fetching folders: {e}")
        return []

def get_folder(user_id, folder_id):
    """Fetch a specific folder"""
    try:
        logger.debug(f"Fetching folder {folder_id} for user_id: {user_id}")
        response = supabase.table('document_folders').select('*').eq('id', folder_id).eq('user_id', user_id).limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        logger.warning(f"No folder found with id: {folder_id} for user_id: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching folder: {e}")
        return None

def create_folder(user_id, folder_data):
    """Create a new folder"""
    try:
        # Ensure required fields
        if not folder_data.get('name'):
            logger.error("Folder name is required")
            return None
            
        data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': folder_data.get('name'),
            'description': folder_data.get('description', ''),
            'color': folder_data.get('color', '#3498db'),  # Default blue color
            'created_at': 'now()',
            'updated_at': 'now()'
        }
        
        logger.debug(f"Creating new folder for user_id: {user_id}")
        response = supabase.table('document_folders').insert(data).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Folder created successfully: {response.data[0]['id']}")
            return response.data[0]
        logger.warning("Failed to create folder")
        return None
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        return None

def update_folder(user_id, folder_id, folder_data):
    """Update an existing folder"""
    try:
        # Check if folder exists
        if not get_folder(user_id, folder_id):
            logger.warning(f"Folder not found: {folder_id}")
            return None
            
        update_data = {
            'name': folder_data.get('name'),
            'description': folder_data.get('description'),
            'color': folder_data.get('color'),
            'updated_at': 'now()'
        }
        
        # Remove any None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        logger.debug(f"Updating folder {folder_id} for user_id: {user_id}")
        response = supabase.table('document_folders').update(update_data).eq('id', folder_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Folder updated successfully: {folder_id}")
            return response.data[0]
        logger.warning(f"Failed to update folder: {folder_id}")
        return None
    except Exception as e:
        logger.error(f"Error updating folder: {e}")
        return None

def delete_folder(user_id, folder_id):
    """Delete a folder"""
    try:
        # First update documents to remove folder association
        logger.debug(f"Updating documents for deleted folder {folder_id}")
        supabase.table('documents').update({
            'folder_id': None,
            'updated_at': 'now()'
        }).eq('folder_id', folder_id).eq('user_id', user_id).execute()
        
        # Then delete the folder
        logger.debug(f"Deleting folder {folder_id} for user_id: {user_id}")
        response = supabase.table('document_folders').delete().eq('id', folder_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data'):
            logger.info(f"Folder deleted successfully: {folder_id}")
            return True
        logger.warning(f"Failed to delete folder: {folder_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        return False

def get_user_documents(user_id, folder_id=None, limit=50, offset=0):
    """Fetch user's documents, optionally filtered by folder"""
    try:
        logger.debug(f"Fetching documents for user_id: {user_id}")
        query = supabase.table('documents').select('*').eq('user_id', user_id)
        
        # Filter by folder if specified
        if folder_id:
            query = query.eq('folder_id', folder_id)
            
        response = query.order('created_at', desc=True).limit(limit).offset(offset).execute()
        
        if hasattr(response, 'data'):
            logger.debug(f"Found {len(response.data)} documents for user_id: {user_id}")
            return response.data
        logger.warning(f"No data returned when fetching documents for user_id: {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return []

def get_document(user_id, document_id):
    """Fetch a specific document"""
    try:
        logger.debug(f"Fetching document {document_id} for user_id: {user_id}")
        response = supabase.table('documents').select('*').eq('id', document_id).eq('user_id', user_id).limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        logger.warning(f"No document found with id: {document_id} for user_id: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        return None

def create_document(user_id, document_data):
    """Create a new document"""
    try:
        # Ensure required fields
        if not document_data.get('title'):
            logger.error("Document title is required")
            return None
            
        data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'title': document_data.get('title'),
            'description': document_data.get('description', ''),
            'original_filename': document_data.get('original_filename', ''),
            'file_type': document_data.get('file_type', ''),
            'folder_id': document_data.get('folder_id'),
            'source_language': document_data.get('source_language', ''),
            'target_language': document_data.get('target_language', ''),
            'word_count': document_data.get('word_count', 0),
            'version': 1,  # Initial version
            'tags': document_data.get('tags', []),
            'status': document_data.get('status', 'completed'),
            'settings': document_data.get('settings', {}),
            'created_at': 'now()',
            'updated_at': 'now()'
        }
        
        logger.debug(f"Creating new document for user_id: {user_id}")
        response = supabase.table('documents').insert(data).execute()
        
        if hasattr(response, 'data') and response.data:
            document_id = response.data[0]['id']
            logger.info(f"Document created successfully: {document_id}")
            
            # If content is provided, save it to storage
            source_content = document_data.get('source_content')
            translated_content = document_data.get('translated_content')
            
            if source_content:
                save_document_content(user_id, document_id, source_content, content_type='source')
                
            if translated_content:
                save_document_content(user_id, document_id, translated_content, content_type='translated')
            
            return response.data[0]
        logger.warning("Failed to create document")
        return None
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        return None

def update_document(user_id, document_id, document_data, create_new_version=False):
    """Update an existing document, optionally creating a new version"""
    try:
        # Get current document
        current_doc = get_document(user_id, document_id)
        if not current_doc:
            logger.warning(f"Document not found: {document_id}")
            return None
        
        if create_new_version:
            # Create a new version by copying the document with an incremented version number
            new_version = current_doc.get('version', 1) + 1
            
            # Create historical record for old version
            history_data = current_doc.copy()
            history_data['document_id'] = document_id
            history_data['id'] = str(uuid.uuid4())
            history_data['created_at'] = 'now()'
            
            # Save historical version
            history_response = supabase.table('document_versions').insert(history_data).execute()
            if not (hasattr(history_response, 'data') and history_response.data):
                logger.warning(f"Failed to create version history for document: {document_id}")
            
            # Update document with new version number
            document_data['version'] = new_version
        
        # Prepare update data
        update_data = {k: v for k, v in document_data.items() if k not in ['id', 'user_id', 'created_at']}
        update_data['updated_at'] = 'now()'
        
        logger.debug(f"Updating document {document_id} for user_id: {user_id}")
        response = supabase.table('documents').update(update_data).eq('id', document_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Document updated successfully: {document_id}")
            
            # If content is provided, save it to storage
            source_content = document_data.get('source_content')
            translated_content = document_data.get('translated_content')
            
            if source_content:
                save_document_content(user_id, document_id, source_content, content_type='source')
                
            if translated_content:
                save_document_content(user_id, document_id, translated_content, content_type='translated')
                
            return response.data[0]
        logger.warning(f"Failed to update document: {document_id}")
        return None
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        return None

def delete_document(user_id, document_id):
    """Delete a document and all its versions/content"""
    try:
        # First delete all version history
        logger.debug(f"Deleting version history for document {document_id}")
        supabase.table('document_versions').delete().eq('document_id', document_id).execute()
        
        # Delete document content from storage
        try:
            # Source content
            source_path = f"documents/{user_id}/{document_id}/source"
            supabase.storage.from_('documents').remove([source_path])
        except:
            logger.warning(f"Could not delete source content for document {document_id}")
            
        try:
            # Translated content
            translated_path = f"documents/{user_id}/{document_id}/translated"
            supabase.storage.from_('documents').remove([translated_path])
        except:
            logger.warning(f"Could not delete translated content for document {document_id}")
        
        # Then delete the document
        logger.debug(f"Deleting document {document_id} for user_id: {user_id}")
        response = supabase.table('documents').delete().eq('id', document_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data'):
            logger.info(f"Document deleted successfully: {document_id}")
            return True
        logger.warning(f"Failed to delete document: {document_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return False

def get_document_versions(user_id, document_id, limit=20, offset=0):
    """Get version history for a document"""
    try:
        logger.debug(f"Fetching version history for document {document_id}")
        
        # First get the current document
        current = get_document(user_id, document_id)
        if not current:
            logger.warning(f"Document not found: {document_id}")
            return []
            
        # Then get historical versions
        response = supabase.table('document_versions').select('*').eq('document_id', document_id).order('version', desc=True).limit(limit).offset(offset).execute()
        
        versions = []
        if hasattr(response, 'data'):
            versions = response.data
            
        # Add the current version at the beginning
        if current:
            # Mark as current version
            current['is_current'] = True
            versions.insert(0, current)
            
        logger.debug(f"Found {len(versions)} versions for document {document_id}")
        return versions
    except Exception as e:
        logger.error(f"Error fetching document versions: {e}")
        return []

def fix_document_content(user_id, document_id):
    """Fix missing document content by creating placeholder content files"""
    try:
        # First check if document exists
        document = get_document(user_id, document_id)
        if not document:
            logger.error(f"Document {document_id} not found for user {user_id}")
            return False
            
        # Try to get existing content
        source_content = get_document_content(user_id, document_id, 'source')
        translated_content = get_document_content(user_id, document_id, 'translated')
        
        fixed = False
        
        # Create placeholder for source if missing
        if not source_content:
            logger.info(f"Creating placeholder source content for document {document_id}")
            placeholder = f"This is placeholder source content for document '{document['title']}'. The original content was missing."
            success = save_document_content(user_id, document_id, placeholder, 'source')
            logger.info(f"Source content for document {document_id} {'created successfully' if success else 'failed to create'}")
            fixed = fixed or success
            
        # Create placeholder for translated if missing
        if not translated_content:
            logger.info(f"Creating placeholder translated content for document {document_id}")
            placeholder = f"This is placeholder translated content for document '{document['title']}'. The original content was missing."
            success = save_document_content(user_id, document_id, placeholder, 'translated')
            logger.info(f"Translated content for document {document_id} {'created successfully' if success else 'failed to create'}")
            fixed = fixed or success
            
        # If we've applied fixes, update document metadata
        if fixed:
            logger.info(f"Updating document {document_id} metadata after content fix")
            update_data = {
                'status': 'fixed',
                'updated_at': 'now()'
            }
            supabase.table('documents').update(update_data).eq('id', document_id).eq('user_id', user_id).execute()
            
        return fixed
    except Exception as e:
        logger.error(f"Error fixing document content: {e}")
        return False

def save_document_content(user_id, document_id, content, content_type='translated'):
    """Save document content to storage"""
    try:
        if not content:
            logger.warning(f"Empty content for document {document_id}, not saving")
            return False
            
        # Create path for the content
        storage_path = f"documents/{user_id}/{document_id}/{content_type}"
        
        # Convert content to bytes if it's not already
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        # First check if the document_id directory exists, create it if not
        document_dir = f"documents/{user_id}/{document_id}"
        
        try:
            # List files to see if directory exists
            dir_exists = False
            try:
                list_files = supabase.storage.from_('documents').list(f"{user_id}/{document_id}")
                # Check if list_files is valid (not None and is a list)
                if list_files and isinstance(list_files, list):
                    dir_exists = True
                    logger.debug(f"Directory exists for document {document_id}")
            except:
                dir_exists = False
                
            # If directory doesn't exist, create it
            if not dir_exists:
                logger.debug(f"Creating directory for document {document_id}")
                placeholder_path = f"{user_id}/{document_id}/.placeholder"
                placeholder_content = b"placeholder"
                
                # Upload placeholder file to create directory structure
                supabase.storage.from_('documents').upload(
                    placeholder_path,
                    placeholder_content,
                    {"contentType": "text/plain", "upsert": "true", "cacheControl": "3600"}
                )
                logger.debug(f"Created directory for document {document_id}")
        except Exception as dir_error:
            logger.error(f"Error checking/creating directory for document {document_id}: {dir_error}")
            # Continue anyway, the upload might still work
        
        # Upload to storage
        logger.debug(f"Saving {content_type} content for document {document_id} to path {storage_path}")
        storage_response = supabase.storage.from_('documents').upload(
            storage_path,
            content,
            {"contentType": "text/plain", "upsert": "true", "cacheControl": "3600"}
        )
        
        logger.info(f"Content saved successfully for document {document_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving document content: {e}")
        return False

def get_document_content(user_id, document_id, content_type='translated', version_id=None):
    """Get document content from storage"""
    try:
        # If version_id is provided, get content from version history
        if version_id:
            # Get the version
            version_response = supabase.table('document_versions').select('*').eq('id', version_id).eq('document_id', document_id).limit(1).execute()
            if hasattr(version_response, 'data') and version_response.data:
                # This would require storing content in the version table
                # For this implementation, we're assuming content is stored in storage
                pass
        
        # Get content from storage
        storage_path = f"documents/{user_id}/{document_id}/{content_type}"
        
        # First check if the document exists
        document = get_document(user_id, document_id)
        if not document:
            logger.warning(f"Document {document_id} not found. Cannot retrieve content.")
            return None
            
        # Try to download content
        try:
            logger.debug(f"Downloading content from path {storage_path}")
            response = supabase.storage.from_('documents').download(storage_path)
            if response:
                content = response.decode('utf-8')
                logger.info(f"Successfully retrieved content for document {document_id}")
                return content
        except Exception as storage_error:
            logger.warning(f"Error downloading content: {storage_error}")
            # Continue to fallback logic
            
        # If we're still here, content wasn't successfully retrieved
        # Check if the document directory exists
        try:
            list_files = supabase.storage.from_('documents').list(f"{user_id}/{document_id}")
            logger.debug(f"Files in document directory: {list_files}")
        except Exception as list_error:
            logger.warning(f"Document directory may not exist: {list_error}")
            list_files = []
            
        # Create placeholder content since the content file is missing
        logger.info(f"Creating placeholder content for document {document_id} ({content_type})")
        placeholder_content = f"This document has no {content_type} content yet. Please edit the document to add content."
        
        # Try to save the placeholder content
        success = save_document_content(user_id, document_id, placeholder_content, content_type)
        if success:
            logger.info(f"Successfully created placeholder content for document {document_id}")
        else:
            logger.warning(f"Failed to create placeholder content for document {document_id}")
            
        return placeholder_content
            
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        # Even in case of errors, return something the user can see
        return "Error retrieving document content. Please try the 'Fix Document Content' option."
        
# Translation Memory Management Functions

def get_translation_memory_entries(user_id, limit=50, offset=0, search=None, language=None):
    """Fetch translation memory entries with optional filtering"""
    try:
        query = supabase.table('translation_cache').select('*').eq('user_id', user_id)
        
        # Filter by language if specified
        if language:
            query = query.eq('target_language', language)
            
        # Filter by search term if specified (fuzzy search in source or translated text)
        if search:
            # This is simplified - would need proper text search implementation
            query = query.or_(f"source_text.ilike.%{search}%,translated_text.ilike.%{search}%")
            
        # Apply pagination
        query = query.order('updated_at', desc=True).limit(limit).offset(offset)
        
        response = query.execute()
        
        if hasattr(response, 'data'):
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error fetching translation memory: {e}")
        return []

def update_translation_memory_entry(user_id, entry_id, data):
    """Update a translation memory entry"""
    try:
        # Ensure user owns this entry
        entry = get_translation_memory_entry(user_id, entry_id)
        if not entry:
            return None
            
        # Update data
        data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('translation_cache').update(data).eq('id', entry_id).eq('user_id', user_id).execute()
        
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating translation memory entry: {e}")
        return None

def get_translation_memory_entry(user_id, entry_id):
    """Get a specific translation memory entry"""
    try:
        response = supabase.table('translation_cache').select('*').eq('id', entry_id).eq('user_id', user_id).limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching translation memory entry: {e}")
        return None

def delete_translation_memory_entry(user_id, entry_id):
    """Delete a translation memory entry"""
    try:
        # Ensure user owns this entry
        entry = get_translation_memory_entry(user_id, entry_id)
        if not entry:
            return False
            
        response = supabase.table('translation_cache').delete().eq('id', entry_id).eq('user_id', user_id).execute()
        if hasattr(response, 'data'):
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting translation memory entry: {e}")
        return False

def get_translation_memory_stats(user_id):
    """Get statistics about the translation memory"""
    try:
        # Get total count
        count_response = supabase.table('translation_cache').select('count', count='exact').eq('user_id', user_id).execute()
        total_count = count_response.count if hasattr(count_response, 'count') else 0
        
        # Get language distribution
        lang_query = """
        SELECT target_language, COUNT(*) as count 
        FROM translation_cache 
        WHERE user_id = ? 
        GROUP BY target_language 
        ORDER BY count DESC
        """
        lang_response = supabase.rpc('exec_sql', {'query': lang_query.replace('?', f"'{user_id}'")}).execute()
        languages = lang_response.data if hasattr(lang_response, 'data') else []
        
        # Get recent activity
        recent_response = supabase.table('translation_cache').select('*').eq('user_id', user_id).order('updated_at', desc=True).limit(5).execute()
        recent = recent_response.data if hasattr(recent_response, 'data') else []
        
        return {
            'total_entries': total_count,
            'languages': languages,
            'recent_activity': recent
        }
    except Exception as e:
        logger.error(f"Error fetching translation memory stats: {e}")
        return {'total_entries': 0, 'languages': [], 'recent_activity': []}
        
# Document Pages Management Functions

def split_content_into_pages(content, page_size=1500):
    """Split content into pages of roughly equal size"""
    if not content:
        return []
        
    # Split by paragraphs first
    paragraphs = content.split('\n\n')
    
    pages = []
    current_page = []
    current_length = 0
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed page size and we already have content,
        # finish the current page and start a new one
        if current_length + len(paragraph) > page_size and current_page:
            pages.append('\n\n'.join(current_page))
            current_page = []
            current_length = 0
            
        # Handle very long paragraphs that exceed page size on their own
        if len(paragraph) > page_size:
            # If we have content waiting, add it to pages first
            if current_page:
                pages.append('\n\n'.join(current_page))
                current_page = []
                
            # Split the long paragraph at reasonable points (sentences)
            sentences = paragraph.replace('. ', '.\n').split('\n')
            temp_page = []
            temp_length = 0
            
            for sentence in sentences:
                if temp_length + len(sentence) > page_size and temp_page:
                    pages.append('\n'.join(temp_page))
                    temp_page = []
                    temp_length = 0
                    
                temp_page.append(sentence)
                temp_length += len(sentence)
                
            # Add any remaining content from the long paragraph
            if temp_page:
                pages.append('\n'.join(temp_page))
        else:
            # Normal case - add paragraph to current page
            current_page.append(paragraph)
            current_length += len(paragraph)
    
    # Add the last page if there's anything left
    if current_page:
        pages.append('\n\n'.join(current_page))
        
    return pages

def get_document_pages(user_id, document_id):
    """Get all pages for a document"""
    try:
        # Try first with user_id filter
        try:
            response = supabase.table('document_pages').select('*').eq('document_id', document_id).eq('user_id', user_id).order('page_number').execute()
            if hasattr(response, 'data'):
                return response.data
        except Exception as filter_error:
            logger.warning(f"Error fetching document pages with user_id filter: {filter_error}")
            # Try without user_id filter if the column doesn't exist yet
            response = supabase.table('document_pages').select('*').eq('document_id', document_id).order('page_number').execute()
            if hasattr(response, 'data'):
                return response.data
                
        return []
    except Exception as e:
        logger.error(f"Error fetching document pages: {e}")
        return []
        
def get_document_page(user_id, page_id):
    """Get a specific page"""
    try:
        # Try first with user_id filter
        try:
            response = supabase.table('document_pages').select('*').eq('id', page_id).eq('user_id', user_id).limit(1).execute()
            if hasattr(response, 'data') and response.data:
                return response.data[0]
        except Exception as filter_error:
            logger.warning(f"Error fetching document page with user_id filter: {filter_error}")
            # Try without user_id filter if the column doesn't exist yet
            response = supabase.table('document_pages').select('*').eq('id', page_id).limit(1).execute()
            if hasattr(response, 'data') and response.data:
                return response.data[0]
                
        return None
    except Exception as e:
        logger.error(f"Error fetching document page: {e}")
        return None
        
def create_document_page(user_id, page_data):
    """Create a document page"""
    try:
        # Ensure required fields
        if 'document_id' not in page_data or 'page_number' not in page_data:
            logger.error("Missing required fields for document page")
            return None
            
        # Add user_id
        page_data['user_id'] = user_id
        
        # Don't set timestamps explicitly, rely on database defaults
        # Remove these keys if they exist to avoid conflicts
        page_data.pop('created_at', None)
        page_data.pop('updated_at', None)
        
        # Generate a unique ID if not provided
        if 'id' not in page_data:
            page_data['id'] = str(uuid.uuid4())
            
        response = supabase.table('document_pages').insert(page_data).execute()
        
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error creating document page: {e}")
        return None
        
def update_document_page(user_id, page_id, data):
    """Update a document page"""
    try:
        # Remove timestamp fields to rely on database defaults
        data.pop('created_at', None)
        data.pop('updated_at', None)
        
        response = supabase.table('document_pages').update(data).eq('id', page_id).eq('user_id', user_id).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating document page: {e}")
        return None
        
def delete_document_page(user_id, page_id):
    """Delete a document page"""
    try:
        response = supabase.table('document_pages').delete().eq('id', page_id).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting document page: {e}")
        return False
        
def get_next_page(user_id, document_id, current_page_number):
    """Get the next page in sequence"""
    try:
        response = supabase.table('document_pages').select('*').eq('document_id', document_id).eq('user_id', user_id).gt('page_number', current_page_number).order('page_number').limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching next page: {e}")
        return None
        
def get_prev_page(user_id, document_id, current_page_number):
    """Get the previous page in sequence"""
    try:
        response = supabase.table('document_pages').select('*').eq('document_id', document_id).eq('user_id', user_id).lt('page_number', current_page_number).order('page_number', desc=True).limit(1).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching previous page: {e}")
        return None
        
def update_document_progress(user_id, document_id):
    """Update document progress based on page status"""
    try:
        # Get all pages for the document
        pages = get_document_pages(user_id, document_id)
        if not pages:
            return False
            
        total_pages = len(pages)
        completed_pages = sum(1 for page in pages if page.get('status') == 'completed')
        overall_progress = int((completed_pages / total_pages) * 100) if total_pages > 0 else 0
        
        # Update document with minimal fields to avoid schema mismatches
        update_data = {
            'status': 'in_progress' if completed_pages < total_pages else 'completed',
            'updated_at': 'now()'  # Use SQL function instead of Python timestamp
        }
        
        # Only try to set overall_progress if it exists in schema
        try:
            # Get the document first to see what fields exist
            document = get_document(user_id, document_id)
            if document and 'overall_progress' in document:
                update_data['overall_progress'] = overall_progress
            if document and 'total_pages' in document:
                update_data['total_pages'] = total_pages
            if document and 'completed_pages' in document:
                update_data['completed_pages'] = completed_pages
        except Exception as schema_error:
            logger.warning(f"Schema check failed, using minimal fields: {schema_error}")
        
        return update_document(user_id, document_id, update_data)
    except Exception as e:
        logger.error(f"Error updating document progress: {e}")
        return False