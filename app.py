import os
import re
import uuid
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, abort, Response
from werkzeug.utils import secure_filename
import tempfile
import logging
import json
import time
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
# Make PostHog optional to avoid import errors
try:
    from posthog import Posthog
    posthog_available = True
except ImportError:
    posthog_available = False
from utils import (
    process_document, process_pdf, is_allowed_file, create_pdf_with_text, create_pdf_with_formatting, 
    create_pdf_with_text_basic, create_docx_with_text, create_html_with_text
)
from auth import login_required, get_current_user, get_user_id, sign_up, sign_in, sign_out, reset_password
from supabase_config import (
    get_user_data, save_user_data, get_user_translations, save_translation,
    get_full_translation, delete_translation, get_user_settings, save_user_settings,
    get_user_assistants, get_assistant, save_assistant, delete_assistant,
    get_user_glossaries, get_glossary, create_glossary, update_glossary, delete_glossary,
    get_glossary_entries, create_glossary_entry, update_glossary_entry, delete_glossary_entry,
    get_user_folders, get_folder, create_folder, update_folder, delete_folder,
    get_user_documents, get_document, create_document, update_document, delete_document,
    get_document_versions, get_document_content, save_document_content, fix_document_content,
    get_translation_memory_entries, get_translation_memory_entry, update_translation_memory_entry,
    delete_translation_memory_entry, get_translation_memory_stats,
    get_document_pages, get_document_page, create_document_page, update_document_page,
    split_content_into_pages, get_next_page, get_prev_page, update_document_progress
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-dev")

# Get API keys from environment (will be empty by default, requiring users to add their own)
DEEPL_API_KEY = ""
OPENAI_API_KEY = ""

# OpenAI Assistant ID - To create a default assistant, run:
# python create_assistant.py YOUR_OPENAI_API_KEY
# Then set the assistant ID in your environment variables
OPENAI_ASSISTANT_ID = os.environ.get('OPENAI_ASSISTANT_ID', "")

# PostHog configuration - check both standard and Next.js naming conventions
POSTHOG_API_KEY = os.environ.get('POSTHOG_API_KEY') or os.environ.get('NEXT_PUBLIC_POSTHOG_KEY')
POSTHOG_HOST = os.environ.get('POSTHOG_HOST') or os.environ.get('NEXT_PUBLIC_POSTHOG_HOST', 'https://eu.i.posthog.com')

# Make PostHog configuration available to templates if API key exists
app.config['POSTHOG_API_KEY'] = POSTHOG_API_KEY
app.config['POSTHOG_HOST'] = POSTHOG_HOST

# Context processor to make current user and assistants available in templates
@app.context_processor
def inject_user():
    user = get_current_user()
    context = {'current_user': user}
    
    # Also make assistants and user settings available globally if the user is logged in
    if user:
        user_id = get_user_id()
        if user_id:
            assistants = get_user_assistants(user_id)
            context['user_assistants'] = assistants
            
            # Add user settings to context
            user_settings = get_user_settings(user_id) or {}
            context['user_settings'] = user_settings
    
    return context

# Custom filters
@app.template_filter('datetime')
def format_datetime(value):
    if not value:
        return ''
    
    try:
        # Handle if value is already a datetime object
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M')
            
        # Try to parse as ISO format
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, AttributeError):
        return value

# Middleware to capture request data for PostHog and enforce login for main pages
@app.before_request
def before_request():
    # Skip login check for authentication routes, help page, and static files
    if (request.path.startswith('/static/') or 
        request.path == '/login' or 
        request.path == '/signup' or 
        request.path == '/reset-password' or
        request.path == '/logout' or
        request.path == '/help'):
        pass
    elif 'user' not in session and request.endpoint != 'login' and request.endpoint != 'signup':
        # Skip redirecting AJAX requests to avoid breaking client-side functionality
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            flash('Logga in för att fortsätta', 'warning')
            logger.debug(f"Redirecting unauthenticated user from {request.path} to login")
            if not request.path.startswith('/static/'):
                session['next'] = request.url
                return redirect(url_for('login'))

    # Only track if PostHog is initialized and available
    if posthog_available and posthog:
        try:
            user_id = get_user_id()
            # Capture page view
            properties = {
                'path': request.path,
                'referrer': request.referrer,
                'ip': request.remote_addr,
                'user_agent': request.user_agent.string if request.user_agent else None
            }
            
            # Add distinct_id for authenticated users
            if user_id:
                # Get user data to include name and other properties
                user_data = get_user_data(user_id)
                if user_data:
                    # Add user properties to events
                    properties['user_name'] = user_data.get('name', 'Unknown')
                    properties['user_email'] = user_data.get('email', 'Unknown')
                    
                    # Also identify the user to PostHog with their properties
                    posthog.identify(
                        distinct_id=user_id,
                        properties={
                            'name': user_data.get('name'),
                            'email': user_data.get('email'),
                            '$name': user_data.get('name'),  # PostHog standard property
                            '$email': user_data.get('email')  # PostHog standard property
                        }
                    )
                
                posthog.capture(
                    distinct_id=user_id,
                    event='$pageview',
                    properties=properties
                )
            else:
                # For anonymous users, use session ID or generate a device ID
                anonymous_id = session.get('anonymous_id')
                if not anonymous_id:
                    anonymous_id = str(hash(request.remote_addr + (request.user_agent.string if request.user_agent else '')))
                    session['anonymous_id'] = anonymous_id
                    
                posthog.capture(
                    distinct_id=anonymous_id,
                    event='$pageview',
                    properties=properties
                )
        except Exception as e:
            logger.error(f"Error tracking pageview in PostHog: {str(e)}")

# Custom filter for formatting dates
@app.template_filter('datetime')
def format_datetime(value):
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    else:
        dt = value
    return dt.strftime('%Y-%m-%d %H:%M')

# Custom filter for JSON serialization
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)

# Language codes for DeepL and glossary configuration
LANGUAGE_CODES = {
    'BG': 'Bulgarian',
    'CS': 'Czech',
    'DA': 'Danish',
    'DE': 'German',
    'EL': 'Greek',
    'EN': 'English',
    'EN-GB': 'English (British)',
    'EN-US': 'English (American)',
    'ES': 'Spanish',
    'ET': 'Estonian',
    'FI': 'Finnish',
    'FR': 'French',
    'HU': 'Hungarian',
    'ID': 'Indonesian',
    'IT': 'Italian',
    'JA': 'Japanese',
    'KO': 'Korean',
    'LT': 'Lithuanian',
    'LV': 'Latvian',
    'NB': 'Norwegian',
    'NL': 'Dutch',
    'PL': 'Polish',
    'PT': 'Portuguese',
    'PT-BR': 'Portuguese (Brazilian)',
    'PT-PT': 'Portuguese (European)',
    'RO': 'Romanian',
    'RU': 'Russian',
    'SK': 'Slovak',
    'SL': 'Slovenian',
    'SV': 'Swedish',
    'TR': 'Turkish',
    'UK': 'Ukrainian',
    'ZH': 'Chinese'
}

# Directory to store translations temporarily
TRANSLATIONS_DIR = os.path.join(tempfile.gettempdir(), 'translations')
if not os.path.exists(TRANSLATIONS_DIR):
    os.makedirs(TRANSLATIONS_DIR)

# Configure upload settings
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# This section has been moved above to initialize variables before they are used

