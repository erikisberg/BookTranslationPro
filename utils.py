import os
import json
import PyPDF2
from fpdf import FPDF
import deepl
from openai import OpenAI
import tempfile
import logging
import time
import traceback
from flask import stream_with_context, Response

logger = logging.getLogger(__name__)

def is_allowed_file(filename):
    return filename.lower().endswith('.pdf')

def check_api_keys():
    """Verify that all required API keys are present and log their status"""
    deepl_key = os.environ.get('DEEPL_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')
    assistant_id = os.environ.get('OPENAI_ASSISTANT_ID')

    logger.info("Checking API keys...")
    if not deepl_key:
        logger.error("DEEPL_API_KEY is missing")
        raise ValueError("DeepL API key is not configured")
    if not openai_key:
        logger.error("OPENAI_API_KEY is missing")
        raise ValueError("OpenAI API key is not configured")
    if not assistant_id:
        logger.error("OPENAI_ASSISTANT_ID is missing")
        raise ValueError("OpenAI Assistant ID is not configured")

    logger.info("All required API keys are present")
    return True

def extract_text_from_page(pdf_reader, page_num):
    try:
        page = pdf_reader.pages[page_num]
        return page.extract_text()
    except Exception as e:
        logger.error(f"Error extracting text from page {page_num}: {str(e)}")
        raise

def translate_text(text, deepl_api_key, target_language='SV'):
    """First step: Translate text using DeepL with retry logic"""
    logger.info(f"Translating text to {target_language}")
    translator = deepl.Translator(deepl_api_key)
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            result = translator.translate_text(text, target_lang=target_language)
            logger.info("Text successfully translated with DeepL")
            return result.text
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"DeepL translation error after {max_retries} attempts: {str(e)}")
                raise Exception(f"Translation failed: {str(e)}")
            logger.warning(f"Translation attempt {attempt + 1} failed, retrying...")
            time.sleep(retry_delay)
            retry_delay *= 2

def review_translation(text, openai_api_key, assistant_id):
    """Second step: Review the Swedish translation using OpenAI Assistant with timeout handling"""
    logger.info("Starting OpenAI translation review")
    client = OpenAI(api_key=openai_api_key, timeout=30)  # Set explicit timeout

    try:
        thread = client.beta.threads.create()
        logger.debug("Created OpenAI thread")

        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"Review and improve this Swedish translation, focusing on natural language flow and accuracy: {text}"
        )
        logger.debug("Added message to thread")

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )
        logger.debug("Started assistant run")

        max_wait_time = 25  # Max wait time in seconds
        start_time = time.time()

        while True:
            if time.time() - start_time > max_wait_time:
                logger.warning("OpenAI review approaching timeout")
                break

            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            logger.debug(f"Run status: {run_status.status}")
            time.sleep(1)

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        text_content = next(
            content.text.value
            for message in messages.data
            for content in message.content
            if hasattr(content, 'text')
        )
        logger.info("Translation successfully reviewed by OpenAI Assistant")
        return text_content

    except Exception as e:
        logger.error(f"OpenAI review error: {str(e)}")
        raise Exception(f"Review failed: {str(e)}")

def process_pdf_stream(input_path, deepl_api_key, openai_api_key, assistant_id, 
                      instructions=None, target_language='SV', review_style='balanced'):
    """Process PDF with streaming to avoid timeouts"""
    def generate():
        try:
            logger.info(f"Starting PDF processing for file: {input_path}")

            # First verify all API keys are present
            check_api_keys()

            # Verify input file exists
            if not os.path.exists(input_path):
                raise Exception(f"Input file not found: {input_path}")

            if os.path.getsize(input_path) == 0:
                raise Exception("Input file is empty")

            translations = []
            with open(input_path, 'rb') as file:
                try:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    logger.info(f"Successfully opened PDF with {total_pages} pages")

                    yield f'data: {json.dumps({"status": "started", "total_pages": total_pages})}\n\n'

                    for page_num in range(total_pages):
                        logger.info(f"Processing page {page_num + 1} of {total_pages}")

                        # Extract text
                        original_text = extract_text_from_page(pdf_reader, page_num)
                        if not original_text.strip():
                            logger.warning(f"Page {page_num + 1} appears to be empty")
                        yield f'data: {json.dumps({"status": "extracting", "page": page_num + 1, "total_pages": total_pages})}\n\n'

                        # Translate
                        translated_text = translate_text(original_text, deepl_api_key, target_language)
                        yield f'data: {json.dumps({"status": "translating", "page": page_num + 1, "total_pages": total_pages})}\n\n'

                        # Review
                        reviewed_text = review_translation(translated_text, openai_api_key, assistant_id)
                        yield f'data: {json.dumps({"status": "reviewing", "page": page_num + 1, "total_pages": total_pages})}\n\n'

                        translations.append({
                            'id': page_num,
                            'original_text': original_text,
                            'translated_text': reviewed_text
                        })

                    logger.info("PDF processing completed successfully")
                    yield f'data: {json.dumps({"status": "completed", "translations": translations})}\n\n'

                except PyPDF2.PdfReadError as e:
                    logger.error(f"Failed to read PDF: {str(e)}")
                    raise Exception(f"Invalid or corrupted PDF file: {str(e)}")

        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            logger.error(traceback.format_exc())
            yield f'data: {json.dumps({"status": "error", "message": str(e)})}\n\n'

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

def create_pdf_with_text(text_content):
    logger.info("Creating output PDF")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('helvetica', size=12)
    pdf.set_auto_page_break(auto=True, margin=15)

    try:
        paragraphs = text_content.split('\n')
        for paragraph in paragraphs:
            cleaned_text = paragraph.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 10, cleaned_text)
            pdf.ln(5)

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf.output(temp_output.name)
        logger.info("PDF created successfully")
        return temp_output.name

    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        raise Exception(f"Failed to create PDF: {str(e)}")

def update_assistant_config(api_key, assistant_id, instructions, target_language, review_style):
    client = OpenAI(api_key=api_key)

    # Format instructions based on review style
    style_instructions = {
        'conservative': "Make minimal changes while fixing only clear errors.",
        'balanced': "Make moderate improvements while maintaining the original style.",
        'creative': "Enhance the text significantly while keeping the core meaning."
    }

    # Make it clear that the assistant is reviewing Swedish translations
    full_instructions = f"""
You are a Swedish language expert reviewing translations.
{instructions}

Target Language: {target_language}
Review Style: {style_instructions[review_style]}

Important: You are reviewing text that has already been translated to Swedish.
Focus on improving the Swedish language quality, naturalness, and accuracy.
"""

    try:
        # Update the assistant's configuration
        client.beta.assistants.update(
            assistant_id=assistant_id,
            instructions=full_instructions
        )
        logger.info("Assistant configuration updated successfully")
    except Exception as e:
        logger.error(f"Error updating assistant configuration: {str(e)}")
        raise Exception(f"Failed to update assistant configuration: {str(e)}")