import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_data(user_id):
    """Fetch user data from Supabase"""
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return None

def save_user_data(user_id, data):
    """Save or update user data in Supabase"""
    try:
        existing_user = get_user_data(user_id)
        if existing_user:
            # Update existing user
            response = supabase.table('users').update(data).eq('id', user_id).execute()
        else:
            # Create new user entry
            data['id'] = user_id
            response = supabase.table('users').insert(data).execute()
        return response.data
    except Exception as e:
        print(f"Error saving user data: {e}")
        return None

def get_user_translations(user_id, limit=20, offset=0):
    """Fetch user's translation history"""
    try:
        response = supabase.table('translations').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(offset).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching translations: {e}")
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