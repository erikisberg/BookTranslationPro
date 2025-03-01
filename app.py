import os
import logging
import traceback
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
import tempfile
from utils import process_pdf, is_allowed_file, update_assistant_config, create_pdf_with_text

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class APIError(Exception):
    """Custom exception class for API errors"""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code

def is_ajax():
    """Check if the request is an AJAX request"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def json_response(data, status=200):
    """Create a JSON response with proper headers"""
    response = jsonify(data)
    response.status_code = status
    response.headers['Content-Type'] = 'application/json'
    return response

def error_response(message, status=400):
    """Create a JSON error response"""
    return json_response({'error': message, 'status': 'error'}, status)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure upload settings
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Get API keys from environment
DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_ASSISTANT_ID = os.environ.get('OPENAI_ASSISTANT_ID')

# Default assistant configuration
DEFAULT_INSTRUCTIONS = """Review and improve this translation while:
1. Maintaining the original meaning and intent
2. Ensuring natural and fluent language
3. Preserving formal/informal tone as appropriate
4. Keeping technical terms accurate
5. Adapting cultural references appropriately"""

@app.errorhandler(Exception)
def handle_exception(error):
    """Global exception handler"""
    logger.error(f"Uncaught exception: {str(error)}")
    logger.error(f"Type: {type(error).__name__}")
    logger.error(traceback.format_exc())

    if is_ajax():
        status_code = getattr(error, 'status_code', 500)
        return error_response(str(error), status_code)

    return render_template('500.html'), 500

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if is_ajax():
        return error_response('Resource not found', 404)
    return render_template('404.html'), 404

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with proper error handling"""
    logger.info("Processing file upload")

    try:
        if 'file' not in request.files:
            raise APIError('No file provided')

        file = request.files['file']
        if file.filename == '':
            raise APIError('No file selected')

        if not is_allowed_file(file.filename):
            raise APIError('Invalid file type. Please upload a PDF.')

        # Process file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(filepath)
            logger.info(f"File saved: {filepath}")

            # Get configuration
            instructions = os.environ.get('ASSISTANT_INSTRUCTIONS', DEFAULT_INSTRUCTIONS)
            target_language = os.environ.get('TARGET_LANGUAGE', 'SV')
            review_style = os.environ.get('REVIEW_STYLE', 'balanced')

            # Process PDF
            translations = process_pdf(
                filepath,
                DEEPL_API_KEY,
                OPENAI_API_KEY,
                OPENAI_ASSISTANT_ID,
                instructions,
                target_language,
                review_style,
                return_segments=True
            )

            session['translations'] = translations

            if is_ajax():
                return json_response({
                    'success': True,
                    'redirect': url_for('review')
                })
            return redirect(url_for('review'))

        finally:
            # Cleanup
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up file: {filepath}")
                except Exception as e:
                    logger.error(f"Failed to clean up file: {e}")

    except Exception as e:
        logger.error("Upload failed")
        logger.error(traceback.format_exc())
        raise

@app.route('/assistant-config', methods=['GET'])
def assistant_config():
    current_instructions = os.environ.get('ASSISTANT_INSTRUCTIONS', DEFAULT_INSTRUCTIONS)
    target_language = os.environ.get('TARGET_LANGUAGE', 'SV')
    review_style = os.environ.get('REVIEW_STYLE', 'balanced')

    return render_template('config.html',
                         current_instructions=current_instructions,
                         target_language=target_language,
                         review_style=review_style)

@app.route('/save-assistant-config', methods=['POST'])
def save_assistant_config():
    try:
        instructions = request.form.get('instructions')
        target_language = request.form.get('target_language')
        review_style = request.form.get('review_style')

        if not all([instructions, target_language, review_style]):
            raise APIError('Missing required configuration fields')

        update_assistant_config(
            OPENAI_API_KEY,
            OPENAI_ASSISTANT_ID,
            instructions,
            target_language,
            review_style
        )

        os.environ['ASSISTANT_INSTRUCTIONS'] = instructions
        os.environ['TARGET_LANGUAGE'] = target_language
        os.environ['REVIEW_STYLE'] = review_style

        if is_ajax():
            return json_response({
                'success': True,
                'redirect': url_for('assistant_config')
            })
        return redirect(url_for('assistant_config'))

    except Exception as e:
        raise APIError(str(e))

@app.route('/review')
def review():
    translations = session.get('translations', [])
    return render_template('review.html', translations=translations)

@app.route('/save-reviews', methods=['POST'])
def save_reviews():
    try:
        translations = session.get('translations', [])
        if not translations:
            raise APIError('No translations to save')

        for translation in translations:
            key = f'translation_{translation["id"]}'
            if key in request.form:
                translation['translated_text'] = request.form[key]

        session['translations'] = translations

        if is_ajax():
            return json_response({
                'success': True,
                'redirect': url_for('review')
            })
        return redirect(url_for('review'))

    except Exception as e:
        raise APIError(str(e))

@app.route('/download-final')
def download_final():
    try:
        translations = session.get('translations', [])
        if not translations:
            raise APIError('No translations available')

        final_text = '\n\n'.join(t['translated_text'] for t in translations)
        output_path = create_pdf_with_text(final_text)

        return send_file(
            output_path,
            as_attachment=True,
            download_name='final_translation.pdf'
        )

    except Exception as e:
        raise APIError(str(e))

    finally:
        if 'output_path' in locals():
            try:
                os.remove(output_path)
            except:
                pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)