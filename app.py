import os
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
import tempfile
import logging
from utils import process_pdf, is_allowed_file, update_assistant_config, create_pdf_with_text

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assistant-config', methods=['GET'])
def assistant_config():
    # Get current configuration from environment or use defaults
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

        # Update the OpenAI assistant configuration
        update_assistant_config(
            OPENAI_API_KEY,
            OPENAI_ASSISTANT_ID,
            instructions,
            target_language,
            review_style
        )

        # Store in environment for persistence
        os.environ['ASSISTANT_INSTRUCTIONS'] = instructions
        os.environ['TARGET_LANGUAGE'] = target_language
        os.environ['REVIEW_STYLE'] = review_style

        return redirect(url_for('assistant_config'))
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/review')
def review():
    translations = session.get('translations', [])
    return render_template('review.html', translations=translations)

@app.route('/save-reviews', methods=['POST'])
def save_reviews():
    translations = session.get('translations', [])

    # Update translations with reviewed text
    for i, translation in enumerate(translations):
        key = f'translation_{i}'
        if key in request.form:
            translation['translated_text'] = request.form[key]

    session['translations'] = translations
    return redirect(url_for('review'))

@app.route('/download-final')
def download_final():
    translations = session.get('translations', [])
    if not translations:
        return jsonify({'error': 'No translations available'}), 400

    # Combine all reviewed translations
    final_text = '\n\n'.join(t['translated_text'] for t in translations)

    # Create final PDF
    output_path = create_pdf_with_text(final_text)

    try:
        return send_file(
            output_path,
            as_attachment=True,
            download_name='final_translation.pdf'
        )
    finally:
        # Cleanup
        try:
            os.remove(output_path)
        except:
            pass

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not is_allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Get current configuration
        instructions = os.environ.get('ASSISTANT_INSTRUCTIONS', DEFAULT_INSTRUCTIONS)
        target_language = os.environ.get('TARGET_LANGUAGE', 'SV')
        review_style = os.environ.get('REVIEW_STYLE', 'balanced')

        # Process the PDF and get translations
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

        # Store translations in session for review
        session['translations'] = translations

        # Return success response with redirect URL
        return jsonify({
            'success': True,
            'redirect': url_for('review')
        })

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return jsonify({'error': str(e)}), 500

    finally:
        # Cleanup temporary files
        if 'filepath' in locals():
            try:
                os.remove(filepath)
            except:
                pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)