import os
import uuid
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

def save_translation(user_id, original_filename, translated_text, settings=None):
    """Save a translation to the user's history"""
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
        
        return response.data[0]
    except Exception as e:
        print(f"Error saving translation: {e}")
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