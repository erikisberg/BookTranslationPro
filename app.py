import os
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, abort
from werkzeug.utils import secure_filename
import tempfile
import logging
import json
import time
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from posthog import Posthog
from utils import (
    process_pdf, is_allowed_file, create_pdf_with_text, create_pdf_with_formatting, 
    create_pdf_with_text_basic, create_docx_with_text, create_html_with_text
)
from auth import login_required, get_current_user, get_user_id, sign_up, sign_in, sign_out, reset_password
from supabase_config import (
    get_user_data, save_user_data, get_user_translations, save_translation,
    get_full_translation, delete_translation, get_user_settings, save_user_settings,
    get_user_assistants, get_assistant, save_assistant, delete_assistant
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-dev")

# Get API keys from environment
DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_ASSISTANT_ID = os.environ.get('OPENAI_ASSISTANT_ID')

# PostHog configuration - check both standard and Next.js naming conventions
POSTHOG_API_KEY = os.environ.get('POSTHOG_API_KEY') or os.environ.get('NEXT_PUBLIC_POSTHOG_KEY')
POSTHOG_HOST = os.environ.get('POSTHOG_HOST') or os.environ.get('NEXT_PUBLIC_POSTHOG_HOST', 'https://eu.i.posthog.com')

# Make PostHog configuration available to templates if API key exists
app.config['POSTHOG_API_KEY'] = POSTHOG_API_KEY
app.config['POSTHOG_HOST'] = POSTHOG_HOST

# Context processor to make current user available in templates
@app.context_processor
def inject_user():
    return {'current_user': get_current_user()}

# Middleware to capture request data for PostHog and enforce login for main pages
@app.before_request
def before_request():
    # Skip login check for authentication routes and static files
    if (request.path.startswith('/static/') or 
        request.path == '/login' or 
        request.path == '/signup' or 
        request.path == '/reset-password' or
        request.path == '/logout'):
        pass
    elif 'user' not in session and request.endpoint != 'login' and request.endpoint != 'signup':
        # Skip redirecting AJAX requests to avoid breaking client-side functionality
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            flash('Logga in för att fortsätta', 'warning')
            logger.debug(f"Redirecting unauthenticated user from {request.path} to login")
            if not request.path.startswith('/static/'):
                session['next'] = request.url
                return redirect(url_for('login'))

    # Only track if PostHog is initialized
    if posthog:
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

# Directory to store translations temporarily
TRANSLATIONS_DIR = os.path.join(tempfile.gettempdir(), 'translations')
if not os.path.exists(TRANSLATIONS_DIR):
    os.makedirs(TRANSLATIONS_DIR)

# Configure upload settings
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# This section has been moved above to initialize variables before they are used

# Initialize PostHog if API key is available
posthog = None
if POSTHOG_API_KEY:
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
    logger.info("PostHog API key not provided, analytics disabled")

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
    'openai_api_key': '',
    'openai_assistant_id': ''
}

def json_response(data, status=200):
    """Helper function to ensure consistent JSON responses"""
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
            if posthog:
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
        
        # Track successful login
        if posthog:
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
            if posthog:
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
            if posthog:
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
        if posthog:
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
    if posthog:
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
    translation_text = get_full_translation(user_id, id)
    
    if not translation_text:
        flash('Översättning kunde inte hittas', 'danger')
        return redirect(url_for('history'))
    
    return render_template('view_translation.html', translation_text=translation_text, id=id)

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
    assistants = get_user_assistants(user_id)
    return render_template('index.html', assistants=assistants)

@app.route('/assistant-config', methods=['GET'])
@login_required
def assistant_config():
    # Get user's assistants
    user_id = get_user_id()
    assistants = get_user_assistants(user_id)
    
    return render_template('assistant_config.html', assistants=assistants)

@app.route('/save-assistant', methods=['POST'])
@login_required
def save_assistant_route():
    """Save or update an assistant configuration"""
    try:
        user_id = get_user_id()
        assistant_data = {
            'id': request.form.get('id'),  # Will be None for new assistants
            'name': request.form.get('name'),
            'assistant_id': request.form.get('assistant_id'),
            'author': request.form.get('author'),
            'genre': request.form.get('genre'),
            'instructions': request.form.get('instructions')
        }
        
        # Save to database
        save_assistant(user_id, assistant_data)
        
        flash('Assistent sparad!', 'success')
        return redirect(url_for('assistant_config'))
    except Exception as e:
        logger.error(f"Error saving assistant: {str(e)}")
        flash(f"Ett fel uppstod: {str(e)}", 'danger')
        return redirect(url_for('assistant_config'))
        
