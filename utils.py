import os
import PyPDF2
from fpdf import FPDF
import deepl
from openai import OpenAI
import tempfile
import logging
import time

logger = logging.getLogger(__name__)

def is_allowed_file(filename):
    return filename.lower().endswith('.pdf')

def extract_text_from_page(pdf_reader, page_num):
    page = pdf_reader.pages[page_num]
    return page.extract_text()

def translate_text(text, deepl_api_key, target_language='SV'):
    """First step: Translate text using DeepL"""
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
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

    try:
        logger.info("Creating new thread for translation review")
        thread = client.beta.threads.create()

        logger.info("Adding message to thread")
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"Review and improve this Swedish translation, focusing on natural language flow and accuracy: {text}"
        )

        logger.info("Starting assistant run")
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # Simplified exponential backoff
        max_retries = 3  # Reduced from 5 to minimize total wait time
        initial_delay = 5  # Increased initial delay from 1 to 5 seconds
        max_delay = 30  # Increased max delay to allow for longer processing

        for attempt in range(max_retries):
            logger.info(f"Checking run status (attempt {attempt + 1}/{max_retries})")
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

            if run_status.status == 'completed':
                logger.info("Run completed successfully")
                break
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"Run failed with status: {run_status.status}")
                # Return original text if OpenAI review fails
                logger.warning("Returning original text due to review failure")
                return text

            if attempt < max_retries - 1:
                delay = min(initial_delay * (4 ** attempt), max_delay)  # More aggressive backoff
                logger.info(f"Waiting {delay} seconds before next check")
                time.sleep(delay)
            else:
                logger.warning("Maximum retry attempts reached, returning original text")
                return text  # Return original text instead of raising exception

        logger.info("Retrieving assistant's response")
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        # Check if we have any messages before accessing them
        if not messages.data:
            logger.warning("No messages received from assistant, returning original text")
            return text

        # Try to get the reviewed text, fall back to original if not found
        try:
            text_content = next(
                content.text.value
                for content in messages.data[0].content
                if hasattr(content, 'text')
            )
            logger.info("Translation review completed successfully")
            return text_content
        except (StopIteration, AttributeError) as e:
            logger.error(f"Error extracting message content: {str(e)}")
            return text

    except Exception as e:
        logger.error(f"Error in review_translation: {str(e)}")
        # Return original text instead of raising exception
        logger.warning("Returning original text due to error")
        return text

def create_pdf_with_text(text_content):
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
    except Exception as e:
        logger.error(f"Error writing text to PDF: {str(e)}")
        raise Exception(f"Failed to create PDF: {str(e)}")

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(temp_output.name)
    return temp_output.name

def process_pdf(input_path, deepl_api_key, openai_api_key, assistant_id, 
                instructions=None, target_language='SV', review_style='balanced',
                return_segments=False):
    try:
        with open(input_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            translations = []

            for page_num in range(len(pdf_reader.pages)):
                logger.info(f"Processing page {page_num + 1}")
                original_text = extract_text_from_page(pdf_reader, page_num)
                translated_text = translate_text(original_text, deepl_api_key, target_language)
                reviewed_text = review_translation(
                    translated_text,
                    openai_api_key,
                    assistant_id
                )

                translations.append({
                    'id': page_num,
                    'original_text': original_text,
                    'translated_text': reviewed_text
                })
                logger.info(f"Completed processing page {page_num + 1}")

            if return_segments:
                return translations
            else:
                combined_text = '\n\n'.join(t['translated_text'] for t in translations)
                return create_pdf_with_text(combined_text)

    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise Exception(f"PDF processing failed: {str(e)}")