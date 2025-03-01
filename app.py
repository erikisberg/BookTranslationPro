import os
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
import tempfile
import logging
from utils import process_pdf, is_allowed_file, update_assistant_config, create_pdf_with_text
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the app
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

def wants_json():
    """Check if the request wants a JSON response"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    if request.headers.get('Accept', '').startswith('application/json'):
        return True
    return False

@app.before_request
def before_request():
    """Setup request context"""
    request.wants_json = wants_json()

@app.after_request
def after_request(response):
    """Ensure proper content type for JSON responses"""
    if request.wants_json and not response.headers.get('Content-Type', '').startswith('application/json'):
        try:
            # If we have an error response, convert it to JSON
            data = {'error': response.get_data(as_text=True)}
            response.data = jsonify(data).get_data()
            response.content_type = 'application/json'
        except Exception as e:
            logger.error(f"Error converting response to JSON: {e}")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler"""
    error_msg = str(e)
    logger.error(f"Uncaught exception: {error_msg}")
    logger.error(traceback.format_exc())

    if request.wants_json:
        return jsonify({'error': error_msg}), 500, {'Content-Type': 'application/json'}
    return render_template('500.html'), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            if request.wants_json:
                return jsonify({'error': 'No file provided'}), 400
            return redirect(url_for('index'))

        file = request.files['file']
        if file.filename == '':
            if request.wants_json:
                return jsonify({'error': 'No file selected'}), 400
            return redirect(url_for('index'))

        if not is_allowed_file(file.filename):
            if request.wants_json:
                return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
            return redirect(url_for('index'))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            instructions = os.environ.get('ASSISTANT_INSTRUCTIONS', DEFAULT_INSTRUCTIONS)
            target_language = os.environ.get('TARGET_LANGUAGE', 'SV')
            review_style = os.environ.get('REVIEW_STYLE', 'balanced')

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

            if request.wants_json:
                return jsonify({
                    'success': True,
                    'redirect': url_for('review')
                }), 200
            return redirect(url_for('review'))

        finally:
            try:
                os.remove(filepath)
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")

    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        logger.error(traceback.format_exc())
        if request.wants_json:
            return jsonify({'error': str(e)}), 500
        return redirect(url_for('index'))

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

        if request.wants_json:
            return json_response({'success': True, 'redirect': url_for('assistant_config')})
        return redirect(url_for('assistant_config'))

    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        if request.wants_json:
            return json_error(str(e), 500)
        return redirect(url_for('assistant_config'))

@app.route('/review')
def review():
    translations = session.get('translations', [])
    return render_template('review.html', translations=translations)

@app.route('/save-reviews', methods=['POST'])
def save_reviews():
    try:
        translations = session.get('translations', [])
        for translation in translations:
            key = f'translation_{translation["id"]}'
            if key in request.form:
                translation['translated_text'] = request.form[key]

        session['translations'] = translations

        if request.wants_json:
            return json_response({'success': True, 'redirect': url_for('review')})
        return redirect(url_for('review'))

    except Exception as e:
        logger.error(f"Error saving reviews: {str(e)}")
        if request.wants_json:
            return json_error(str(e), 500)
        return redirect(url_for('review'))

@app.route('/download-final')
def download_final():
    translations = session.get('translations', [])
    if not translations:
        if request.wants_json:
            return json_error('No translations available', 400)
        return redirect(url_for('index'))

    try:
        final_text = '\n\n'.join(t['translated_text'] for t in translations)
        output_path = create_pdf_with_text(final_text)

        return send_file(
            output_path,
            as_attachment=True,
            download_name='final_translation.pdf'
        )
    except Exception as e:
        logger.error(f"Error creating final PDF: {str(e)}")
        if request.wants_json:
            return json_error(str(e), 500)
        return redirect(url_for('index'))
    finally:
        if 'output_path' in locals():
            try:
                os.remove(output_path)
            except:
                pass

def json_response(data, status=200):
    """Helper function to ensure consistent JSON responses"""
    return jsonify(data), status, {'Content-Type': 'application/json'}

def json_error(message, status=400):
    """Helper function for JSON error responses"""
    return json_response({'error': message}, status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)