@app.route('/delete-assistant/<assistant_id>')
@login_required
def delete_assistant_route(assistant_id):
    """Delete an assistant"""
    try:
        user_id = get_user_id()
        success = delete_assistant(user_id, assistant_id)
        
        if success:
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
    # Get current export settings from session or use defaults
    settings = session.get('export_settings', DEFAULT_EXPORT_SETTINGS)
    
    return render_template('export_settings.html',
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

@app.route('/api_keys_settings', methods=['GET', 'POST'])
@login_required
def api_keys_settings():
    user_id = get_user_id()
    
    if request.method == 'POST':
        # Get the submitted API keys
        api_keys = {
            'deepl_api_key': request.form.get('deepl_api_key', '').strip(),
            'openai_api_key': request.form.get('openai_api_key', '').strip(),
            'openai_assistant_id': request.form.get('openai_assistant_id', '').strip()
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
        
        # Display success message and redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_response({'success': True, 'redirect': url_for('export_settings')})
        return redirect(url_for('export_settings'))
        
    except Exception as e:
        logger.error(f"Error saving export settings: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        return redirect(url_for('export_settings'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return redirect(url_for('index'))

    if 'file' not in request.files:
        return json_error('No file provided')

    file = request.files['file']
    if file.filename == '':
        return json_error('No file selected')

    if not is_allowed_file(file.filename):
        # Track invalid file type upload attempt
        if posthog:
            posthog.capture(
                distinct_id=get_user_id(),
                event='file_upload_error',
                properties={
                    'error': 'invalid_file_type',
                    'filename': file.filename,
                    'file_extension': os.path.splitext(file.filename)[1].lower() if file.filename else None
                }
            )
        return json_error('Invalid file type. Please upload a PDF.')

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
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
        user_api_keys = get_user_settings(user_id).get('api_keys', DEFAULT_API_KEYS) if user_id else DEFAULT_API_KEYS
        
        # Use user's API keys if provided, otherwise fallback to system keys
        deepl_api_key = user_api_keys.get('deepl_api_key') or DEEPL_API_KEY
        
        # Handle assistant selection and OpenAI settings
        if not skip_openai:
            openai_api_key = user_api_keys.get('openai_api_key') or OPENAI_API_KEY
            
            # If user selected a specific assistant, use that
            if assistant_id_selected:
                assistant_data = get_assistant(user_id, assistant_id_selected)
                if assistant_data and assistant_data.get('assistant_id'):
                    openai_assistant_id = assistant_data.get('assistant_id')
                    logger.info(f"Using selected assistant: {assistant_data.get('name')} ({openai_assistant_id})")
                else:
                    openai_assistant_id = user_api_keys.get('openai_assistant_id') or OPENAI_ASSISTANT_ID
            else:
                openai_assistant_id = user_api_keys.get('openai_assistant_id') or OPENAI_ASSISTANT_ID
        else:
            openai_api_key = None
            openai_assistant_id = None
            
        logger.info(f"Using {'user' if user_api_keys.get('deepl_api_key') else 'system'} DeepL API key")
        if not skip_openai:
            logger.info(f"Using {'user' if user_api_keys.get('openai_api_key') else 'system'} OpenAI API key")
            logger.info(f"Using {'user' if user_api_keys.get('openai_assistant_id') else 'system'} OpenAI Assistant ID")

        # Get custom instructions if using a specific assistant
        custom_instructions = None
        if assistant_id_selected and not skip_openai:
            assistant_data = get_assistant(user_id, assistant_id_selected)
            if assistant_data:
                custom_instructions = assistant_data.get('instructions')
                logger.info(f"Using custom instructions for assistant: {assistant_data.get('name')}")
        
        # Process the PDF and get translations
        translations = process_pdf(
            filepath,
            deepl_api_key,
            openai_api_key,
            openai_assistant_id,
            source_language=source_language,
            target_language=target_language,
            custom_instructions=custom_instructions,
            return_segments=True
        )

        # Generate a unique ID for this translation session
        translation_id = str(int(time.time()))
        session['translation_id'] = translation_id

        # Store translations in file
        translation_file = os.path.join(TRANSLATIONS_DIR, f"{translation_id}.json")
        with open(translation_file, 'w') as f:
            json.dump(translations, f)
            
        # Store filename for later
        session['original_filename'] = secure_filename(file.filename)

        # Track successful file upload and translation
        if posthog:
            posthog.capture(
                distinct_id=get_user_id(),
                event='file_translated',
                properties={
                    'filename': filename,
                    'skip_openai_review': skip_openai,
                    'file_size_kb': os.path.getsize(filepath) / 1024,
                    'page_count': len(translations),
                    'translation_id': translation_id
                }
            )

        return json_response({
            'success': True,
            'redirect': url_for('review')
        })

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return json_error(str(e), 500)

    finally:
        # Cleanup temporary files
        if 'filepath' in locals():
            try:
                os.remove(filepath)
            except:
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

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_response({'success': True, 'redirect': url_for('review')})
        return redirect(url_for('review'))

    except Exception as e:
        logger.error(f"Error saving reviews: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e), 500)
        return redirect(url_for('review'))

@app.route('/download-final')
@login_required
def download_final():
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
            if posthog:
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

@app.errorhandler(404)
def not_found_error(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_error('Resource not found', 404)
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_error('Internal server error occurred', 500)
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)