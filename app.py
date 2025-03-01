import os
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import tempfile
import logging
from utils import process_pdf, is_allowed_file

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

@app.route('/')
def index():
    return render_template('index.html')

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
        
        # Process the PDF
        output_path = process_pdf(
            filepath,
            DEEPL_API_KEY,
            OPENAI_API_KEY,
            OPENAI_ASSISTANT_ID
        )
        
        # Send the processed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name='translated_' + filename
        )
    
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
        if 'output_path' in locals():
            try:
                os.remove(output_path)
            except:
                pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
