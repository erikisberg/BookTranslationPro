import os
import PyPDF2
from fpdf import FPDF
import deepl
from openai import OpenAI
import tempfile
import logging

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
    """First step: Translate text using DeepL"""
    logger.info(f"Translating text to {target_language}")
    translator = deepl.Translator(deepl_api_key)
    try:
        result = translator.translate_text(text, target_lang=target_language)
        logger.info("Text successfully translated with DeepL")
        return result.text
    except Exception as e:
        logger.error(f"DeepL translation error: {str(e)}")
        raise Exception(f"Translation failed: {str(e)}")

def review_translation(text, openai_api_key, assistant_id):
    """Second step: Review the Swedish translation using OpenAI Assistant"""
    logger.info("Starting OpenAI translation review")
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

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

        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            logger.debug(f"Run status: {run_status.status}")

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        text_content = next(
            content.text.value
            for content in messages.data[0].content
            if hasattr(content, 'text')
        )
        logger.info("Translation successfully reviewed by OpenAI Assistant")
        return text_content

    except Exception as e:
        logger.error(f"OpenAI review error: {str(e)}")
        raise Exception(f"Review failed: {str(e)}")

def process_pdf(input_path, deepl_api_key, openai_api_key, assistant_id, 
                instructions=None, target_language='SV', review_style='balanced',
                return_segments=False):
    """Process PDF with detailed logging"""
    logger.info(f"Starting PDF processing: {input_path}")

    try:
        # First verify all API keys are present
        check_api_keys()

        with open(input_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            logger.info(f"PDF loaded successfully. Pages: {len(pdf_reader.pages)}")
            translations = []

            for page_num in range(len(pdf_reader.pages)):
                logger.info(f"Processing page {page_num + 1} of {len(pdf_reader.pages)}")

                # Extract text from page
                original_text = extract_text_from_page(pdf_reader, page_num)
                logger.debug(f"Extracted text from page {page_num + 1}")

                # Translate text
                translated_text = translate_text(original_text, deepl_api_key, target_language)
                logger.debug(f"Translated text from page {page_num + 1}")

                # Review translation
                reviewed_text = review_translation(
                    translated_text,
                    openai_api_key,
                    assistant_id
                )
                logger.debug(f"Reviewed translation for page {page_num + 1}")

                # Store both original and translated text
                translations.append({
                    'id': page_num,
                    'original_text': original_text,
                    'translated_text': reviewed_text
                })

            logger.info("PDF processing completed successfully")
            if return_segments:
                return translations
            else:
                combined_text = '\n\n'.join(t['translated_text'] for t in translations)
                return create_pdf_with_text(combined_text)

    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise Exception(f"PDF processing failed: {str(e)}")

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