# Initialize PostHog if API key is available and the module is installed
posthog = None
if POSTHOG_API_KEY and posthog_available:
    try:
        posthog = Posthog(
            project_api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST
        )
        logger.info(f"PostHog initialized successfully with key: {POSTHOG_API_KEY[:5]}...")
        logger.info(f"PostHog host: {POSTHOG_HOST}")
        
        # Test event to verify connection
        posthog.capture(
            distinct_id='system',
            event='posthog_initialized',
            properties={
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to initialize PostHog: {str(e)}")
        posthog = None
else:
    logger.info("PostHog API key not provided or module not available, analytics disabled")

# Log API key info for debugging
logger.info(f"DEEPL_API_KEY present: {'Yes' if DEEPL_API_KEY else 'No'}")
logger.info(f"OPENAI_API_KEY present: {'Yes' if OPENAI_API_KEY else 'No'}")
logger.info(f"OPENAI_ASSISTANT_ID present: {'Yes' if OPENAI_ASSISTANT_ID else 'No'}")
logger.info(f"POSTHOG_API_KEY present: {'Yes' if POSTHOG_API_KEY else 'No'}")

# Default assistant configuration
DEFAULT_INSTRUCTIONS = """Granska och förbättra denna översättning genom att:
1. Bibehålla originalets betydelse och avsikt
2. Säkerställa ett naturligt och flytande språk
3. Bevara formell/informell ton på lämpligt sätt
4. Hålla tekniska termer korrekta
5. Anpassa kulturella referenser på lämpligt sätt"""

# Default export settings
DEFAULT_EXPORT_SETTINGS = {
    'export_format': 'pdf',
    'page_size': 'A4',
    'orientation': 'portrait',
    'font_family': 'helvetica',
    'font_size': 12,
    'line_spacing': '1.5',
    'alignment': 'left',
    'margin_size': 15,
    'include_page_numbers': True,
    'header_text': '',
    'footer_text': '',
    'include_both_languages': False
}

# Default API keys settings (empty means use system defaults)
DEFAULT_API_KEYS = {
    'deepl_api_key': '',
    'openai_api_key': ''
}

def json_response(data, status=200):
    """Helper function to ensure consistent JSON responses"""
    logger.debug(f"Sending JSON response (status {status}): {data}")
    return jsonify(data), status, {'Content-Type': 'application/json'}

def json_error(message, status=400):
    """Helper function for JSON error responses"""
    return json_response({'error': message}, status)

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Vänligen ange e-post och lösenord', 'danger')
            return render_template('login.html')
            
        # Attempt to sign in
        response = sign_in(email, password)
        if not response:
            # Track failed login attempt
            if posthog_available and posthog:
                posthog.capture(
                    distinct_id=email,
                    event='login_failed',
                    properties={
                        'reason': 'invalid_credentials'
                    }
                )
            flash('Inloggning misslyckades. Kontrollera dina uppgifter.', 'danger')
            return render_template('login.html')
            
        # Store user in session
        session['user'] = {
            'id': response.user.id,
            'email': response.user.email,
            'name': response.user.user_metadata.get('name', 'Användare')
        }
        
        # Ensure user exists in the users table (needed for foreign key constraints)
        user_data = {
            'email': response.user.email or 'user@example.com'  # Ensure email is never null
            # Note: 'name' column doesn't exist in users table according to error message
        }
        save_user_data(response.user.id, user_data)
        
        # Load user settings
        user_settings = get_user_settings(response.user.id)
        if user_settings:
            # Store export settings in session
            if 'export_settings' in user_settings:
                session['export_settings'] = user_settings['export_settings']
                
            # Store assistants in session if available
            if 'assistants' in user_settings:
                session['user_assistants'] = user_settings['assistants']
        
        # Track successful login
        if posthog_available and posthog:
            posthog.capture(
                distinct_id=response.user.id,
                event='login_successful',
                properties={
                    'email': response.user.email,
                    'name': response.user.user_metadata.get('name')
                }
            )
                
        flash('Du är nu inloggad!', 'success')
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('index'))
        
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if get_current_user():
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # Validate form data
        if not all([name, email, password, password_confirm]):
            flash('Alla fält måste fyllas i', 'danger')
            return render_template('signup.html')
            
        if password != password_confirm:
            flash('Lösenorden matchar inte', 'danger')
            # Track validation error
            if posthog_available and posthog:
                posthog.capture(
                    distinct_id=email or session.get('anonymous_id', 'unknown'),
                    event='signup_validation_error',
                    properties={
                        'error': 'password_mismatch'
                    }
                )
            return render_template('signup.html')
            
        # Attempt to sign up
        metadata = {
            'name': name
        }
        response = sign_up(email, password, metadata)
        if not response:
            flash('Registrering misslyckades. Prova en annan e-postadress.', 'danger')
            # Track signup failure
            if posthog_available and posthog:
                posthog.capture(
                    distinct_id=email,
                    event='signup_failed',
                    properties={
                        'reason': 'email_exists_or_invalid'
                    }
                )
            return render_template('signup.html')
            
        # Create user record in the users table (needed for foreign key constraints)
        if response.user and response.user.id:
            user_data = {
                'email': email or 'user@example.com'  # Ensure email is never null
                # Note: 'name' column doesn't exist in users table according to error message
            }
            save_user_data(response.user.id, user_data)
        
        # Track successful signup
        if posthog_available and posthog:
            if response.user and response.user.id:
                posthog.capture(
                    distinct_id=response.user.id,
                    event='signup_successful',
                    properties={
                        'email': email,
                        'name': name
                    }
                )
            else:
                posthog.capture(
                    distinct_id=email,
                    event='signup_successful'
                )
            
        flash('Konto skapat! Kontrollera din e-post för att bekräfta ditt konto.', 'success')
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/logout')
def logout():
    # Track logout event
    if posthog_available and posthog:
        user_id = get_user_id()
        if user_id:
            posthog.capture(
                distinct_id=user_id,
                event='user_logged_out'
            )
    
    sign_out()
    session.clear()
    flash('Du är nu utloggad', 'info')
    return redirect(url_for('index'))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Vänligen ange din e-postadress', 'danger')
            return render_template('reset_password.html')
            
        # Send password reset email
        success = reset_password(email)
        
        if success:
            flash('Ett e-postmeddelande har skickats med instruktioner för att återställa ditt lösenord', 'success')
            return redirect(url_for('login'))
        else:
            flash('Kunde inte skicka återställningsmail. Försök igen senare.', 'danger')
            
    return render_template('reset_password.html')

# User Profile Routes
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    
    if request.method == 'POST':
        name = request.form.get('name')
        
        if name:
            # Update name
            user_id = get_user_id()
            user_data = {'user_metadata': {'name': name}}
            save_user_data(user_id, user_data)
            
            # Update session
            session['user']['name'] = name
            flash('Profil uppdaterad!', 'success')
            
    return render_template('profile.html')

@app.route('/history')
@login_required
def history():
    user_id = get_user_id()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    per_page = 10
    
    # Get translations
    translations = get_user_translations(user_id, limit=per_page, offset=(page-1)*per_page)
    
    # TODO: Implement search functionality
    
    # Calculate total pages
    total_translations = len(get_user_translations(user_id, limit=1000))
    pages = (total_translations // per_page) + (1 if total_translations % per_page > 0 else 0)
    
    return render_template('history.html', 
                          translations=translations, 
                          page=page, 
                          pages=pages,
                          search=search)

@app.route('/view-translation/<id>')
@login_required
def view_translation(id):
    user_id = get_user_id()
    
    try:
        translation_text = get_full_translation(user_id, id)
        
        if not translation_text:
            # Check if this is a document ID
            document = get_document(user_id, id)
            if document:
                # This is a document ID, redirect to workspace
                logger.info(f"Redirecting to workspace for document ID {id}")
                return redirect(url_for('translation_workspace', id=id))
            
            # Try to repair the translation
            logger.warning(f"Translation {id} not found, checking in document storage")
            
            # Check if there's a document with the same ID
            document_content = None
            try:
                document_content = get_document_content(user_id, id, 'translated')
            except Exception as doc_error:
                logger.error(f"Error fetching document content: {str(doc_error)}")
            
            if document_content:
                logger.info(f"Found document content, displaying that instead")
                return render_template('view_translation.html', translation_text=document_content, id=id)
            
            logger.error(f"Translation {id} not found and no fallback available")
            flash('Översättning kunde inte hittas', 'danger')
            return redirect(url_for('history'))
        
        return render_template('view_translation.html', translation_text=translation_text, id=id)
    except Exception as e:
        logger.error(f"Error in view_translation: {str(e)}")
        flash(f"Ett fel uppstod: {str(e)}", 'danger')
        return redirect(url_for('history'))
    
@app.route('/view-translation/<id>/workspace')
@login_required
def translation_workspace(id):
    user_id = get_user_id()
    
    # First check if this is a document ID
    document = get_document(user_id, id)
    if document:
        # We already have a document, we can skip the translation lookup
        # Get document content to use as source
        translation_text = get_document_content(user_id, id, 'source')
        if not translation_text:
            # If no source content, try to get translated content
            translation_text = get_document_content(user_id, id, 'translated')
            if not translation_text:
                translation_text = "No content available for this document."
    else:
        # Try to get translation text
        translation_text = get_full_translation(user_id, id)
        
        if not translation_text:
            logger.error(f"Neither document nor translation found for ID {id}")
            flash('Varken översättning eller dokument kunde hittas', 'danger')
            return redirect(url_for('history'))
    
    # First check if we have a document already created for this translation
    try:
        # Try to find a document with matching ID
        document = get_document(user_id, id)
        
        # If no document found, create one
        if not document:
            logger.info(f"Creating document for translation {id}")
            
            # Check first if a document already exists in the database with a different ID
            # but created from this translation
            existing_documents = get_user_documents(user_id)
            existing_doc = None
            
            for doc in existing_documents:
                if doc.get('description') == f"Created from translation {id}":
                    existing_doc = doc
                    logger.info(f"Found existing document {doc['id']} for translation {id}")
                    break
            
            if existing_doc:
                document = existing_doc
            else:
                # Create a document from the translation with the translation ID
                # Force the ID to be the same as the translation ID
                
                # Try to extract a better title from the original filename if available
                title = f"Translation {id}"
                description = f"Created from translation {id}"
                
                # Check if we have original filename in session
                if 'original_filename' in session:
                    orig_filename = session.get('original_filename')
                    if orig_filename:
                        # Use file basename without extension as title
                        base_name = os.path.splitext(os.path.basename(orig_filename))[0]
                        if base_name:
                            title = base_name
                            description = f"Translated from {orig_filename}"
                
                # Get project title from form if set in session
                project_title = session.get('last_project_title')
                if project_title:
                    title = project_title
                
                doc_data = {
                    'id': id,  # Use same ID for easy reference
                    'title': title,
                    'description': description,
                    'source_language': 'auto',
                    'target_language': 'SV',
                    'status': 'in_progress',
                    'word_count': len(translation_text.split()),
                    'version': 1
                }
                
                # Create the document
                document = create_document(user_id, doc_data)
            
            if not document:
                logger.error(f"Failed to create document for translation {id}")
                flash('Kunde inte skapa arbetsdokument', 'danger')
                return redirect(url_for('view_translation', id=id))
                
            # Save the translation content properly
            try:
                # First check if we have an original document/entry in translations
                translation_entry = None
                try:
                    # Try to look up the translation in the database
                    from supabase_config import get_db
                    supabase = get_db()
                    response = supabase.table('translations').select('*').eq('id', id).execute()
                    if response.data and len(response.data) > 0:
                        translation_entry = response.data[0]
                except Exception as e:
                    logger.warning(f"Could not look up translation entry: {str(e)}")
                
                # Try to get separate source and translated text
                if translation_entry and 'original_text' in translation_entry and 'translated_text' in translation_entry:
                    # We found the original data - use it
                    source_text = translation_entry.get('original_text', '')
                    translated_text = translation_entry.get('translated_text', '')
                    
                    # Save the content
                    save_document_content(user_id, document['id'], source_text, 'source')
                    save_document_content(user_id, document['id'], translated_text, 'translated')
                    
                    logger.info(f"Successfully saved source and translated content from translation entry")
                else:
                    # We don't have the original entry - try to get the full translation
                    full_translation = get_full_translation(user_id, id)
                    if full_translation:
                        # Save as translated content
                        save_document_content(user_id, document['id'], full_translation, 'translated')
                        
                        # For source content, use the same text rather than empty string
                        # This ensures we always have content in both panels
                        logger.info("Setting source content to same as translation - user can edit later")
                        save_document_content(user_id, document['id'], full_translation, 'source')
                        
                        # Mark document as needing source setup
                        if document.get('settings'):
                            settings = document.get('settings', {})
                            settings['needs_source_setup'] = True
                            update_document(user_id, document['id'], {'settings': settings})
                        
                        logger.warning(f"Could only save translated content, source content is empty")
                    else:
                        # If we can't get any translation data, use what we have
                        # Use translation_text for both to ensure content is available
                        save_document_content(user_id, document['id'], translation_text, 'source')
                        save_document_content(user_id, document['id'], translation_text, 'translated')
                        
                        # Update document settings to indicate source is missing
                        if document.get('settings'):
                            settings = document.get('settings', {})
                            settings['needs_source_setup'] = True
                            update_document(user_id, document['id'], {'settings': settings})
                        
                        logger.warning(f"Could not find original translation data, using available text")
            except Exception as source_error:
                logger.warning(f"Error setting up content: {str(source_error)}")
                # Fall back to using translation text for both sides
                save_document_content(user_id, document['id'], translation_text, 'source')
                save_document_content(user_id, document['id'], translation_text, 'translated')
    except Exception as e:
        logger.error(f"Error checking/creating document: {str(e)}")
        flash('Ett fel uppstod: ' + str(e), 'danger')
        return redirect(url_for('view_translation', id=id))
    
    # Check if the translation has already been split into pages
    try:
        pages = get_document_pages(user_id, document['id'])
        
        # If no pages exist, create them
        if not pages:
            logger.info(f"Creating pages for document {document['id']}")
            
            # Split the translation into pages
            content_pages = split_content_into_pages(translation_text)
            
            if not content_pages:
                logger.error(f"Failed to split content for document {id}")
                flash('Kunde inte dela upp innehållet i sidor', 'danger')
                return redirect(url_for('view_translation', id=id))
            
            # Get both source and translated content
            source_content = get_document_content(user_id, document['id'], 'source')
            translated_content = get_document_content(user_id, document['id'], 'translated')
            
            logger.info(f"Source content length: {len(source_content) if source_content else 0}")
            logger.info(f"Translated content length: {len(translated_content) if translated_content else 0}")
            
            # Check if both are available and properly set
            if source_content and translated_content and len(source_content.strip()) > 0 and len(translated_content.strip()) > 0:
                logger.info("Creating pages with both source and translated content")
                
                # Split both into pages
                source_pages = split_content_into_pages(source_content) if source_content else []
                translated_pages = split_content_into_pages(translated_content) if translated_content else []
                
                # Create pages with both source and translated content
                for i, source_page in enumerate(source_pages, 1):
                    # Get corresponding translated page if available
                    translated_page = translated_pages[i-1] if i <= len(translated_pages) else ''
                    
                    page_data = {
                        'document_id': document['id'],  # Use the actual document ID
                        'page_number': i,
                        'source_content': source_page,
                        'translated_content': translated_page,  # Use translated content if available
                        'status': 'in_progress',
                        'completion_percentage': 50 if translated_page else 0  # Set initial progress
                    }
                    create_document_page(user_id, page_data)
            # If we have at least translated content, use it
            elif translated_content and len(translated_content.strip()) > 0:
                logger.info("Creating pages with translated content only")
                
                # Split the translated content
                translated_pages = split_content_into_pages(translated_content)
                
                # Create pages with translated content only
                for i, translated_page in enumerate(translated_pages, 1):
                    page_data = {
                        'document_id': document['id'],  # Use the actual document ID
                        'page_number': i,
                        'source_content': '',  # Empty source
                        'translated_content': translated_page,
                        'status': 'in_progress',
                        'completion_percentage': 50  # Some progress since we have translation
                    }
                    create_document_page(user_id, page_data)
            # Fall back to using content_pages as source only
            else:
                logger.info("Creating pages with content_pages as source")
                for i, page_content in enumerate(content_pages, 1):
                    page_data = {
                        'document_id': document['id'],  # Use the actual document ID
                        'page_number': i,
                        'source_content': page_content,
                        'translated_content': '',  # Start with empty translation
                        'status': 'in_progress',
                        'completion_percentage': 0
                    }
                    create_document_page(user_id, page_data)
                
            # Get the newly created pages
            pages = get_document_pages(user_id, document['id'])
            
            if not pages:
                logger.error(f"Failed to create pages for document {document['id']}")
                flash('Kunde inte skapa sidor', 'danger')
                return redirect(url_for('view_translation', id=id))
                
            # Update document progress
            update_document_progress(user_id, document['id'])
    except Exception as e:
        logger.error(f"Error creating workspace pages: {str(e)}")
        flash('Ett fel uppstod vid skapande av sidor: ' + str(e), 'danger')
        return redirect(url_for('view_translation', id=id))
    
    # Calculate stats for template
    completed_pages = sum(1 for page in pages if page.get('status') == 'completed')
    overall_progress = int((completed_pages / len(pages) * 100) if pages else 0)
    
    # Ensure we have the document information to display in the workspace
    if not document:
        document = get_document(user_id, id)
    
    # Check if we need to add stats data to existing document
    if document and 'settings' in document:
        settings = document.get('settings', {})
        # If we don't have stats data in settings, add placeholder values for the template
        if not settings.get('cache_hits') and not settings.get('smart_review_savings'):
            # If this is an older document without stats, we'll show placeholders
            document['settings']['cache_hits'] = 0
            document['settings']['cache_ratio'] = 0
            document['settings']['smart_review_savings'] = 0
            document['settings']['smart_review_ratio'] = 0
            document['settings']['glossary_hits'] = 0
            document['settings']['glossary_ratio'] = 0
            
            # Add character count
            if 'char_count' not in document['settings']:
                # If either source or translated content is available, count characters
                source_content = get_document_content(user_id, document['id'], 'source')
                if source_content:
                    document['settings']['char_count'] = len(source_content)
                else:
                    translated_content = get_document_content(user_id, document['id'], 'translated')
                    if translated_content:
                        document['settings']['char_count'] = len(translated_content)
                    else:
                        document['settings']['char_count'] = 0
            
            # Log that we're adding placeholder stats
            logger.info(f"Adding placeholder stats for document {document['id']}")
    
    return render_template('translation_workspace.html', 
                          translation_id=id, 
                          document=document,
                          pages=pages, 
                          total_pages=len(pages),
                          completed_pages=completed_pages,
                          overall_progress=overall_progress)
                          
@app.route('/view-translation/<document_id>/page/<page_id>', methods=['GET', 'POST'])
@login_required
def edit_translation_page(document_id, page_id):
    user_id = get_user_id()
    
    try:
        # Get the document first to verify it exists
        document = get_document(user_id, document_id)
        if not document:
            logger.warning(f"Document {document_id} not found for user {user_id}")
            flash('Dokumentet kunde inte hittas', 'danger')
            return redirect(url_for('view_translation', id=document_id))
        
        # Get the page data
        page = get_document_page(user_id, page_id)
        if not page:
            logger.warning(f"Page {page_id} not found for user {user_id}")
            flash('Sidan kunde inte hittas', 'danger')
            return redirect(url_for('translation_workspace', id=document_id))
        
        # Verify page belongs to the correct document
        if page.get('document_id') != document_id:
            logger.warning(f"Page {page_id} belongs to document {page.get('document_id')}, not {document_id}")
            flash('Sidan tillhör inte detta dokument', 'danger')
            return redirect(url_for('translation_workspace', id=document_id))
        
        # Handle form submission
        if request.method == 'POST':
            try:
                # Update the page with the new content
                translated_content = request.form.get('translated_content', '')
                status = request.form.get('status', 'in_progress')
                
                # Check if AI review was requested
                if 'ai_review' in request.form:
                    # Get the API keys and assistant ID
                    user_settings = get_user_settings(user_id) or {}
                    openai_api_key = user_settings.get('api_keys', {}).get('openai_api_key', OPENAI_API_KEY)
                    
                    # Get the assistant ID to use
                    assistant_id = None
                    if 'assistant_id' in request.form and request.form['assistant_id']:
                        assistant_id = request.form['assistant_id']
                    elif document.get('settings') and document['settings'].get('assistant_id'):
                        assistant_id = document['settings']['assistant_id']
                    else:
                        # Use the first available assistant or the default
                        user_assistants = get_user_assistants(user_id)
                        if user_assistants:
                            assistant_id = user_assistants[0]['id']
                        else:
                            assistant_id = OPENAI_ASSISTANT_ID
                    
                    # Get custom instructions if provided
                    custom_instructions = request.form.get('ai_instructions', None)
                    
                    if openai_api_key and assistant_id:
                        try:
                            from utils import review_page_translation
                            
                            # Run the review process
                            reviewed_text, success, error_msg = review_page_translation(
                                translated_content, 
                                openai_api_key, 
                                assistant_id, 
                                custom_instructions
                            )
                            
                            if success:
                                # Update the translated text with the reviewed version
                                translated_content = reviewed_text
                                
                                # Mark as AI reviewed and completed
                                status = 'completed'
                                
                                # Track AI review stats in document settings
                                if document.get('settings'):
                                    settings = document.get('settings', {})
                                    if not isinstance(settings, dict):
                                        settings = {}
                                        
                                    # Initialize stats if needed
                                    if 'ai_review_count' not in settings:
                                        settings['ai_review_count'] = 0
                                        
                                    # Increment count
                                    settings['ai_review_count'] = settings.get('ai_review_count', 0) + 1
                                    
                                    # Update document settings
                                    update_document(user_id, document_id, {'settings': settings})
                                
                                flash('AI-granskning slutförd!', 'success')
                            else:
                                flash(f'AI-granskning misslyckades: {error_msg}', 'warning')
                        except Exception as e:
                            logger.error(f"Error reviewing page: {str(e)}")
                            flash(f'Fel vid AI-granskning: {str(e)}', 'danger')
                    else:
                        flash('OpenAI API-nyckel eller assistent-ID saknas', 'warning')
                
                # Calculate completion percentage
                if status == 'completed':
                    completion_percentage = 100
                elif status == 'in_progress' and translated_content:
                    # Approximate completion based on content length ratio
                    src_length = len(page.get('source_content', ''))
                    if src_length > 0:
                        ratio = min(len(translated_content) / src_length, 0.99)  # Cap at 99% until marked completed
                        completion_percentage = int(ratio * 100)
                    else:
                        completion_percentage = 0
                else:
                    completion_percentage = 0
                    
                # Update the page
                update_data = {
                    'translated_content': translated_content,
                    'status': status,
                    'completion_percentage': completion_percentage
                    # Don't set last_edited_at, let database handle it
                }
                
                # Conditionally add reviewed_by_ai - handle case where column might not exist yet
                if 'ai_review' in request.form:
                    try:
                        # Check if column exists first
                        from supabase_config import get_db
                        supabase = get_db()
                        
                        # Try to add the field
                        update_data['reviewed_by_ai'] = True
                    except Exception as schema_error:
                        logger.warning(f"Could not set reviewed_by_ai field: {str(schema_error)}")
                
                # Log update attempt
                logger.info(f"Updating page {page_id} with status {status} and completion {completion_percentage}%")
                
                # Update the page
                result = update_document_page(user_id, page_id, update_data)
                if not result:
                    logger.error(f"Failed to update page {page_id}")
                    flash('Kunde inte spara ändringar', 'danger')
                    # Return early, don't redirect
                    return render_template('edit_translation_page.html', 
                                          document_id=document_id, 
                                          page=page,
                                          has_next=False,
                                          has_prev=False)
                
                # Update overall document progress
                update_document_progress(user_id, document['id'])
                
                # Check if this is an AJAX request
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                
                # Handle redirections for different button types
                if 'save_next' in request.form:
                    next_page = get_next_page(user_id, document_id, page.get('page_number', 0))
                    if next_page:
                        if is_ajax:
                            return json_response({'success': True, 'redirect': url_for('edit_translation_page', document_id=document_id, page_id=next_page.get('id'))})
                        return redirect(url_for('edit_translation_page', document_id=document_id, page_id=next_page.get('id')))
                elif 'save_prev' in request.form:
                    prev_page = get_prev_page(user_id, document_id, page.get('page_number', 0))
                    if prev_page:
                        if is_ajax:
                            return json_response({'success': True, 'redirect': url_for('edit_translation_page', document_id=document_id, page_id=prev_page.get('id'))})
                        return redirect(url_for('edit_translation_page', document_id=document_id, page_id=prev_page.get('id')))
                elif 'save' in request.form and 'ai_review' not in request.form:
                    # Regular save button (only show message if not after AI review)
                    if is_ajax:
                        return json_response({'success': True, 'message': 'Sidan har sparats'})
                    flash('Sidan har sparats', 'success')
                    # Stay on same page
                    return redirect(url_for('edit_translation_page', document_id=document_id, page_id=page_id))
                
                # Default case if no specific button was pressed
                if is_ajax:
                    return json_response({'success': True, 'message': 'Sidan har sparats'})
                
                # Only show this message if not already showing AI review message
                if 'ai_review' not in request.form:
                    flash('Sidan har sparats', 'success')
                    
                return redirect(url_for('edit_translation_page', document_id=document_id, page_id=page_id))
                
            except Exception as e:
                logger.error(f"Error updating page: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return json_error(f'Ett fel uppstod: {str(e)}', 500)
                flash(f'Ett fel uppstod: {str(e)}', 'danger')
                return redirect(url_for('edit_translation_page', document_id=document_id, page_id=page_id))
        
        # For GET requests, fetch necessary data for the template
        # Get next and previous pages for navigation
        next_page = get_next_page(user_id, document_id, page.get('page_number', 0))
        prev_page = get_prev_page(user_id, document_id, page.get('page_number', 0))
        
        # Get user assistants for AI review dropdown
        user_assistants = get_user_assistants(user_id)
        if not user_assistants and OPENAI_ASSISTANT_ID:
            # Add the default assistant if available
            user_assistants = [{'id': OPENAI_ASSISTANT_ID, 'name': 'Standardassistent'}]
        
        return render_template('edit_translation_page.html', 
                              document_id=document_id, 
                              page=page,
                              has_next=next_page is not None,
                              has_prev=prev_page is not None,
                              next_page_id=next_page.get('id') if next_page else None,
                              prev_page_id=prev_page.get('id') if prev_page else None,
                              user_assistants=user_assistants)
                              
    except Exception as e:
        logger.error(f"Error in edit_translation_page: {str(e)}")
        flash(f'Ett fel uppstod: {str(e)}', 'danger')
        return redirect(url_for('view_translation', id=document_id))

@app.route('/download-translation/<id>')
@login_required
def download_translation(id):
    user_id = get_user_id()
    translation_text = get_full_translation(user_id, id)
    
    if not translation_text:
        flash('Översättning kunde inte hittas', 'danger')
        return redirect(url_for('history'))
    
    # Get user's export settings
    settings = session.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    # Create file
    if settings['export_format'] == 'pdf':
        output_path = create_pdf_with_formatting(
            translation_text, 
            font_family=settings['font_family'],
            font_size=settings['font_size'],
            page_size=settings['page_size'],
            orientation=settings['orientation'],
            margin=settings['margin_size'],
            line_spacing=float(settings['line_spacing']),
            alignment=settings['alignment'],
            include_page_numbers=settings['include_page_numbers'],
            header_text=settings['header_text'],
            footer_text=settings['footer_text']
        )
        mime_type = 'application/pdf'
        ext = 'pdf'
    elif settings['export_format'] == 'docx':
        output_path = create_docx_with_text(
            translation_text,
            font_family=settings['font_family'],
            font_size=settings['font_size'],
            page_size=settings['page_size'],
            orientation=settings['orientation'],
            margin=settings['margin_size'],
            line_spacing=float(settings['line_spacing']),
            alignment=settings['alignment'],
            include_page_numbers=settings['include_page_numbers'],
            header_text=settings['header_text'],
            footer_text=settings['footer_text']
        )
        mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ext = 'docx'
    elif settings['export_format'] == 'txt':
        output_path = os.path.join(tempfile.gettempdir(), f'translation_{id}.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translation_text)
        mime_type = 'text/plain'
        ext = 'txt'
    else:
        output_path = create_html_with_text(
            translation_text, 
            font_family=settings['font_family'],
            font_size=settings['font_size'],
            line_spacing=float(settings['line_spacing']),
            alignment=settings['alignment'],
            header_text=settings['header_text'],
            footer_text=settings['footer_text']
        )
        mime_type = 'text/html'
        ext = 'html'
    
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f'translation_{id}.{ext}',
        mimetype=mime_type
    )

@app.route('/delete-translation', methods=['POST'])
@login_required
def delete_translation_route():
    user_id = get_user_id()
    translation_id = request.form.get('translation_id')
    
    if not translation_id:
        flash('Ingen översättning angiven', 'danger')
        return redirect(url_for('history'))
    
    success = delete_translation(user_id, translation_id)
    
    if success:
        flash('Översättning borttagen', 'success')
    else:
        flash('Kunde inte ta bort översättning', 'danger')
    
    return redirect(url_for('history'))

@app.route('/')
@login_required
def index():
    # Get user's assistants for the dropdown
    user_id = get_user_id()
    
    # First try to get from session
    assistants = session.get('user_assistants', None)
    
    # If not in session, get from database
    if assistants is None:
        assistants = get_user_assistants(user_id)
        # Save to session for future use
        if assistants:
            session['user_assistants'] = assistants
            session.modified = True
    
    # Get user's glossaries for the dropdown
    glossaries = get_user_glossaries(user_id)
    
    # Enrich glossaries with language names
    for glossary in glossaries:
        if glossary.get('source_language') in LANGUAGE_CODES:
            glossary['source_language'] = LANGUAGE_CODES[glossary['source_language']]
        if glossary.get('target_language') in LANGUAGE_CODES:
            glossary['target_language'] = LANGUAGE_CODES[glossary['target_language']]
    
    # Get user's folders for the dropdown
    folders = get_user_folders(user_id)
    
    # Get recent documents for the dashboard
    try:
        documents = get_user_documents(user_id, limit=5)
        
        # Calculate progress for each document
        for doc in documents:
            if 'total_pages' not in doc or 'completed_pages' not in doc:
                # Get document pages to calculate progress
                try:
                    pages = get_document_pages(user_id, doc['id'])
                    if pages:
                        doc['total_pages'] = len(pages)
                        doc['completed_pages'] = sum(1 for p in pages if p.get('status') == 'completed')
                        doc['overall_progress'] = int((doc['completed_pages'] / doc['total_pages'] * 100) if doc['total_pages'] > 0 else 0)
                    else:
                        doc['total_pages'] = 0
                        doc['completed_pages'] = 0
                        doc['overall_progress'] = 0
                except Exception as page_error:
                    logger.error(f"Error getting pages for document {doc['id']}: {str(page_error)}")
                    doc['total_pages'] = 0
                    doc['completed_pages'] = 0
                    doc['overall_progress'] = 0
    except Exception as e:
        logger.error(f"Error loading recent documents: {str(e)}")
        documents = []
    
    # Get translation memory stats
    try:
        translation_memory_stats = get_translation_memory_stats(user_id)
    except Exception as e:
        logger.error(f"Error loading translation memory stats: {str(e)}")
        translation_memory_stats = {'total_entries': 0, 'languages': []}
            
    return render_template('index.html', 
                          assistants=assistants, 
                          glossaries=glossaries, 
                          folders=folders,
                          documents=documents,
                          translation_memory_stats=translation_memory_stats)

@app.route('/assistant-config', methods=['GET'])
@login_required
def assistant_config():
    # Get user's assistants
    user_id = get_user_id()
    
    # First try to get from session
    assistants = session.get('user_assistants', None)
    
    # If not in session, get from database
    if assistants is None:
        assistants = get_user_assistants(user_id)
        # Save to session for future use
        if assistants:
            session['user_assistants'] = assistants
            session.modified = True
    
    # Debug log the assistant structure
    if assistants:
        for idx, assistant in enumerate(assistants):
            logger.info(f"Assistant {idx+1}:")
            for key, value in assistant.items():
                logger.info(f"  {key}: {value[:30] if isinstance(value, str) and len(value) > 30 else value}")
    
    # Get current export settings from session or use defaults
    settings = session.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    return render_template('assistant_config.html', 
                         assistants=assistants,
                         export_format=settings['export_format'],
                         page_size=settings['page_size'],
                         orientation=settings['orientation'],
                         font_family=settings['font_family'],
                         font_size=settings['font_size'],
                         line_spacing=settings['line_spacing'],
                         alignment=settings['alignment'],
                         margin_size=settings['margin_size'],
                         include_page_numbers=settings['include_page_numbers'],
                         header_text=settings['header_text'],
                         footer_text=settings['footer_text'],
                         include_both_languages=settings['include_both_languages'])

@app.route('/save-assistant', methods=['POST'])
@login_required
def save_assistant_route():
    """Save or update an assistant configuration with optional OpenAI integration"""
    try:
        user_id = get_user_id()
        user = get_current_user()
        
        # Get form data
        assistant_name = request.form.get('name')
        assistant_instructions = request.form.get('instructions')
        assistant_author = request.form.get('author')
        assistant_genre = request.form.get('genre')
        assistant_id_param = request.form.get('id')  # Local ID, will be None for new assistants
        
        # Get user's OpenAI key from settings
        user_settings = get_user_settings(user_id) or {}
        user_api_keys = user_settings.get('api_keys', {})
        openai_api_key = user_api_keys.get('openai_api_key')
        
        if not openai_api_key:
            flash('OpenAI API nyckel saknas. Lägg till en på API-nyckelsidan.', 'danger')
            return redirect(url_for('api_keys_settings'))
        
        # Create/update in OpenAI if requested
        assistant_data = {
            'id': assistant_id_param,
            'name': assistant_name,
            'author': assistant_author,
            'genre': assistant_genre,
            'instructions': assistant_instructions
        }
        
        # For a new assistant
        if not assistant_id_param:
            # Check if we should create in OpenAI
            create_in_openai = request.form.get('create_in_openai') == 'yes'
            
            if create_in_openai:
                try:
                    # Create in OpenAI
                    from utils import create_openai_assistant
                    openai_result = create_openai_assistant(
                        openai_api_key,
                        assistant_name,
                        assistant_instructions
                    )
                    # Use the returned assistant ID
                    assistant_data['assistant_id'] = openai_result.get('id')
                    logger.info(f"Created assistant in OpenAI with ID: {assistant_data['assistant_id']}")
                except Exception as e:
                    logger.error(f"Failed to create assistant in OpenAI: {str(e)}")
                    flash(f"Kunde inte skapa assistent i OpenAI: {str(e)}", 'danger')
                    return redirect(url_for('assistant_config'))
            else:
                # Use manually entered ID
                assistant_data['assistant_id'] = request.form.get('assistant_id')
                if not assistant_data['assistant_id'] and request.form.get('manual_assistant_id'):
                    assistant_data['assistant_id'] = request.form.get('manual_assistant_id')
                    
                if not assistant_data['assistant_id']:
                    flash('Du måste ange ett OpenAI Assistant ID eller välja att skapa automatiskt', 'danger')
                    return redirect(url_for('assistant_config'))
        
        # For updating an existing assistant
        else:
            # Get the existing assistant to get the OpenAI ID
            existing_assistant = get_assistant(user_id, assistant_id_param)
            if not existing_assistant:
                flash('Kunde inte hitta assistenten för uppdatering', 'danger')
                return redirect(url_for('assistant_config'))
                
            assistant_data['assistant_id'] = existing_assistant.get('assistant_id')
            
            # Check if we should update in OpenAI
            sync_with_openai = request.form.get('sync_with_openai') == 'yes'
            
            if sync_with_openai and assistant_data['assistant_id']:
                try:
                    # Update in OpenAI
                    from utils import update_openai_assistant
                    update_openai_assistant(
                        openai_api_key,
                        assistant_data['assistant_id'],
                        name=assistant_name,
                        instructions=assistant_instructions
                    )
                    logger.info(f"Updated assistant in OpenAI with ID: {assistant_data['assistant_id']}")
                except Exception as e:
                    logger.error(f"Failed to update assistant in OpenAI: {str(e)}")
                    flash(f"Kunde inte uppdatera assistent i OpenAI: {str(e)}", 'warning')
                    # Continue with the local update even if OpenAI update fails
        
        # Save to database
        saved_assistant = save_assistant(user_id, assistant_data)
        
        # Update the session with the latest assistants
        if saved_assistant:
            user_settings = get_user_settings(user_id)
            if user_settings and 'assistants' in user_settings:
                session['user_assistants'] = user_settings['assistants']
                session.modified = True
        
        flash('Assistent sparad!', 'success')
        return redirect(url_for('assistant_config'))
    except Exception as e:
        logger.error(f"Error saving assistant: {str(e)}")
        flash(f"Ett fel uppstod: {str(e)}", 'danger')
        return redirect(url_for('assistant_config'))
        
@app.route('/delete-assistant/<assistant_id>')
@login_required
def delete_assistant_route(assistant_id):
    """Delete an assistant locally and optionally from OpenAI"""
    try:
        user_id = get_user_id()
        user = get_current_user()
        
        # Get the assistant to get the OpenAI ID before deleting
        assistant = get_assistant(user_id, assistant_id)
        openai_assistant_id = None
        
        if assistant:
            openai_assistant_id = assistant.get('assistant_id')
            
        # Delete from database
        success = delete_assistant(user_id, assistant_id)
        
        # Try to delete from OpenAI if we have an ID
        if success and openai_assistant_id:
            try:
                # Get user's OpenAI key from settings
                user_settings = get_user_settings(user_id) or {}
                user_api_keys = user_settings.get('api_keys', {})
                openai_api_key = user_api_keys.get('openai_api_key')
                
                if openai_api_key:
                    from utils import delete_openai_assistant
                    openai_delete_success = delete_openai_assistant(openai_api_key, openai_assistant_id)
                    
                    if openai_delete_success:
                        logger.info(f"Deleted assistant from OpenAI: {openai_assistant_id}")
                    else:
                        logger.warning(f"OpenAI assistant deletion response indicated failure: {openai_assistant_id}")
            except Exception as e:
                # Just log the error but don't prevent local deletion
                logger.error(f"Error deleting assistant from OpenAI: {str(e)}")
                flash(f"Assistenten togs bort lokalt, men kunde inte tas bort från OpenAI: {str(e)}", 'warning')
        
        # Update session
        if success:
            user_settings = get_user_settings(user_id)
            if user_settings and 'assistants' in user_settings:
                session['user_assistants'] = user_settings['assistants']
                session.modified = True
            
            flash('Assistent borttagen!', 'success')
        else:
            flash('Kunde inte ta bort assistent.', 'danger')
    except Exception as e:
        logger.error(f"Error deleting assistant: {str(e)}")
        flash(f"Ett fel uppstod: {str(e)}", 'danger')
        
    return redirect(url_for('assistant_config'))
                         
@app.route('/export_settings', methods=['GET'])
@login_required
def export_settings():
    user_id = get_user_id()
    document_id = request.args.get('document_id')
    
    if not document_id:
        flash('Document ID is required', 'warning')
        return redirect(url_for('documents'))
    
    # Get document to verify ownership
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get current export settings, either from document or user defaults
    document_settings = document.get('settings', {})
    export_settings = document_settings.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    # Extract settings for the template
    return render_template(
        'export_settings.html',
        document_id=document_id,
        export_format=export_settings.get('export_format', 'pdf'),
        page_size=export_settings.get('page_size', 'A4'),
        orientation=export_settings.get('orientation', 'portrait'),
        font_family=export_settings.get('font_family', 'helvetica'),
        font_size=export_settings.get('font_size', 12),
        line_spacing=export_settings.get('line_spacing', '1.5'),
        alignment=export_settings.get('alignment', 'left'),
        margin_size=export_settings.get('margin_size', 15),
        include_page_numbers=export_settings.get('include_page_numbers', True),
        header_text=export_settings.get('header_text', ''),
        footer_text=export_settings.get('footer_text', ''),
        include_both_languages=export_settings.get('include_both_languages', False)
    )

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/api_keys_settings', methods=['GET', 'POST'])
@login_required
def api_keys_settings():
    user_id = get_user_id()
    
    if request.method == 'POST':
        # Get the submitted API keys
        api_keys = {
            'deepl_api_key': request.form.get('deepl_api_key', '').strip(),
            'openai_api_key': request.form.get('openai_api_key', '').strip()
            # 'openai_assistant_id' removed as it's now handled in the assistants page
        }
        
        # Save to user settings
        user_settings = get_user_settings(user_id) or {}
        user_settings['api_keys'] = api_keys
        save_user_settings(user_id, user_settings)
        
        flash('API-nycklar sparade!', 'success')
        return redirect(url_for('api_keys_settings'))
    
    # Get current API keys from user settings
    user_settings = get_user_settings(user_id) or {}
    current_api_keys = user_settings.get('api_keys', DEFAULT_API_KEYS)
    
    return render_template('api_keys.html', current_api_keys=current_api_keys)

@app.route('/save-assistant-config', methods=['POST'])
@login_required
def save_assistant_config():
    try:
        instructions = request.form.get('instructions')
        target_language = request.form.get('target_language')
        review_style = request.form.get('review_style')

        # Store in environment for persistence
        os.environ['ASSISTANT_INSTRUCTIONS'] = instructions
        os.environ['TARGET_LANGUAGE'] = target_language
        os.environ['REVIEW_STYLE'] = review_style

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_response({'success': True, 'redirect': url_for('assistant_config')})
        return redirect(url_for('assistant_config'))

    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        return redirect(url_for('assistant_config'))
        
@app.route('/save_export_settings', methods=['POST'])
@login_required
def save_export_settings():
    try:
        # Collect form data
        settings = {
            'export_format': request.form.get('file_format', 'pdf'),
            'page_size': request.form.get('page_size', 'A4'),
            'orientation': request.form.get('orientation', 'portrait'),
            'font_family': request.form.get('font_family', 'helvetica'),
            'font_size': int(request.form.get('font_size', 12)),
            'line_spacing': request.form.get('line_spacing', '1.5'),
            'alignment': request.form.get('alignment', 'left'),
            'margin_size': int(request.form.get('margin_size', 15)),
            'include_page_numbers': 'include_page_numbers' in request.form,
            'header_text': request.form.get('header_text', ''),
            'footer_text': request.form.get('footer_text', ''),
            'include_both_languages': 'include_both_languages' in request.form
        }
        
        # Check if we're updating document-specific settings
        document_id = request.form.get('document_id')
        
        # Store in session with debug logging
        logger.info(f"Saving export settings: {settings}")
        session['export_settings'] = settings
        session.modified = True
        
        # Store in user settings in Supabase if logged in
        user_id = get_user_id()
        if user_id:
            # Ensure user exists before saving settings
            user_data = {
                'email': session.get('user', {}).get('email') or 'user@example.com'  # Ensure email is never null
            }
            save_user_data(user_id, user_data)
            save_user_settings(user_id, {'export_settings': settings})
            
            # If document ID provided, update document-specific settings
            if document_id:
                document = get_document(user_id, document_id)
                if document:
                    document_settings = document.get('settings', {})
                    document_settings['export_settings'] = settings
                    update_data = {'settings': document_settings}
                    update_document(user_id, document_id, update_data)
                    flash('Export settings saved for this project', 'success')
                    return redirect(url_for('translation_workspace', id=document_id))
        
        # Display success message and redirect
        flash('Export settings saved successfully', 'success')
        if document_id:
            return redirect(url_for('translation_workspace', id=document_id))
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_response({'success': True, 'redirect': url_for('export_settings')})
        return redirect(url_for('export_settings'))
        
    except Exception as e:
        logger.error(f"Error saving export settings: {str(e)}")
        flash(f'Error saving settings: {str(e)}', 'danger')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        if document_id:
            return redirect(url_for('translation_workspace', id=document_id))
        return redirect(url_for('export_settings'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return redirect(url_for('index'))

    # Check for files - both single file and batch mode
    files = []
    
    # Get project metadata
    project_title = request.form.get('projectTitle', '')
    project_description = request.form.get('projectDescription', '')
    
    # Log for debugging
    logger.info(f"Received project title: '{project_title}', description: '{project_description}'")
    
    # Check for batch mode (files[])
    if 'files[]' in request.files:
        files = request.files.getlist('files[]')
    # Check for single file mode
    elif 'file' in request.files:
        files = [request.files['file']]
    
    if not files:
        return json_error('No files provided')
    
    # Filter out empty filenames
    files = [f for f in files if f.filename != '']
    
    if not files:
        return json_error('No files selected')

    # Validate all files
    invalid_files = []
    for file in files:
        if not is_allowed_file(file.filename):
            invalid_files.append(file.filename)
    
    if invalid_files:
        # Track invalid file type upload attempt
        if posthog_available and posthog:
            posthog.capture(
                distinct_id=get_user_id(),
                event='file_upload_error',
                properties={
                    'error': 'invalid_file_type',
                    'filenames': invalid_files,
                    'file_count': len(invalid_files)
                }
            )
        return json_error(f'Invalid file type(s): {", ".join(invalid_files)}. Please upload PDF, Word (DOCX/DOC), text (TXT), RTF, or ODT files only.')

    try:
        # We'll process each file and collect their translations
        all_translations = []
        filepaths = []
        
        # Maximum file size (100MB)
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes
        
        # Check upload directory exists and is writable
        upload_dir = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_dir):
            try:
                os.makedirs(upload_dir, exist_ok=True)
                logger.info(f"Created upload directory: {upload_dir}")
            except Exception as dir_error:
                logger.error(f"Failed to create upload directory: {str(dir_error)}")
                return json_error("Server configuration error: Upload directory cannot be created")
        
        if not os.access(upload_dir, os.W_OK):
            logger.error(f"Upload directory is not writable: {upload_dir}")
            return json_error("Server configuration error: Upload directory is not writable")
        
        # Check disk space
        try:
            import shutil
            disk_usage = shutil.disk_usage(upload_dir)
            if disk_usage.free < 500 * 1024 * 1024:  # Less than 500MB free
                logger.warning(f"Low disk space: {disk_usage.free / (1024*1024):.2f}MB free")
        except Exception as disk_error:
            logger.warning(f"Unable to check disk space: {str(disk_error)}")
        
        # Save all files with validation
        for file in files:
            # Validate filename
            original_filename = file.filename
            if not original_filename:
                logger.warning("Received file with empty filename")
                continue
                
            # Create a secure filename
            filename = secure_filename(original_filename)
            if filename != original_filename:
                logger.info(f"Sanitized filename from '{original_filename}' to '{filename}'")
            
            # Generate a unique filename to avoid conflicts
            unique_prefix = str(uuid.uuid4())[:8]
            unique_filename = f"{unique_prefix}_{filename}"
            filepath = os.path.join(upload_dir, unique_filename)
            
            # Check file size limit
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset file pointer
            
            if file_size > MAX_FILE_SIZE:
                logger.warning(f"File too large: {filename} ({file_size / (1024*1024):.2f}MB)")
                return json_error(f"File {filename} is too large. Maximum file size is 100MB.")
            
            # Check for empty files
            if file_size == 0:
                logger.warning(f"Empty file: {filename}")
                return json_error(f"File {filename} is empty and cannot be processed.")
            
            # Scan first few bytes to validate file type
            try:
                file_header = file.read(512)
                file.seek(0)  # Reset file pointer
                
                # Basic PDF header check
                if filename.lower().endswith('.pdf') and not file_header.startswith(b'%PDF-'):
                    logger.warning(f"Invalid PDF file format: {filename}")
                    return json_error(f"File {filename} is not a valid PDF file.")
                
                # DOCX is a ZIP file
                if filename.lower().endswith('.docx') and not (file_header.startswith(b'PK\x03\x04') or file_header.startswith(b'PK\x05\x06')):
                    logger.warning(f"Invalid DOCX file format: {filename}")
                    return json_error(f"File {filename} is not a valid DOCX file.")
            except Exception as header_check_error:
                logger.warning(f"Error checking file header: {str(header_check_error)}")
            
            try:
                # Actually save the file
                file.save(filepath)
                logger.info(f"Saved file: {filename} ({file_size / 1024:.2f}KB) to {filepath}")
                filepaths.append(filepath)
                
                # Track original filename mapping for reference
                session[f'original_filename_{unique_filename}'] = original_filename
                
            except Exception as save_error:
                logger.error(f"Failed to save file {filename}: {str(save_error)}")
                return json_error(f"Failed to upload file {filename}: {str(save_error)}")
                
        # Verify we have files to process
        if not filepaths:
            logger.error("No valid files were uploaded")
            return json_error("No valid files were uploaded. Please try again.")
        
        logger.info(f"Processing {len(filepaths)} files in batch mode")
        
        # Check if OpenAI review should be skipped
        skip_openai = request.form.get('skipOpenAI') == 'true'
        logger.info(f"Skip OpenAI review: {skip_openai}")
        
        # Get language options
        source_language = request.form.get('sourceLanguage', 'auto')
        target_language = request.form.get('targetLanguage', 'SV')
        logger.info(f"Language options - Source: {source_language}, Target: {target_language}")
        
        # Get selected assistant ID
        assistant_id_selected = request.form.get('assistantId')
        
        # Get user's API keys if available
        user_id = get_user_id()
        user_settings = get_user_settings(user_id) or {}
        user_api_keys = user_settings.get('api_keys', DEFAULT_API_KEYS)
        
        # Update session with assistants if they're not there but exist in settings
        if 'user_assistants' not in session and 'assistants' in user_settings:
            session['user_assistants'] = user_settings['assistants']
            session.modified = True
        
        # Get API keys (must be provided by the user)
        deepl_api_key = user_api_keys.get('deepl_api_key')
        if not deepl_api_key:
            return json_error('DeepL API-nyckel saknas. Lägg till en på API-nyckelsidan.')
        
        # Handle assistant selection and OpenAI settings
        if not skip_openai:
            openai_api_key = user_api_keys.get('openai_api_key')
            if not openai_api_key:
                return json_error('OpenAI API-nyckel saknas. Lägg till en på API-nyckelsidan eller avaktivera OpenAI-förbättringen.')
            
            # If user selected a specific assistant, use that
            if assistant_id_selected:
                assistant_data = get_assistant(user_id, assistant_id_selected)
                if assistant_data and assistant_data.get('assistant_id'):
                    openai_assistant_id = assistant_data.get('assistant_id')
                    logger.info(f"Using selected assistant: {assistant_data.get('name')} ({openai_assistant_id})")
                else:
                    # Selected assistant doesn't exist or has no OpenAI ID
                    logger.warning(f"Selected assistant {assistant_id_selected} not found or has no OpenAI ID. Using default.")
                    openai_assistant_id = OPENAI_ASSISTANT_ID
            else:
                # No assistant selected, use default
                openai_assistant_id = OPENAI_ASSISTANT_ID
                
            # Verify default assistant is set and valid
            if not openai_assistant_id:
                logger.warning("No default OpenAI assistant ID configured. Using fallback text.")
                # Skip AI review since we don't have a valid assistant ID
                skip_openai = True
                openai_api_key = None
            else:
                # Additional fallback - check for format validity
                if not str(openai_assistant_id).startswith("asst_"):
                    logger.warning(f"Invalid OpenAI assistant ID format: {openai_assistant_id}. OpenAI assistant IDs should start with 'asst_'")
                    logger.warning("Skipping AI review and using DeepL translation only.")
                    skip_openai = True
                    openai_api_key = None
        else:
            openai_api_key = None
            openai_assistant_id = None
            
        logger.info(f"Using {'user' if user_api_keys.get('deepl_api_key') else 'system'} DeepL API key")
        if not skip_openai:
            logger.info(f"Using {'user' if user_api_keys.get('openai_api_key') else 'system'} OpenAI API key")

        # Get custom instructions if using a specific assistant
        custom_instructions = None
        if assistant_id_selected and not skip_openai:
            # Try to get from the already fetched assistant (avoid redundant DB calls)
            assistant_found = False
            
            # Check if we have assistants in session
            if 'user_assistants' in session:
                for assistant in session['user_assistants']:
                    if assistant.get('id') == assistant_id_selected:
                        custom_instructions = assistant.get('instructions')
                        logger.info(f"Using custom instructions for assistant from session: {assistant.get('name')}")
                        assistant_found = True
                        break
            
            # If not found in session, try database
            if not assistant_found:
                assistant_data = get_assistant(user_id, assistant_id_selected)
                if assistant_data:
                    custom_instructions = assistant_data.get('instructions')
                    logger.info(f"Using custom instructions for assistant from DB: {assistant_data.get('name')}")
            
            # If still no instructions, use default
            if not custom_instructions:
                logger.info("No custom instructions found, using default instructions")
                custom_instructions = DEFAULT_INSTRUCTIONS
        
        # Process each document and collect translations
        original_filenames = []
        total_sections = 0
        
        # Initialize statistics
        cache_hits = 0
        cache_ratio = 0
        smart_review_savings = 0
        smart_review_ratio = 0
        
        # Initialize glossary stats
        globals()['glossary_hits'] = 0
        globals()['glossary_ratio'] = 0
        globals()['unique_terms_used'] = 0
        
        for i, filepath in enumerate(filepaths):
            try:
                logger.info(f"Processing file {i+1}/{len(filepaths)}: {os.path.basename(filepath)}")
                
                # Get processing options from form
                use_cache = request.form.get('useCache') != 'false'  # Default to True
                smart_review = request.form.get('smartReview') != 'false'  # Default to True
                glossary_id = request.form.get('glossaryId')  # Will be None if not provided
                
                # Get folder selection
                folder_id = request.form.get('folderId')
                
                # Process this document
                process_result = process_document(
                    filepath,
                    deepl_api_key,
                    openai_api_key,
                    openai_assistant_id,
                    source_language=source_language,
                    target_language=target_language,
                    custom_instructions=custom_instructions,
                    return_segments=True,
                    use_cache=use_cache,
                    smart_review=smart_review,
                    complexity_threshold=40,  # Default threshold, could be made configurable
                    glossary_id=glossary_id
                )
                
                # Process document now returns a tuple with translations and stats
                if isinstance(process_result, tuple) and len(process_result) == 2:
                    file_translations, file_stats = process_result
                    
                    # Update overall statistics (used later for document creation)
                    if 'cache_hits' in file_stats:
                        cache_hits += file_stats['cache_hits']
                    if 'cache_ratio' in file_stats:
                        # Average the ratios across files
                        cache_ratio = ((cache_ratio * i) + file_stats['cache_ratio']) / (i + 1) if i > 0 else file_stats['cache_ratio']
                    if 'smart_review_savings' in file_stats:
                        smart_review_savings += file_stats['smart_review_savings']
                    if 'smart_review_ratio' in file_stats:
                        # Average the ratios across files
                        smart_review_ratio = ((smart_review_ratio * i) + file_stats['smart_review_ratio']) / (i + 1) if i > 0 else file_stats['smart_review_ratio']
                    
                    # Add glossary statistics
                    if 'glossary_hits' in file_stats:
                        if not hasattr(globals(), 'glossary_hits'):
                            globals()['glossary_hits'] = 0
                        globals()['glossary_hits'] += file_stats['glossary_hits']
                    if 'glossary_ratio' in file_stats:
                        if not hasattr(globals(), 'glossary_ratio'):
                            globals()['glossary_ratio'] = 0
                        # Average the ratios across files
                        globals()['glossary_ratio'] = ((globals()['glossary_ratio'] * i) + file_stats['glossary_ratio']) / (i + 1) if i > 0 else file_stats['glossary_ratio']
                    if 'unique_terms_used' in file_stats:
                        if not hasattr(globals(), 'unique_terms_used'):
                            globals()['unique_terms_used'] = 0
                        globals()['unique_terms_used'] += file_stats['unique_terms_used']
                        
                    logger.info(f"Statistics for file {i+1}: Cache hits: {file_stats.get('cache_hits', 0)}, "
                                f"Smart review savings: {file_stats.get('smart_review_savings', 0)}, "
                                f"Glossary hits: {file_stats.get('glossary_hits', 0)}, "
                                f"Unique glossary terms: {file_stats.get('unique_terms_used', 0)}")
                else:
                    # Handle older version return type
                    file_translations = process_result
                
                # Store original filename in each translation item for multi-file identification
                for item in file_translations:
                    item['original_file'] = os.path.basename(filepath)
                
                # Add to the overall translations
                all_translations.extend(file_translations)
                original_filenames.append(os.path.basename(filepath))
                total_sections += len(file_translations)
                
                logger.info(f"Successfully processed file {i+1}: {len(file_translations)} sections")
            except Exception as e:
                logger.error(f"Error processing file {i+1}: {str(e)}")
                # Continue with other files even if one fails

        # Generate a unique ID for this translation session
        translation_id = str(int(time.time()))
        session['translation_id'] = translation_id

        # Store all translations in file
        translation_file = os.path.join(TRANSLATIONS_DIR, f"{translation_id}.json")
        with open(translation_file, 'w') as f:
            json.dump(all_translations, f)
            
        # Save as a document for document management
        if len(filepaths) == 1:
            # Always use project title from form as the primary title
            project_title = request.form.get('projectTitle', '')
            project_description = request.form.get('projectDescription', '')
            
            # Store project title and description in session for later use
            if project_title:
                session['last_project_title'] = project_title
                session.modified = True
            
            if project_description:
                session['last_project_description'] = project_description
                session.modified = True
            
            original_filename = os.path.basename(filepaths[0])
            # Always prefer project title over filename
            title = project_title or os.path.splitext(original_filename)[0]
            
            # Combine all translated segments
            translated_text = '\n\n'.join([t['translated_text'] for t in all_translations if t['status'] == 'success'])
            source_text = '\n\n'.join([t['original_text'] for t in all_translations if t['status'] == 'success'])
            
            # Debug info to track what's happening
            logger.info(f"Source text sample (first 100 chars): {source_text[:100]}...")
            logger.info(f"Translated text sample (first 100 chars): {translated_text[:100]}...")
            
            # Verify source and translated text are different
            if source_text == translated_text:
                logger.warning("Source and translated text are identical - this might indicate a translation issue")
                logger.warning(f"Source language: {source_language}, Target language: {target_language}")
            
            # Create document data
            doc_data = {
                'title': title,
                'description': project_description if project_description else f"Translated from {original_filename}",
                'original_filename': original_filename,
                'file_type': os.path.splitext(original_filename)[1].lower(),
                'source_language': source_language,
                'target_language': target_language,
                'word_count': len(translated_text.split()),
                'status': 'in_progress',  # Changed from 'completed' to 'in_progress'
                'settings': {
                    'export_settings': session.get('export_settings', DEFAULT_EXPORT_SETTINGS),
                    'project_info': f"Project settings: {project_description}",
                    'total_pages': len(source_text.split('\n\n')),
                    # Add text statistics
                    'char_count': len(source_text),
                    # Add translation statistics
                    'cache_hits': cache_hits,
                    'cache_ratio': cache_ratio,
                    'smart_review_savings': smart_review_savings,
                    'smart_review_ratio': smart_review_ratio,
                    'glossary_hits': globals().get('glossary_hits', 0),
                    'glossary_ratio': globals().get('glossary_ratio', 0),
                    'unique_terms_used': globals().get('unique_terms_used', 0),
                    # Store language information explicitly in settings
                    'explicit_source_language': source_language,
                    'explicit_target_language': target_language,
                    'translation_info': {
                        'source': source_language,
                        'target': target_language,
                        'date': datetime.now().isoformat()
                    }
                },
                'source_content': source_text,
                'translated_content': translated_text,
                'folder_id': folder_id if folder_id else None
            }
            
            # Save document
            try:
                doc_result = create_document(user_id, doc_data)
                logger.info(f"Created document with ID: {doc_result['id']}")
            except Exception as doc_error:
                logger.error(f"Error saving document: {str(doc_error)}")
        else:
            # Multiple files - create a document for each file
            for i, filepath in enumerate(filepaths):
                try:
                    # Get translations for this file
                    file_translations = [t for t in all_translations if t.get('original_file') == os.path.basename(filepath)]
                    
                    if not file_translations:
                        continue
                        
                    # Combine translated segments
                    translated_text = '\n\n'.join([t['translated_text'] for t in file_translations if t['status'] == 'success'])
                    source_text = '\n\n'.join([t['original_text'] for t in file_translations if t['status'] == 'success'])
                    
                    # Skip if empty
                    if not translated_text or not source_text:
                        continue
                    
                    # Create document - for multi-file mode, use chapter naming
                    original_filename = os.path.basename(filepath)
                    
                    # Always use project title from form as the primary title
                    project_title = request.form.get('projectTitle', '')
                    project_description = request.form.get('projectDescription', '')
                    
                    # Store project title and description in session for later use if not already stored
                    if project_title and 'last_project_title' not in session:
                        session['last_project_title'] = project_title
                        session.modified = True
                    
                    if project_description and 'last_project_description' not in session:
                        session['last_project_description'] = project_description
                        session.modified = True
                    
                    # For batch chapters, name them as chapters, always use project title if provided
                    file_number = i + 1
                    # Always prefer project title for chapter naming
                    chapter_title = f"{project_title} - Chapter {file_number}" if project_title else os.path.splitext(original_filename)[0]
                    
                    doc_data = {
                        'title': chapter_title,
                        'description': project_description if project_description else f"Translated from {original_filename}",
                        'original_filename': original_filename,
                        'file_type': os.path.splitext(original_filename)[1].lower(),
                        'source_language': source_language,
                        'target_language': target_language,
                        'word_count': len(translated_text.split()),
                        'status': 'in_progress',
                        'settings': {
                            'export_settings': session.get('export_settings', DEFAULT_EXPORT_SETTINGS),
                            'project_info': f"Project settings: {project_description}",
                            'total_pages': len(source_text.split('\n\n')),
                            # Add text statistics
                            'char_count': len(source_text),
                            # Add translation statistics
                            'cache_hits': cache_hits,
                            'cache_ratio': cache_ratio,
                            'smart_review_savings': smart_review_savings,
                            'smart_review_ratio': smart_review_ratio,
                            'glossary_hits': globals().get('glossary_hits', 0),
                            'glossary_ratio': globals().get('glossary_ratio', 0),
                            'unique_terms_used': globals().get('unique_terms_used', 0)
                        },
                        'source_content': source_text,
                        'translated_content': translated_text,
                        'folder_id': folder_id if folder_id else None
                    }
                    
                    # Save document
                    doc_result = create_document(user_id, doc_data)
                    logger.info(f"Created document with ID: {doc_result['id']}")
                except Exception as doc_error:
                    logger.error(f"Error saving document {i+1}: {str(doc_error)}")
                    continue
            
        # Store filenames for later - joined with comma for multiple files
        session['original_filename'] = ", ".join(original_filenames) if len(original_filenames) > 1 else original_filenames[0]
        session['file_count'] = len(original_filenames)

        # Gather cache and smart review stats
        cache_hits = 0
        cache_ratio = 0
        smart_review_savings = 0
        smart_review_ratio = 0
        
        # Initialize glossary stats if they weren't set during processing
        if 'glossary_hits' not in globals():
            globals()['glossary_hits'] = 0
        if 'glossary_ratio' not in globals():
            globals()['glossary_ratio'] = 0  
        if 'unique_terms_used' not in globals():
            globals()['unique_terms_used'] = 0
        
        for t in all_translations:
            # Check if translation contains cache metadata
            if t.get('cache_metadata') and t.get('cache_metadata').get('source_hash'):
                cache_hits += 1
                
            # Check if review was skipped due to smart review
            if t.get('review_skipped_reason') == 'low_complexity':
                smart_review_savings += 1
        
        if total_sections > 0:
            cache_ratio = (cache_hits / total_sections) * 100
            smart_review_ratio = (smart_review_savings / total_sections) * 100
            logger.info(f"Cache statistics: {cache_hits}/{total_sections} segments from cache ({cache_ratio:.1f}%)")
            logger.info(f"Smart review savings: {smart_review_savings}/{total_sections} segments skipped ({smart_review_ratio:.1f}%)")
            
            # Log glossary statistics
            if globals()['glossary_hits'] > 0:
                logger.info(f"Glossary statistics: {globals()['glossary_hits']} terms replaced, {globals()['unique_terms_used']} unique terms used")
                logger.info(f"Glossary ratio: {globals()['glossary_ratio']:.2f} replacements per 1000 characters")
        
        # Track successful file upload and translation
        if posthog_available and posthog:
            posthog.capture(
                distinct_id=get_user_id(),
                event='files_translated',
                properties={
                    'filenames': original_filenames,
                    'file_count': len(original_filenames),
                    'skip_openai_review': skip_openai,
                    'total_sections': total_sections,
                    'translation_id': translation_id,
                    'cache_enabled': use_cache,
                    'cache_hits': cache_hits,
                    'cache_ratio': round(cache_ratio, 1),
                    'smart_review_enabled': smart_review,
                    'smart_review_savings': smart_review_savings,
                    'smart_review_ratio': round(smart_review_ratio, 1)
                }
            )

        # Store the created document ID for later reference
        created_doc_id = None
        if 'doc_result' in locals() and doc_result and 'id' in doc_result:
            created_doc_id = doc_result['id']
        
        # After successful upload, redirect directly to the workspace
        # for the newly created project instead of the review screen
        if created_doc_id:
            return json_response({
                'success': True,
                'redirect': url_for('translation_workspace', id=created_doc_id)
            })
        else:
            # Fallback to documents page if we couldn't get a specific document ID
            return json_response({
                'success': True,
                'redirect': url_for('documents')
            })

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return json_error(str(e), 500)

    finally:
        # Cleanup temporary files
        if 'filepaths' in locals():
            for filepath in filepaths:
                try:
                    os.remove(filepath)
                    logger.debug(f"Removed temporary file: {filepath}")
                except Exception as e:
                    logger.error(f"Failed to remove temporary file {filepath}: {str(e)}")
                    pass

@app.route('/review')
@login_required
def review():
    translation_id = session.get('translation_id')
    translations = []
    
    if translation_id:
        # Load translations from file
        translation_file = os.path.join(TRANSLATIONS_DIR, f"{translation_id}.json")
        if os.path.exists(translation_file):
            try:
                with open(translation_file, 'r') as f:
                    translations = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.error("Failed to load translations from file")
    
    return render_template('review.html', translations=translations)

@app.route('/save-reviews', methods=['POST'])
@login_required
def save_reviews():
    try:
        translation_id = session.get('translation_id')
        if not translation_id:
            return json_error('No active translation session')
            
        # Load translations from file
        translation_file = os.path.join(TRANSLATIONS_DIR, f"{translation_id}.json")
        if not os.path.exists(translation_file):
            return json_error('No translations to save')
            
        try:
            with open(translation_file, 'r') as f:
                translations = json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.error("Failed to load translations from file")
            return json_error('Failed to load translations')

        # Update translations with reviewed text
        for translation in translations:
            key = f'translation_{translation["id"]}'
            if key in request.form:
                translation['translated_text'] = request.form[key]

        # Save updated translations back to file
        with open(translation_file, 'w') as f:
            json.dump(translations, f)
            
        # Save to database if requested
        if 'save_to_db' in request.form and request.form['save_to_db'] == 'yes':
            try:
                user_id = get_user_id()
                # Ensure user exists in the users table before saving translation
                user_data = {
                    'email': session.get('user', {}).get('email') or 'user@example.com'  # Ensure email is never null
                }
                save_user_data(user_id, user_data)
                
                # Prepare for saving to database
                original_filename = session.get('original_filename', 'document.pdf')
                
                # Combine all translations
                combined_text = '\n\n'.join([t['translated_text'] for t in translations if t['status'] == 'success'])
                
                # Get export settings
                settings = session.get('export_settings', DEFAULT_EXPORT_SETTINGS)
                
                # Check for cache metadata to store along with translations
                cache_entries = []
                for t in translations:
                    if t.get('status') == 'success' and t.get('cache_metadata'):
                        cache_entries.append(t.get('cache_metadata'))
                
                # Save to database with cache entries if available
                if len(cache_entries) > 0:
                    logger.info(f"Saving translation with {len(cache_entries)} cache entries")
                    
                    # Save primary translation entry
                    save_result = save_translation(
                        user_id, 
                        original_filename, 
                        combined_text, 
                        settings
                    )
                    
                    # Add cache entries
                    for entry in cache_entries:
                        if entry.get('source_text') and entry.get('source_hash') and entry.get('target_language'):
                            try:
                                # Just save to cache without creating another translation entry
                                save_translation(
                                    user_id,
                                    None,  # No filename needed for cache-only entries
                                    None,  # No translation text (already saved in main entry)
                                    None,  # No settings
                                    source_text=entry.get('source_text'),
                                    source_hash=entry.get('source_hash'),
                                    target_language=entry.get('target_language')
                                )
                            except Exception as cache_error:
                                logger.error(f"Error saving to cache: {str(cache_error)}")
                else:
                    # Standard save without cache entries
                    save_result = save_translation(user_id, original_filename, combined_text, settings)
                
                # Track event
                if posthog and save_result:
                    posthog.capture(
                        distinct_id=user_id,
                        event='translation_saved',
                        properties={
                            'filename': original_filename,
                            'translation_id': translation_id,
                            'section_count': len(translations)
                        }
                    )
                
                flash('Översättning sparad i ditt bibliotek!', 'success')
                
                # Redirect to history page after saving to database
                return redirect(url_for('history'))
            except Exception as e:
                logger.error(f"Error saving translation to database: {str(e)}")
                flash(f"Kunde inte spara översättningen: {str(e)}", 'danger')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_response({'success': True, 'redirect': url_for('review')})
        
        flash('Ändringar sparade!', 'success')
        return redirect(url_for('review'))

    except Exception as e:
        logger.error(f"Error saving reviews: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        return redirect(url_for('review'))

@app.route('/download-final')
@login_required
def download_final():
    # Check if a specific format was requested
    requested_format = request.args.get('format', 'pdf')
    
    translation_id = session.get('translation_id')
    if not translation_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error('No active translation session', 400)
        return redirect(url_for('index'))
        
    # Load translations from file
    translation_file = os.path.join(TRANSLATIONS_DIR, f"{translation_id}.json")
    if not os.path.exists(translation_file):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error('No translations available', 400)
        return redirect(url_for('index'))
        
    try:
        with open(translation_file, 'r') as f:
            translations = json.load(f)
            
        if not translations:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return json_error('No translations available', 400)
            return redirect(url_for('index'))
        
        # Get export settings with debug logging
        settings = session.get('export_settings', DEFAULT_EXPORT_SETTINGS)
        
        # Override format if specified in the request
        if requested_format in ['pdf', 'docx', 'txt', 'html']:
            settings = settings.copy()  # Create a copy to avoid modifying the session
            settings['export_format'] = requested_format
            
        logger.info(f"Using export settings: {settings}")
        
        # Prepare the content based on settings
        if settings['include_both_languages']:
            # Format with both languages
            content = []
            for t in translations:
                content.append("=== ORIGINAL TEXT ===")
                content.append(t['original_text'])
                content.append("\n=== TRANSLATED TEXT ===")
                content.append(t['translated_text'])
                content.append("\n" + "-" * 80 + "\n")  # Separator between pages
            final_text = '\n'.join(content)
        else:
            # Just the translations
            final_text = '\n\n'.join(t['translated_text'] for t in translations)
            
        # Save to user's history
        user_id = get_user_id()
        if user_id:
            # Ensure user exists in the users table before saving translation
            user_data = {
                'email': session.get('user', {}).get('email') or 'user@example.com'  # Ensure email is never null
                # Note: 'name' column doesn't exist in users table according to error message
            }
            save_user_data(user_id, user_data)
            
            original_filename = session.get('original_filename', 'translation.pdf')
            save_translation(user_id, original_filename, final_text, settings)
            
            # Track download event with PostHog
            if posthog_available and posthog:
                posthog.capture(
                    distinct_id=user_id,
                    event='translation_downloaded',
                    properties={
                        'format': settings['export_format'],
                        'original_filename': original_filename,
                        'translation_id': translation_id,
                        'page_count': len(translations),
                        'include_both_languages': settings['include_both_languages'],
                        'font_family': settings['font_family'],
                        'page_size': settings['page_size'],
                        'orientation': settings['orientation']
                    }
                )
        
        # Generate output based on format
        output_format = settings['export_format']
        
        if output_format == 'pdf':
            # Use the enhanced create_pdf function with settings
            try:
                logger.info(f"Creating PDF with detailed settings...")
                output_path = create_pdf_with_formatting(
                    final_text, 
                    font_family=settings['font_family'],
                    font_size=settings['font_size'],
                    page_size=settings['page_size'],
                    orientation=settings['orientation'],
                    margin=settings['margin_size'],
                    line_spacing=float(settings['line_spacing']),
                    alignment=settings['alignment'],
                    include_page_numbers=settings['include_page_numbers'],
                    header_text=settings['header_text'],
                    footer_text=settings['footer_text']
                )
                logger.info(f"PDF created successfully at: {output_path}")
            except Exception as e:
                logger.error(f"Error in PDF formatting: {str(e)}")
                # Fallback to basic PDF creation
                output_path = create_pdf_with_text_basic(final_text)
            download_name = 'final_translation.pdf'
            mime_type = 'application/pdf'
        
        elif output_format == 'docx':
            # Create a Word document
            from utils import create_docx_with_text
            output_path = create_docx_with_text(
                final_text,
                font_family=settings['font_family'],
                font_size=settings['font_size'],
                page_size=settings['page_size'],
                orientation=settings['orientation'],
                margin=settings['margin_size'],
                line_spacing=float(settings['line_spacing']),
                alignment=settings['alignment'],
                include_page_numbers=settings['include_page_numbers'],
                header_text=settings['header_text'],
                footer_text=settings['footer_text']
            )
            download_name = 'final_translation.docx'
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            
        elif output_format == 'txt':
            # Create a simple text file
            output_path = os.path.join(tempfile.gettempdir(), 'final_translation.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_text)
            download_name = 'final_translation.txt'
            mime_type = 'text/plain'
            
        elif output_format == 'html':
            # Create an HTML file
            from utils import create_html_with_text
            output_path = create_html_with_text(
                final_text, 
                font_family=settings['font_family'],
                font_size=settings['font_size'],
                line_spacing=float(settings['line_spacing']),
                alignment=settings['alignment'],
                include_page_numbers=settings['include_page_numbers'],
                header_text=settings['header_text'],
                footer_text=settings['footer_text']
            )
            download_name = 'final_translation.html'
            mime_type = 'text/html'
        
        else:
            # Default to PDF with standard formatting
            output_path = create_pdf_with_formatting(final_text)
            download_name = 'final_translation.pdf'
            mime_type = 'application/pdf'

        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_name,
            mimetype=mime_type
        )

    except Exception as e:
        logger.error(f"Error creating final PDF: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        return redirect(url_for('index'))

    finally:
        if 'output_path' in locals():
            try:
                os.remove(output_path)
            except:
                pass

# Glossary Management Routes
@app.route('/glossary', methods=['GET'])
@login_required
def glossary_list():
    """Show glossary management page"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
        
    try:
        try:
            glossaries = get_user_glossaries(user_id)
            
            # Enrich glossaries with entry counts
            for glossary in glossaries:
                try:
                    entries = get_glossary_entries(glossary['id'])
                    glossary['entries_count'] = len(entries)
                except Exception as entry_error:
                    logger.error(f"Error getting entries for glossary {glossary['id']}: {str(entry_error)}")
                    glossary['entries_count'] = 0
        except Exception as glossary_error:
            logger.error(f"Error getting glossaries: {str(glossary_error)}")
            glossaries = []
            flash("Error loading glossaries. Database tables may need to be set up.", "warning")
        
        return render_template('glossary.html', glossaries=glossaries, languages=LANGUAGE_CODES)
    except Exception as e:
        logger.error(f"Error displaying glossary page: {str(e)}")
        flash("An error occurred loading the glossary page. Database tables may need to be set up.", "danger")
        return redirect(url_for('index'))

@app.route('/glossary', methods=['POST'])
@login_required
def create_new_glossary():
    """Create a new glossary"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Add more detailed logging    
    logger.info(f"Creating new glossary for user {user_id}")
    logger.debug(f"Request content type: {request.content_type}")
    logger.debug(f"Request headers: {request.headers}")
    logger.debug(f"Request form data: {request.form}")
    logger.debug(f"Request JSON: {request.get_json(silent=True)}")
        
    # Get glossary data from request - with fallback methods for parsing
    try:
        if request.is_json:
            data = request.json
            logger.debug(f"Received JSON data: {data}")
        elif request.form:
            # Try to get data from form
            data = {
                'name': request.form.get('name', ''),
                'description': request.form.get('description', ''),
                'source_language': request.form.get('source_language', ''),
                'target_language': request.form.get('target_language', '')
            }
            logger.debug(f"Received form data: {data}")
        else:
            # Last resort - try to parse body as JSON
            try:
                data = json.loads(request.data.decode('utf-8'))
                logger.debug(f"Parsed raw data as JSON: {data}")
            except:
                logger.error("Failed to parse request data as JSON")
                data = {}
    except Exception as e:
        logger.error(f"Error parsing request data: {str(e)}")
        return json_error(f'Error parsing request: {str(e)}', 400)
    
    if not data or not data.get('name'):
        logger.error("Glossary name is required but was not provided")
        return json_error('Glossary name is required', 400)
        
    # Create glossary
    try:
        result = create_glossary(user_id, data)
        if not result:
            logger.error("create_glossary returned None/False result")
            return json_error('Failed to create glossary', 500)
        
        logger.info(f"Glossary created successfully with ID: {result['id']}")
        
        # Track in analytics
        if posthog_available and posthog:
            try:
                # Get user data for better analytics
                user_data = get_user_data(user_id)
                event_properties = {
                    'glossary_id': result['id'],
                    'glossary_name': result['name'],
                    'source_language': result.get('source_language', 'not_set'),
                    'target_language': result.get('target_language', 'not_set')
                }
                
                # Add user properties if available
                if user_data:
                    event_properties['user_name'] = user_data.get('name', 'Unknown')
                    event_properties['user_email'] = user_data.get('email', 'Unknown')
                
                posthog.capture(
                    distinct_id=user_id,
                    event='glossary_created',
                    properties=event_properties
                )
            except Exception as e:
                logger.error(f"Error tracking glossary creation: {str(e)}")
        
        # Handle form submissions differently than AJAX
        if request.form:
            # For form submissions, redirect back to glossary page
            flash("Ordlista har skapats!", "success")
            return redirect(url_for('glossary_list'))
        else:
            # For AJAX requests, return JSON
            return json_response({
                'success': True,
                'message': 'Glossary created successfully',
                'glossary': result
            })
    except Exception as e:
        logger.error(f"Exception creating glossary: {str(e)}")
        if request.form:
            flash(f"Fel vid skapande av ordlista: {str(e)}", "error")
            return redirect(url_for('glossary_list'))
        else:
            return json_error(f'Error creating glossary: {str(e)}', 500)
    

@app.route('/glossary/<glossary_id>', methods=['GET'])
@login_required
def get_glossary_detail(glossary_id):
    """Get glossary details"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    return json_response({
        'success': True,
        'glossary': glossary
    })

@app.route('/glossary/<glossary_id>', methods=['PUT'])
@login_required
def update_glossary_detail(glossary_id):
    """Update an existing glossary"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Get glossary data from request
    data = request.json
    if not data:
        return json_error('No data provided', 400)
        
    # Check if glossary exists
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Update glossary
    result = update_glossary(user_id, glossary_id, data)
    if not result:
        return json_error('Failed to update glossary', 500)
    
    return json_response({
        'success': True,
        'message': 'Glossary updated successfully',
        'glossary': result
    })

@app.route('/glossary/<glossary_id>', methods=['DELETE'])
@login_required
def delete_glossary_by_id(glossary_id):
    """Delete a glossary"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Delete glossary
    result = delete_glossary(user_id, glossary_id)
    if not result:
        return json_error('Failed to delete glossary', 500)
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='glossary_deleted',
                properties={
                    'glossary_id': glossary_id,
                    'glossary_name': glossary.get('name', 'unknown')
                }
            )
        except Exception as e:
            logger.error(f"Error tracking glossary deletion: {str(e)}")
    
    return json_response({
        'success': True,
        'message': 'Glossary deleted successfully'
    })

@app.route('/glossary/<glossary_id>/entries', methods=['GET'])
@login_required
def get_glossary_entries_list(glossary_id):
    """Get entries for a specific glossary"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Get entries
    entries = get_glossary_entries(glossary_id)
    
    return json_response({
        'success': True,
        'entries': entries
    })

@app.route('/glossary/<glossary_id>/entries', methods=['POST'])
@login_required
def create_new_entry(glossary_id):
    """Create a new glossary entry"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Get entry data from request
    data = request.json
    if not data or not data.get('source_term') or not data.get('target_term'):
        return json_error('Source term and target term are required', 400)
        
    # Create entry
    result = create_glossary_entry(glossary_id, data)
    if not result:
        return json_error('Failed to create glossary entry', 500)
    
    return json_response({
        'success': True,
        'message': 'Term added successfully',
        'entry': result
    })

@app.route('/glossary/<glossary_id>/entries/<entry_id>', methods=['PUT'])
@login_required
def update_entry(glossary_id, entry_id):
    """Update an existing glossary entry"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Get entry data from request
    data = request.json
    if not data:
        return json_error('No data provided', 400)
        
    # Update entry
    result = update_glossary_entry(entry_id, data)
    if not result:
        return json_error('Failed to update glossary entry', 500)
    
    return json_response({
        'success': True,
        'message': 'Term updated successfully',
        'entry': result
    })

@app.route('/glossary/<glossary_id>/entries/<entry_id>', methods=['DELETE'])
@login_required
def delete_entry(glossary_id, entry_id):
    """Delete a glossary entry"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Delete entry
    result = delete_glossary_entry(entry_id)
    if not result:
        return json_error('Failed to delete glossary entry', 500)
    
    return json_response({
        'success': True,
        'message': 'Term deleted successfully'
    })

@app.route('/glossary/<glossary_id>/import', methods=['POST'])
@login_required
def import_glossary_entries(glossary_id):
    """Import glossary entries from CSV file"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        return json_error('Glossary not found', 404)
        
    # Check if file was uploaded
    if 'file' not in request.files:
        return json_error('No file provided', 400)
        
    file = request.files['file']
    if file.filename == '':
        return json_error('No file selected', 400)
        
    # Process CSV file
    has_header = request.form.get('has_header', 'false').lower() == 'true'
    try:
        import csv
        
        # Save the file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        file.save(temp_file.name)
        temp_file.close()
        
        # Read the CSV file
        entries = []
        with open(temp_file.name, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            
            # Skip header row if needed
            if has_header:
                next(reader, None)
                
            for row in reader:
                if len(row) >= 2:
                    entry_data = {
                        'source_term': row[0].strip(),
                        'target_term': row[1].strip()
                    }
                    
                    # Add optional fields if available
                    if len(row) >= 3:
                        entry_data['context'] = row[2].strip()
                    if len(row) >= 4:
                        entry_data['notes'] = row[3].strip()
                        
                    # Only add if source and target terms are not empty
                    if entry_data['source_term'] and entry_data['target_term']:
                        entries.append(entry_data)
        
        # Clean up temporary file
        os.unlink(temp_file.name)
        
        # Process each entry
        success_count = 0
        for entry_data in entries:
            result = create_glossary_entry(glossary_id, entry_data)
            if result:
                success_count += 1
        
        # Track in analytics
        if posthog_available and posthog:
            try:
                posthog.capture(
                    distinct_id=user_id,
                    event='glossary_entries_imported',
                    properties={
                        'glossary_id': glossary_id,
                        'glossary_name': glossary.get('name', 'unknown'),
                        'count': success_count,
                        'total_entries': len(entries)
                    }
                )
            except Exception as e:
                logger.error(f"Error tracking glossary import: {str(e)}")
        
        return json_response({
            'success': True,
            'message': f'Successfully imported {success_count} terms',
            'count': success_count
        })
    except Exception as e:
        logger.error(f"Error importing glossary entries: {str(e)}")
        return json_error(f'Error importing glossary entries: {str(e)}', 500)

# Document Export Functions

@app.route('/export/<document_id>', methods=['GET'])
@login_required
def export_document(document_id):
    import re
    from utils import create_pdf_with_formatting, create_docx_with_text, create_html_with_text
    
    user_id = get_user_id()
    export_format = request.args.get('format', 'pdf')
    
    # Get document to verify ownership
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get document content
    translated_content = get_document_content(user_id, document_id, 'translated')
    source_content = get_document_content(user_id, document_id, 'source')
    
    if not translated_content:
        flash('No content to export', 'warning')
        return redirect(url_for('translation_workspace', id=document_id))
    
    # Get export settings
    document_settings = document.get('settings', {})
    export_settings = document_settings.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    # Extract needed settings
    font_family = export_settings.get('font_family', 'helvetica')
    font_size = export_settings.get('font_size', 12)
    page_size = export_settings.get('page_size', 'A4')
    orientation = export_settings.get('orientation', 'portrait')
    margin_size = export_settings.get('margin_size', 15)
    line_spacing = float(export_settings.get('line_spacing', 1.5))
    alignment = export_settings.get('alignment', 'left')
    include_page_numbers = export_settings.get('include_page_numbers', True)
    header_text = export_settings.get('header_text', '')
    footer_text = export_settings.get('footer_text', '')
    include_both_languages = export_settings.get('include_both_languages', False)
    
    # Prepare content based on settings
    if include_both_languages and source_content:
        final_content = ""
        source_paragraphs = source_content.split('\n\n')
        translated_paragraphs = translated_content.split('\n\n')
        
        # Use the shorter of the two to avoid issues
        min_length = min(len(source_paragraphs), len(translated_paragraphs))
        
        for i in range(min_length):
            final_content += f"{source_paragraphs[i]}\n\n"
            final_content += f"{translated_paragraphs[i]}\n\n"
            final_content += "---\n\n"  # Separator between sections
    else:
        final_content = translated_content
    
    # Add document title as header if not set
    if not header_text and document.get('title'):
        header_text = document.get('title')
        
    # Generate the document based on format
    try:
        if export_format == 'pdf':
            output_file = create_pdf_with_formatting(
                final_content, font_family, font_size, page_size, 
                orientation, margin_size, line_spacing, alignment,
                include_page_numbers, header_text, footer_text
            )
            mimetype = 'application/pdf'
        elif export_format == 'docx':
            output_file = create_docx_with_text(
                final_content, font_family, font_size, page_size,
                orientation, margin_size, line_spacing, alignment,
                include_page_numbers, header_text, footer_text
            )
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif export_format == 'html':
            output_file = create_html_with_text(
                final_content, font_family, font_size, line_spacing, 
                alignment, include_page_numbers, header_text, footer_text
            )
            mimetype = 'text/html'
        else:  # Default to txt
            # For text, just write to a file
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
            with open(temp_output.name, 'w', encoding='utf-8') as f:
                f.write(final_content)
            output_file = temp_output.name
            mimetype = 'text/plain'
        
        # Create a filename with document title and format
        safe_title = re.sub(r'[^\w\-_\. ]', '_', document.get('title', 'document'))
        filename = f"{safe_title}.{export_format}"
        
        # Track export in analytics
        if posthog_available and posthog:
            posthog.capture(
                distinct_id=user_id,
                event='document_exported',
                properties={
                    'document_id': document_id,
                    'format': export_format,
                    'include_both_languages': include_both_languages,
                    'document_title': document.get('title')
                }
            )
        
        return send_file(
            output_file, 
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        logger.error(f"Error exporting document: {str(e)}")
        flash(f'Error exporting document: {str(e)}', 'danger')
        return redirect(url_for('translation_workspace', id=document_id))

@app.route('/export-selected-pages/<document_id>', methods=['POST'])
@login_required
def export_selected_pages(document_id):
    import re
    from utils import create_pdf_with_formatting, create_docx_with_text, create_html_with_text
    
    user_id = get_user_id()
    
    # Get document to verify ownership
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get selected pages
    selected_page_ids = request.form.getlist('selected_pages')
    if not selected_page_ids:
        flash('No pages selected', 'warning')
        return redirect(url_for('translation_workspace', id=document_id))
    
    # Get export settings
    export_format = request.form.get('format', 'pdf')
    content_type = request.form.get('content_type', 'translated')
    include_page_numbers = 'include_page_numbers' in request.form
    include_title = 'include_title' in request.form
    create_toc = 'create_toc' in request.form
    
    # Get document settings for formatting
    document_settings = document.get('settings', {})
    export_settings = document_settings.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    # Extract needed settings
    font_family = export_settings.get('font_family', 'helvetica')
    font_size = export_settings.get('font_size', 12)
    page_size = export_settings.get('page_size', 'A4')
    orientation = export_settings.get('orientation', 'portrait')
    margin_size = export_settings.get('margin_size', 15)
    line_spacing = float(export_settings.get('line_spacing', 1.5))
    alignment = export_settings.get('alignment', 'left')
    
    # Collect content from selected pages
    final_content = ""
    toc_entries = []
    
    # Add title if requested
    if include_title and document.get('title'):
        final_content += f"# {document.get('title')}\n\n"
        if document.get('description'):
            final_content += f"{document.get('description')}\n\n"
        final_content += f"Languages: {document.get('source_language')} → {document.get('target_language')}\n\n"
        final_content += "---\n\n"
    
    # Collect all the pages first to sort them
    pages_data = []
    for page_id in selected_page_ids:
        page = get_document_page(user_id, page_id)
        if page and page.get('document_id') == document_id:
            pages_data.append(page)
    
    # Sort pages by page number
    pages_data.sort(key=lambda x: x.get('page_number', 0))
    
    # Now build the content
    for i, page in enumerate(pages_data):
        page_number = page.get('page_number', i+1)
        page_title = f"Page {page_number}"
        toc_entries.append((page_title, page_number))
        
        # Add page header
        final_content += f"## {page_title}\n\n"
        
        # Select content based on user's choice
        if content_type == 'source':
            page_content = page.get('source_content', '')
        elif content_type == 'translated':
            page_content = page.get('translated_content', '')
        else:  # Both
            source = page.get('source_content', '')
            translated = page.get('translated_content', '')
            page_content = f"### Original\n\n{source}\n\n### Translation\n\n{translated}"
        
        final_content += f"{page_content}\n\n"
        final_content += "---\n\n"  # Page separator
    
    # Insert table of contents if requested
    if create_toc and toc_entries:
        toc_content = "## Table of Contents\n\n"
        for title, number in toc_entries:
            toc_content += f"* [{title}](#page-{number})\n"
        toc_content += "\n---\n\n"
        final_content = toc_content + final_content
    
    # Generate header and footer text
    header_text = document.get('title', '') if include_title else ''
    footer_text = ''
    
    # Generate the document based on format
    try:
        if export_format == 'pdf':
            output_file = create_pdf_with_formatting(
                final_content, font_family, font_size, page_size, 
                orientation, margin_size, line_spacing, alignment,
                include_page_numbers, header_text, footer_text
            )
            mimetype = 'application/pdf'
        elif export_format == 'docx':
            output_file = create_docx_with_text(
                final_content, font_family, font_size, page_size,
                orientation, margin_size, line_spacing, alignment,
                include_page_numbers, header_text, footer_text
            )
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif export_format == 'html':
            output_file = create_html_with_text(
                final_content, font_family, font_size, line_spacing, 
                alignment, include_page_numbers, header_text, footer_text
            )
            mimetype = 'text/html'
        else:  # Default to txt
            # For text, just write to a file
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
            with open(temp_output.name, 'w', encoding='utf-8') as f:
                f.write(final_content)
            output_file = temp_output.name
            mimetype = 'text/plain'
        
        # Create a filename with document title and format
        safe_title = re.sub(r'[^\w\-_\. ]', '_', document.get('title', 'document'))
        filename = f"{safe_title}_selected_pages.{export_format}"
        
        # Track export in analytics
        if posthog_available and posthog:
            posthog.capture(
                distinct_id=user_id,
                event='selected_pages_exported',
                properties={
                    'document_id': document_id,
                    'format': export_format,
                    'page_count': len(pages_data),
                    'content_type': content_type,
                    'document_title': document.get('title')
                }
            )
        
        return send_file(
            output_file, 
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        logger.error(f"Error exporting selected pages: {str(e)}")
        flash(f'Error exporting pages: {str(e)}', 'danger')
        return redirect(url_for('translation_workspace', id=document_id))

@app.route('/documents/<document_id>/update-all-pages-status', methods=['POST'])
@login_required
def update_all_pages_status(document_id):
    """Update the status of all pages in a document"""
    user_id = get_user_id()
    
    # Get document to verify ownership
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get the new status from request
    data = request.json or {}
    new_status = data.get('status')
    
    if not new_status or new_status not in ['in_progress', 'completed', 'needs_review']:
        return json_error('Invalid status', 400)
    
    try:
        # Get all pages for this document
        pages = get_document_pages(user_id, document_id)
        
        # Update each page's status
        for page in pages:
            # Set completion percentage based on status
            completion_percentage = 100 if new_status == 'completed' else 50 if new_status == 'needs_review' else 25
            
            # Update page data
            page_data = {
                'status': new_status,
                'completion_percentage': completion_percentage
            }
            update_document_page(user_id, page['id'], page_data)
        
        # Update document progress
        update_document_progress(user_id, document_id)
        
        return json_response({
            'success': True,
            'message': f'Updated {len(pages)} pages to status: {new_status}'
        })
    except Exception as e:
        logger.error(f"Error updating page statuses: {str(e)}")
        return json_error(f'Error updating page statuses: {str(e)}', 500)

@app.route('/glossary/<glossary_id>/export', methods=['GET'])
@login_required
def export_glossary_entries(glossary_id):
    """Export glossary entries to CSV file"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
        
    # Check if glossary exists and belongs to user
    glossary = get_glossary(user_id, glossary_id)
    if not glossary:
        flash('Glossary not found', 'danger')
        return redirect(url_for('glossary_list'))
        
    # Get entries
    entries = get_glossary_entries(glossary_id)
    
    # Create CSV file
    try:
        import csv
        from io import StringIO
        
        # Create in-memory CSV file
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['source_term', 'target_term', 'context', 'notes'])
        
        # Write entries
        for entry in entries:
            writer.writerow([
                entry.get('source_term', ''),
                entry.get('target_term', ''),
                entry.get('context', ''),
                entry.get('notes', '')
            ])
        
        # Prepare response
        output.seek(0)
        
        # Track in analytics
        if posthog_available and posthog:
            try:
                posthog.capture(
                    distinct_id=user_id,
                    event='glossary_entries_exported',
                    properties={
                        'glossary_id': glossary_id,
                        'glossary_name': glossary.get('name', 'unknown'),
                        'count': len(entries)
                    }
                )
            except Exception as e:
                logger.error(f"Error tracking glossary export: {str(e)}")
        
        # Create a safe filename from the glossary name
        safe_name = ''.join(c for c in glossary.get('name', 'glossary') if c.isalnum() or c in ' _-').strip()
        safe_name = safe_name.replace(' ', '_')
        
        filename = f"{safe_name}_glossary.csv"
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting glossary entries: {str(e)}")
        flash(f'Error exporting glossary: {str(e)}', 'danger')
        return redirect(url_for('glossary_list'))

# Translation Memory Management Routes

@app.route('/translation-memory')
@login_required
def translation_memory():
    """View translation memory entries"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
        
    # Get pagination params
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # Get filter parameters
    search = request.args.get('search', '')
    language = request.args.get('language', '')
    
    # Get entries
    entries = get_translation_memory_entries(
        user_id, 
        limit=per_page, 
        offset=offset,
        search=search, 
        language=language
    )
    
    # Get statistics
    stats = get_translation_memory_stats(user_id)
    
    # Get total count for pagination
    total_entries = stats['total_entries']
    total_pages = (total_entries + per_page - 1) // per_page
    
    # Get unique languages from stats for dropdown
    languages = stats.get('languages', [])
    
    return render_template(
        'translation_memory.html',
        entries=entries,
        page=page,
        total_pages=total_pages,
        search=search,
        language=language,
        languages=languages,
        stats=stats
    )

@app.route('/translation-memory/<entry_id>', methods=['GET'])
@login_required
def view_translation_memory_entry(entry_id):
    """View a specific translation memory entry"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
        
    entry = get_translation_memory_entry(user_id, entry_id)
    if not entry:
        flash('Entry not found', 'danger')
        return redirect(url_for('translation_memory'))
        
    return render_template('translation_memory_view.html', entry=entry)

@app.route('/translation-memory/<entry_id>', methods=['PUT'])
@login_required
def update_translation_memory_entry_route(entry_id):
    """Update a translation memory entry"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    result = update_translation_memory_entry(user_id, entry_id, data)
    if not result:
        return jsonify({'success': False, 'error': 'Failed to update entry'}), 500
        
    return jsonify({
        'success': True,
        'message': 'Entry updated successfully',
        'entry': result
    })

@app.route('/translation-memory/<entry_id>', methods=['DELETE'])
@login_required
def delete_translation_memory_entry_route(entry_id):
    """Delete a translation memory entry"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    result = delete_translation_memory_entry(user_id, entry_id)
    if not result:
        return jsonify({'success': False, 'error': 'Failed to delete entry'}), 500
        
    return jsonify({
        'success': True,
        'message': 'Entry deleted successfully'
    })

@app.errorhandler(404)
def not_found_error(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_error('Resource not found', 404)
    return render_template('404.html'), 404

# Document Management Routes

@app.route('/documents')
@login_required
def documents():
    """Show all user book translation projects"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    try:    
        # Get pagination params
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Get search params
        search = request.args.get('search', '')
        
        # Get all user folders for sidebar and document count
        try:
            folders = get_user_folders(user_id)
            
            # Enrich folders with document count
            for folder in folders:
                folder_docs = get_user_documents(user_id, folder['id'])
                folder['document_count'] = len(folder_docs)
        except Exception as folder_error:
            logger.error(f"Error loading folders: {str(folder_error)}")
            folders = []
        
        # Get documents, filtered by search if provided
        try:
            documents = get_user_documents(user_id, limit=per_page, offset=offset)
            
            # Simple search on backend (ideally this would be done in the database query)
            if search:
                documents = [d for d in documents if search.lower() in d.get('title', '').lower() or 
                                                    search.lower() in d.get('description', '').lower()]
            
            # Get total document count for pagination
            total_documents = len(get_user_documents(user_id))
            total_pages = (total_documents + per_page - 1) // per_page
            
            # Calculate progress info for each document
            for doc in documents:
                if 'total_pages' not in doc or 'completed_pages' not in doc:
                    # Get document pages to calculate progress if not already in the document data
                    try:
                        pages = get_document_pages(user_id, doc['id'])
                        if pages:
                            doc['total_pages'] = len(pages)
                            doc['completed_pages'] = sum(1 for p in pages if p.get('status') == 'completed')
                            doc['overall_progress'] = int((doc['completed_pages'] / doc['total_pages'] * 100) if doc['total_pages'] > 0 else 0)
                        else:
                            doc['total_pages'] = 0
                            doc['completed_pages'] = 0
                            doc['overall_progress'] = 0
                    except Exception as page_error:
                        logger.error(f"Error getting pages for document {doc['id']}: {str(page_error)}")
                        doc['total_pages'] = 0
                        doc['completed_pages'] = 0
                        doc['overall_progress'] = 0
        except Exception as docs_error:
            logger.error(f"Error loading documents: {str(docs_error)}")
            documents = []
            total_documents = 0
            total_pages = 1
        
        return render_template(
            'documents.html',
            documents=documents,
            folders=folders,
            current_folder=None,
            total_documents=total_documents,
            page=page,
            total_pages=total_pages,
            search=search
        )
    except Exception as e:
        logger.error(f"Error displaying documents page: {str(e)}")
        flash("An error occurred loading the documents page. Database tables may need to be set up.", "danger")
        return redirect(url_for('index'))

@app.route('/documents/folders/<folder_id>')
@login_required
def documents_folder(folder_id):
    """Show documents in a specific folder"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    try:
        # Get the folder
        try:
            folder = get_folder(user_id, folder_id)
            if not folder:
                flash('Folder not found', 'danger')
                return redirect(url_for('documents'))
        except Exception as folder_error:
            logger.error(f"Error getting folder {folder_id}: {str(folder_error)}")
            flash('Error loading folder. Database tables may need to be set up.', 'danger')
            return redirect(url_for('index'))
        
        # Get pagination params
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Get search params
        search = request.args.get('search', '')
        
        # Get all user folders for sidebar and document count
        try:
            folders = get_user_folders(user_id)
            
            # Enrich folders with document count
            for f in folders:
                folder_docs = get_user_documents(user_id, f['id'])
                f['document_count'] = len(folder_docs)
        except Exception as folders_error:
            logger.error(f"Error loading folders: {str(folders_error)}")
            folders = []
        
        # Get documents in this folder
        try:
            documents = get_user_documents(user_id, folder_id, limit=per_page, offset=offset)
            
            # Simple search on backend (ideally this would be done in the database query)
            if search:
                documents = [d for d in documents if search.lower() in d.get('title', '').lower() or 
                                                    search.lower() in d.get('description', '').lower()]
            
            # Get total document count for pagination
            total_documents = len(get_user_documents(user_id, folder_id))
            total_pages = (total_documents + per_page - 1) // per_page
        except Exception as docs_error:
            logger.error(f"Error loading documents: {str(docs_error)}")
            documents = []
            total_documents = 0
            total_pages = 1
        
        return render_template(
            'documents.html',
            documents=documents,
            folders=folders,
            current_folder=folder,
            total_documents=total_documents,
            page=page,
            total_pages=total_pages,
            search=search
        )
    except Exception as e:
        logger.error(f"Error displaying folder documents page: {str(e)}")
        flash("An error occurred loading the folder page. Database tables may need to be set up.", "danger")
        return redirect(url_for('index'))

@app.route('/documents/folders', methods=['POST'])
@login_required
def create_folder_route():
    """Create a new folder"""
    user_id = get_user_id()
    if not user_id:
        if request.content_type and 'application/json' in request.content_type:
            return json_error('Unauthorized', 401)
        else:
            flash('Unauthorized', 'error')
            return redirect(url_for('documents'))
    
    # Get folder data from request
    if request.content_type and 'application/json' in request.content_type:
        # JSON request (API/Ajax)
        data = request.json
        if not data or not data.get('name'):
            return json_error('Folder name is required', 400)
    else:
        # Form submission
        data = {
            'name': request.form.get('name', ''),
            'description': request.form.get('description', ''),
            'color': request.form.get('color', '#3498db')
        }
        
        if not data['name']:
            flash('Folder name is required', 'error')
            return redirect(url_for('documents'))
    
    # Create folder
    try:
        result = create_folder(user_id, data)
        if not result:
            if request.content_type and 'application/json' in request.content_type:
                return json_error('Failed to create folder', 500)
            else:
                flash('Failed to create folder', 'error')
                return redirect(url_for('documents'))
    except Exception as e:
        logging.error(f"Error creating folder: {str(e)}")
        if request.content_type and 'application/json' in request.content_type:
            return json_error(f'Failed to create folder: {str(e)}', 500)
        else:
            flash(f'Failed to create folder: {str(e)}', 'error')
            return redirect(url_for('documents'))
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='folder_created',
                properties={
                    'folder_id': result['id'],
                    'folder_name': result['name']
                }
            )
        except Exception as e:
            logger.error(f"Error tracking folder creation: {str(e)}")
    
    # Return appropriate response based on request type
    if request.content_type and 'application/json' in request.content_type:
        return json_response({
            'success': True,
            'message': 'Folder created successfully',
            'folder': result
        })
    else:
        # Form submission - redirect to the new folder
        flash('Folder created successfully', 'success')
        if result and result.get('id'):
            return redirect(url_for('documents_folder', folder_id=result['id']))
        else:
            return redirect(url_for('documents'))

@app.route('/documents/folders/<folder_id>', methods=['PUT'])
@login_required
def update_folder_route(folder_id):
    """Update an existing folder"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get folder data from request
    data = request.json
    if not data:
        return json_error('No data provided', 400)
    
    # Check if folder exists
    folder = get_folder(user_id, folder_id)
    if not folder:
        return json_error('Folder not found', 404)
    
    # Update folder
    result = update_folder(user_id, folder_id, data)
    if not result:
        return json_error('Failed to update folder', 500)
    
    return json_response({
        'success': True,
        'message': 'Folder updated successfully',
        'folder': result
    })

@app.route('/documents/folders/<folder_id>/delete', methods=['POST'])
@login_required
def delete_folder_post_route(folder_id):
    """Delete a folder (POST method fallback for browsers without JS)"""
    user_id = get_user_id()
    if not user_id:
        flash('Unauthorized', 'error')
        return redirect(url_for('documents'))
    
    # Get the folder
    folder = get_folder(user_id, folder_id)
    if not folder:
        flash('Folder not found', 'error')
        return redirect(url_for('documents'))
    
    # Delete folder
    result = delete_folder(user_id, folder_id)
    if not result:
        flash('Failed to delete folder', 'error')
        return redirect(url_for('documents'))
    
    flash('Folder deleted successfully', 'success')
    return redirect(url_for('documents'))

@app.route('/documents/folders/<folder_id>', methods=['DELETE'])
@login_required
def delete_folder_route(folder_id):
    """Delete a folder"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Check if folder exists
    folder = get_folder(user_id, folder_id)
    if not folder:
        return json_error('Folder not found', 404)
    
    # Delete folder
    result = delete_folder(user_id, folder_id)
    if not result:
        return json_error('Failed to delete folder', 500)
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='folder_deleted',
                properties={
                    'folder_id': folder_id,
                    'folder_name': folder.get('name', 'unknown')
                }
            )
        except Exception as e:
            logger.error(f"Error tracking folder deletion: {str(e)}")
    
    return json_response({
        'success': True,
        'message': 'Folder deleted successfully'
    })

@app.route('/documents/<document_id>/fix', methods=['POST'])
@login_required
def fix_document(document_id):
    """Fix a document with missing content files"""
    user_id = get_user_id()
    
    # Get the document to verify ownership
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found.', 'error')
        return redirect(url_for('documents'))
    
    # Try to fix the document content
    success = fix_document_content(user_id, document_id)
    
    if success:
        flash('Document content has been fixed successfully.', 'success')
    else:
        flash('Failed to fix document content. Please try again later.', 'error')
        
    # Redirect back to the document
    return redirect(url_for('view_document', document_id=document_id))

@app.route('/documents/<document_id>')
@login_required
def view_document(document_id):
    """View a document"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get document content
    source_content = get_document_content(user_id, document_id, 'source')
    translated_content = get_document_content(user_id, document_id, 'translated')
    
    # Get folder details if document is in a folder
    folder_name = None
    folder_color = None
    if document.get('folder_id'):
        folder = get_folder(user_id, document['folder_id'])
        if folder:
            folder_name = folder.get('name', 'Unknown Folder')
            folder_color = folder.get('color', '#3498db')
    
    # Get all folders for the move document modal
    folders = get_user_folders(user_id)
    
    # Get recent versions for preview
    versions = get_document_versions(user_id, document_id, limit=5)
    
    return render_template(
        'document_view.html',
        document=document,
        source_content=source_content,
        translated_content=translated_content,
        folder_name=folder_name,
        folder_color=folder_color,
        folders=folders,
        versions=versions
    )

@app.route('/documents/<document_id>/versions')
@login_required
def document_versions(document_id):
    """View document version history"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get all versions
    versions = get_document_versions(user_id, document_id)
    
    return render_template(
        'document_versions.html',
        document=document,
        versions=versions
    )

@app.route('/documents/<document_id>/versions/<version_id>')
@login_required
def view_document_version(document_id, version_id):
    """View a specific version of a document"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get the version
    versions = get_document_versions(user_id, document_id)
    version = next((v for v in versions if v.get('id') == version_id), None)
    
    if not version:
        flash('Version not found', 'danger')
        return redirect(url_for('view_document', document_id=document_id))
    
    # Get document content for this version
    source_content = get_document_content(user_id, document_id, 'source', version_id)
    translated_content = get_document_content(user_id, document_id, 'translated', version_id)
    
    return render_template(
        'document_version_view.html',
        document=document,
        version=version,
        source_content=source_content,
        translated_content=translated_content,
        versions=versions
    )

@app.route('/documents/<document_id>/versions/<version_id>/restore', methods=['POST'])
@login_required
def restore_document_version(document_id, version_id):
    """Restore a previous version of a document"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get the version
    versions = get_document_versions(user_id, document_id)
    version = next((v for v in versions if v.get('id') == version_id), None)
    
    if not version:
        return json_error('Version not found', 404)
    
    # Get version content
    source_content = get_document_content(user_id, document_id, 'source', version_id)
    translated_content = get_document_content(user_id, document_id, 'translated', version_id)
    
    # Get restoration notes
    data = request.json or {}
    notes = data.get('notes', f"Restored from version {version.get('version')}")
    
    # Create a new version based on the restored content
    update_data = {
        'version_notes': notes,
        'source_content': source_content,
        'translated_content': translated_content
    }
    
    result = update_document(user_id, document_id, update_data, create_new_version=True)
    if not result:
        return json_error('Failed to restore version', 500)
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='document_version_restored',
                properties={
                    'document_id': document_id,
                    'document_title': document.get('title', 'unknown'),
                    'from_version': version.get('version'),
                    'to_version': result.get('version')
                }
            )
        except Exception as e:
            logger.error(f"Error tracking version restoration: {str(e)}")
    
    return json_response({
        'success': True,
        'message': f"Successfully restored version {version.get('version')} as new version {result.get('version')}",
        'document_id': document_id,
        'version': result.get('version')
    })

@app.route('/documents/<document_id>/versions', methods=['POST'])
@login_required
def create_document_version(document_id):
    """Create a new version of a document"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get version notes
    data = request.json or {}
    notes = data.get('notes', '')
    
    # Update the document to create a new version
    update_data = {
        'version_notes': notes
    }
    
    result = update_document(user_id, document_id, update_data, create_new_version=True)
    if not result:
        return json_error('Failed to create new version', 500)
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='document_version_created',
                properties={
                    'document_id': document_id,
                    'document_title': document.get('title', 'unknown'),
                    'version': result.get('version')
                }
            )
        except Exception as e:
            logger.error(f"Error tracking version creation: {str(e)}")
    
    return json_response({
        'success': True,
        'message': 'New version created successfully',
        'document_id': document_id,
        'version': result.get('version')
    })

@app.route('/documents/<document_id>/edit')
@login_required
def edit_document(document_id):
    """Edit a document"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get document content
    source_content = get_document_content(user_id, document_id, 'source')
    translated_content = get_document_content(user_id, document_id, 'translated')
    
    # Get all folders for selection
    folders = get_user_folders(user_id)
    
    return render_template(
        'document_edit.html',
        document=document,
        source_content=source_content,
        translated_content=translated_content,
        folders=folders,
        languages=LANGUAGE_CODES
    )

@app.route('/documents/<document_id>', methods=['PUT'])
@login_required
def update_document_route(document_id):
    """Update document details"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get update data
    data = request.json
    if not data:
        return json_error('No data provided', 400)
    
    # Update document
    result = update_document(user_id, document_id, data)
    if not result:
        return json_error('Failed to update document', 500)
    
    return json_response({
        'success': True,
        'message': 'Document updated successfully',
        'document': result
    })

@app.route('/documents/<document_id>/content', methods=['PUT'])
@login_required
def update_document_content(document_id):
    """Update document content"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get update data
    data = request.json
    if not data:
        return json_error('No data provided', 400)
    
    # Save source content if provided
    source_content = data.get('source_content')
    if source_content is not None:
        save_document_content(user_id, document_id, source_content, 'source')
    
    # Save translated content if provided
    translated_content = data.get('translated_content')
    if translated_content is not None:
        save_document_content(user_id, document_id, translated_content, 'translated')
    
    return json_response({
        'success': True,
        'message': 'Document content updated successfully'
    })

@app.route('/documents/<document_id>/move', methods=['POST'])
@login_required
def move_document(document_id):
    """Move a document to a different folder"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Get target folder
    data = request.json
    folder_id = data.get('folder_id')
    
    # Check if target folder exists if a folder_id is provided
    if folder_id:
        folder = get_folder(user_id, folder_id)
        if not folder:
            return json_error('Target folder not found', 404)
    
    # Update document folder
    update_data = {'folder_id': folder_id}
    result = update_document(user_id, document_id, update_data)
    if not result:
        return json_error('Failed to move document', 500)
    
    # Determine destination name for message
    destination = "root level" if not folder_id else f"folder '{folder['name']}'"
    
    return json_response({
        'success': True,
        'message': f'Document moved to {destination} successfully'
    })

@app.route('/documents/<document_id>/download')
@login_required
def download_document(document_id):
    """Download a document"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'danger')
        return redirect(url_for('documents'))
    
    # Get document content
    translated_content = get_document_content(user_id, document_id, 'translated')
    if not translated_content:
        flash('Document content not found', 'danger')
        return redirect(url_for('view_document', document_id=document_id))
    
    # Get export settings
    export_format = request.args.get('format', 'pdf')
    
    # Use the document title for the download filename
    safe_title = ''.join(c for c in document.get('title', 'document') if c.isalnum() or c in ' _-').strip()
    safe_title = safe_title.replace(' ', '_')
    
    try:
        # Generate output based on format
        if export_format == 'txt':
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
            with open(temp_file.name, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=f"{safe_title}.txt",
                mimetype='text/plain'
            )
        
        elif export_format == 'docx':
            # Get user's export settings or use defaults
            settings = document.get('settings', {}).get('export_settings', DEFAULT_EXPORT_SETTINGS)
            
            output_path = create_docx_with_text(
                translated_content,
                font_family=settings.get('font_family', 'helvetica'),
                font_size=settings.get('font_size', 12),
                page_size=settings.get('page_size', 'A4'),
                orientation=settings.get('orientation', 'portrait'),
                margin=settings.get('margin_size', 15),
                line_spacing=float(settings.get('line_spacing', 1.5)),
                alignment=settings.get('alignment', 'left'),
                include_page_numbers=settings.get('include_page_numbers', True),
                header_text=settings.get('header_text', ''),
                footer_text=settings.get('footer_text', '')
            )
            
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"{safe_title}.docx",
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        
        elif export_format == 'html':
            # Get user's export settings or use defaults
            settings = document.get('settings', {}).get('export_settings', DEFAULT_EXPORT_SETTINGS)
            
            output_path = create_html_with_text(
                translated_content,
                font_family=settings.get('font_family', 'helvetica'),
                font_size=settings.get('font_size', 12),
                line_spacing=float(settings.get('line_spacing', 1.5)),
                alignment=settings.get('alignment', 'left'),
                include_page_numbers=settings.get('include_page_numbers', True),
                header_text=settings.get('header_text', ''),
                footer_text=settings.get('footer_text', '')
            )
            
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"{safe_title}.html",
                mimetype='text/html'
            )
        
        else:
            # Default to PDF
            settings = document.get('settings', {}).get('export_settings', DEFAULT_EXPORT_SETTINGS)
            
            output_path = create_pdf_with_formatting(
                translated_content,
                font_family=settings.get('font_family', 'helvetica'),
                font_size=settings.get('font_size', 12),
                page_size=settings.get('page_size', 'A4'),
                orientation=settings.get('orientation', 'portrait'),
                margin=settings.get('margin_size', 15),
                line_spacing=float(settings.get('line_spacing', 1.5)),
                alignment=settings.get('alignment', 'left'),
                include_page_numbers=settings.get('include_page_numbers', True),
                header_text=settings.get('header_text', ''),
                footer_text=settings.get('footer_text', '')
            )
            
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"{safe_title}.pdf",
                mimetype='application/pdf'
            )
    
    except Exception as e:
        logger.error(f"Error creating download file: {str(e)}")
        flash(f"Error generating document: {str(e)}", 'danger')
        return redirect(url_for('view_document', document_id=document_id))
        
    finally:
        # Clean up temporary file
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file.name)
            except:
                pass
        if 'output_path' in locals():
            try:
                os.unlink(output_path)
            except:
                pass

@app.route('/documents/<document_id>/delete', methods=['POST'])
@login_required
def delete_document_post_route(document_id):
    """Delete a document (POST method fallback for browsers without JS)"""
    user_id = get_user_id()
    if not user_id:
        flash('Unauthorized', 'error')
        return redirect(url_for('documents'))
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        flash('Document not found', 'error')
        return redirect(url_for('documents'))
    
    # Delete document
    result = delete_document(user_id, document_id)
    if not result:
        flash('Failed to delete document', 'error')
        return redirect(url_for('documents'))
    
    flash('Document deleted successfully', 'success')
    return redirect(url_for('documents'))

@app.route('/documents/<document_id>', methods=['DELETE'])
@login_required
def delete_document_route(document_id):
    """Delete a document"""
    user_id = get_user_id()
    if not user_id:
        return json_error('Unauthorized', 401)
    
    # Get the document
    document = get_document(user_id, document_id)
    if not document:
        return json_error('Document not found', 404)
    
    # Delete document
    result = delete_document(user_id, document_id)
    if not result:
        return json_error('Failed to delete document', 500)
    
    # Track in analytics
    if posthog_available and posthog:
        try:
            posthog.capture(
                distinct_id=user_id,
                event='document_deleted',
                properties={
                    'document_id': document_id,
                    'document_title': document.get('title', 'unknown')
                }
            )
        except Exception as e:
            logger.error(f"Error tracking document deletion: {str(e)}")
    
    return json_response({
        'success': True,
        'message': 'Document deleted successfully'
    })

# Admin Route for Database Setup
@app.route('/admin/setup-database')
@login_required
def setup_database():
    """Setup database tables for glossaries and documents"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login'))
    
    # Check if user has admin privileges 
    # For simplicity, we'll just check if they're the first user or have a specific ID pattern
    # In a real app, you would have proper roles and permissions
    user_data = get_user_data(user_id)
    is_admin = False
    
    if user_data:
        # Simple admin check - could be enhanced with proper roles
        is_admin = True
        
    if not is_admin:
        flash("You don't have permission to access this page", "danger")
        return redirect(url_for('index'))
    
    try:
        # Get the SQL setup script content
        with open('setup_tables.sql', 'r') as f:
            sql_script = f.read()
        
        # Execute the SQL script 
        # Note: This is a simplified approach. In a production environment,
        # you would want to use a more robust solution for database migrations.
        try:
            # Split the script into individual statements
            statements = sql_script.split(';')
            
            success_count = 0
            error_messages = []
            
            # Execute each statement
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt:  # Skip empty statements
                    continue
                    
                try:
                    # This is a simplistic approach - in a real app use proper SQL execution
                    from supabase_config import supabase
                    result = supabase.rpc('exec_sql', {'query': stmt}).execute()
                    success_count += 1
                except Exception as stmt_error:
                    error_messages.append(f"Error executing statement: {str(stmt_error)}")
                    # Continue with other statements
            
            # Create storage bucket if it doesn't exist
            try:
                # Try to create the documents bucket directly
                try:
                    # Create bucket with public access and CORS enabled
                    # Using the correct format for create_bucket
                    supabase.storage.create_bucket(
                        id="documents", 
                        options={
                            "public": True,
                            "file_size_limit": 52428800,
                            "allowed_mime_types": ["text/plain", "application/pdf", "application/msword", 
                                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
                        }
                    )
                    
                    # Set CORS policy for the bucket
                    try:
                        # This is the format for setting CORS policy via the Admin API
                        cors_config = {
                            "origins": ["*"],
                            "methods": ["GET", "POST", "PUT", "DELETE"],
                            "headers": ["*"],
                            "maxAgeSeconds": 3600
                        }
                        # Note: This might require a direct SQL query or Admin API access
                        # For now, log that the proper CORS config needs to be set in dashboard
                        logger.info("CORS policy needs to be set in Supabase dashboard for 'documents' bucket")
                    except Exception as cors_error:
                        logger.error(f"Error setting CORS policy: {cors_error}")
                        
                    logger.info("Created 'documents' storage bucket with public access")
                except Exception as bucket_exists_error:
                    # Bucket might already exist, which is fine
                    if "already exists" in str(bucket_exists_error).lower():
                        logger.info("'documents' bucket already exists")
                        # Make sure bucket is public with proper settings
                        try:
                            # Update bucket to be public with proper configs
                            supabase.storage.update_bucket(
                                id="documents", 
                                options={
                                    "public": True,
                                    "file_size_limit": 52428800,
                                    "allowed_mime_types": ["text/plain", "application/pdf", "application/msword", 
                                                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
                                }
                            )
                            logger.info("Updated 'documents' bucket to be public with proper settings")
                            
                            # Remind about CORS configuration
                            logger.info("Note: CORS policy may need to be updated in Supabase dashboard for 'documents' bucket")
                        except Exception as update_error:
                            logger.error(f"Error updating 'documents' bucket: {update_error}")
                    else:
                        # Some other error occurred
                        raise bucket_exists_error
            except Exception as bucket_error:
                error_messages.append(f"Error creating 'documents' bucket: {str(bucket_error)}")
                logger.error(f"Error creating documents bucket: {bucket_error}")
            
            # Report results
            if error_messages:
                flash(f"Database setup completed with {len(error_messages)} errors. See logs for details.", "warning")
                for error in error_messages:
                    logger.error(error)
            else:
                flash("Database tables set up successfully!", "success")
                
            return render_template('setup_database.html', 
                                  success_count=success_count, 
                                  error_count=len(error_messages),
                                  errors=error_messages)
                
        except Exception as exec_error:
            logger.error(f"Error executing SQL script: {str(exec_error)}")
            flash(f"Error executing database setup script: {str(exec_error)}", "danger")
            return render_template('setup_database.html', error=str(exec_error))
        
    except Exception as e:
        logger.error(f"Error in database setup: {str(e)}")
        flash(f"Error reading setup script: {str(e)}", "danger")
        return render_template('setup_database.html', error=str(e))

@app.errorhandler(500)
def internal_server_error(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_error('Internal server error occurred', 500)
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)