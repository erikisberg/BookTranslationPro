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