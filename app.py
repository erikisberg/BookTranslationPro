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

def wants_json():
    """Check if the request wants a JSON response"""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept', '').startswith('application/json')
    )

@app.before_request
def before_request():
    """Log request details"""
    logger.info(f"Received {request.method} request to {request.path}")
    logger.debug(f"Headers: {dict(request.headers)}")
    logger.debug(f"Form data: {dict(request.form)}")
    logger.debug(f"Files: {request.files}")
    request.wants_json = wants_json()
    logger.info(f"Request wants JSON response: {request.wants_json}")

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler with detailed logging"""
    error_msg = str(e)
    logger.error(f"Uncaught exception: {error_msg}")
    logger.error(f"Exception type: {type(e).__name__}")
    logger.error(f"Traceback:\n{traceback.format_exc()}")
    logger.error(f"Request path: {request.path}")
    logger.error(f"Request method: {request.method}")
    logger.error(f"Request headers: {dict(request.headers)}")

    if request.wants_json:
        logger.info("Returning JSON error response")
        response = jsonify({
            'error': error_msg,
            'status': 'error'
        })
        response.status_code = 500
        response.headers['Content-Type'] = 'application/json'
        return response

    logger.info("Returning HTML error response")
    return render_template('500.html'), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with detailed error logging"""
    logger.info("Processing file upload request")
    try:
        # Validate request
        if 'file' not in request.files:
            logger.warning("No file in request")
            raise ValueError('No file provided')

        file = request.files['file']
        if file.filename == '':
            logger.warning("Empty filename")
            raise ValueError('No file selected')

        if not is_allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            raise ValueError('Invalid file type. Please upload a PDF.')

        # Save and process file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"Saving file to {filepath}")
        file.save(filepath)

        try:
            # Get configuration
            instructions = os.environ.get('ASSISTANT_INSTRUCTIONS', DEFAULT_INSTRUCTIONS)
            target_language = os.environ.get('TARGET_LANGUAGE', 'SV')
            review_style = os.environ.get('REVIEW_STYLE', 'balanced')

            logger.info("Processing PDF with configuration")
            logger.debug(f"Target language: {target_language}")
            logger.debug(f"Review style: {review_style}")

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

            # Store result
            session['translations'] = translations
            logger.info("Successfully processed PDF")

            # Return response
            if request.wants_json:
                logger.info("Returning JSON success response")
                return jsonify({
                    'success': True,
                    'redirect': url_for('review')
                }), 200, {'Content-Type': 'application/json'}

            logger.info("Redirecting to review page")
            return redirect(url_for('review'))

        finally:
            # Cleanup
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up temporary file: {filepath}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up file: {cleanup_error}")

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        logger.error(traceback.format_exc())
        if request.wants_json:
            return jsonify({
                'error': str(e),
                'status': 'error'
            }), 500, {'Content-Type': 'application/json'}
        return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

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

        if wants_json():
            return jsonify({'success': True, 'redirect': url_for('assistant_config')})
        return redirect(url_for('assistant_config'))

    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        if wants_json():
            return jsonify({'error': str(e)}), 500
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

        if wants_json():
            return jsonify({'success': True, 'redirect': url_for('review')})
        return redirect(url_for('review'))

    except Exception as e:
        logger.error(f"Error saving reviews: {str(e)}")
        if wants_json():
            return jsonify({'error': str(e)}), 500
        return redirect(url_for('review'))

@app.route('/download-final')
def download_final():
    translations = session.get('translations', [])
    if not translations:
        if wants_json():
            return jsonify({'error': 'No translations available'}), 400
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
        if wants_json():
            return jsonify({'error': str(e)}), 500
        return redirect(url_for('index'))

    finally:
        if 'output_path' in locals():
            try:
                os.remove(output_path)
            except:
                pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)