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
    """Extract and validate text from a PDF page"""
    try:
        page = pdf_reader.pages[page_num]
        text = page.extract_text()

        # Validate extracted text
        if not text or text.isspace():
            raise ValueError("Extracted text is empty or whitespace only")

        text = text.strip()
        if len(text) < 10:  # Minimum reasonable length for a page
            raise ValueError("Extracted text is too short to be valid content")

        logger.info(f"Successfully extracted {len(text)} characters from page {page_num + 1}")
        return text

    except Exception as e:
        logger.error(f"Error extracting text from page {page_num + 1}: {str(e)}")
        raise Exception(f"Failed to extract text from page {page_num + 1}: {str(e)}")

def translate_text(text, deepl_api_key, target_language='SV'):
    """First step: Translate text using DeepL"""
    if not text or text.isspace():
        raise ValueError("Cannot translate empty text")

    translator = deepl.Translator(deepl_api_key)
    try:
        logger.info(f"Sending {len(text)} characters to DeepL for translation")
        result = translator.translate_text(text, target_lang=target_language)

        if not result.text or result.text.isspace():
            raise ValueError("DeepL returned empty translation")

        logger.info("Text successfully translated with DeepL")
        return result.text

    except Exception as e:
        logger.error(f"DeepL translation error: {str(e)}")
        raise Exception(f"Translation failed: {str(e)}")

def review_translation(text, openai_api_key, assistant_id):
    """Second step: Review the Swedish translation using OpenAI Assistant"""
    if not text or text.isspace():
        raise ValueError("Cannot review empty translation")

    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

    try:
        logger.info(f"Creating new thread for reviewing {len(text)} characters")
        thread = client.beta.threads.create()

        logger.info("Adding message to thread")
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""Review and improve this Swedish translation. 
            The text should be clear, natural, and maintain the original meaning:

            {text}

            If the text appears scrambled or unclear, return an error message starting with 'TRANSLATION_ERROR:'.
            """
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
                break
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"Run failed with status: {run_status.status}")
                return text

            if attempt < max_retries - 1:
                delay = min(initial_delay * (4 ** attempt), max_delay)
                logger.info(f"Waiting {delay} seconds before next check")
                time.sleep(delay)
            else:
                logger.warning("Maximum retry attempts reached")
                return text

        logger.info("Retrieving assistant's response")
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        if not messages.data:
            logger.warning("No messages received from assistant")
            return text

        try:
            response = next(
                content.text.value
                for content in messages.data[0].content
                if hasattr(content, 'text')
            )

            if response.startswith('TRANSLATION_ERROR:'):
                raise ValueError(response)

            logger.info("Translation review completed successfully")
            return response

        except (StopIteration, AttributeError) as e:
            logger.error(f"Error extracting message content: {str(e)}")
            return text

    except Exception as e:
        logger.error(f"Error in review_translation: {str(e)}")
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

def process_pdf(filepath, deepl_api_key, openai_api_key, assistant_id, return_segments=False):
    """Process each page of the PDF independently with separate API calls."""
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            translations = []
            total_pages = len(pdf_reader.pages)

            logger.info(f"Starting to process PDF with {total_pages} pages")

            for page_num in range(total_pages):
                try:
                    logger.info(f"Processing page {page_num + 1} of {total_pages}")

                    # Step 1: Extract text from the current page
                    original_text = extract_text_from_page(pdf_reader, page_num)
                    if not original_text:
                        raise ValueError("No valid text extracted from page")

                    # Step 2: Translate text using DeepL
                    logger.info(f"Translating page {page_num + 1} with DeepL")
                    translated_text = translate_text(original_text, deepl_api_key)
                    if not translated_text:
                        raise ValueError("Translation returned empty result")

                    # Step 3: Review translation using OpenAI
                    logger.info(f"Reviewing translation for page {page_num + 1} with OpenAI")
                    reviewed_text = review_translation(
                        translated_text,
                        openai_api_key,
                        assistant_id
                    )

                    translations.append({
                        'id': page_num,
                        'original_text': original_text,
                        'translated_text': reviewed_text,
                        'status': 'success'
                    })
                    logger.info(f"Successfully completed processing page {page_num + 1}")

                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                    translations.append({
                        'id': page_num,
                        'original_text': original_text if 'original_text' in locals() else '',
                        'translated_text': translated_text if 'translated_text' in locals() else original_text if 'original_text' in locals() else '',
                        'status': 'error',
                        'error': str(e)
                    })
                    continue

            successful_pages = sum(1 for t in translations if t['status'] == 'success')
            logger.info(f"PDF processing complete. Successfully processed {successful_pages} out of {total_pages} pages")

            if not translations:
                raise Exception("No pages could be processed")

            if return_segments:
                return translations
            else:
                successful_translations = [t['translated_text'] for t in translations if t['status'] == 'success']
                if not successful_translations:
                    raise Exception("No pages were successfully translated")
                combined_text = '\n\n'.join(successful_translations)
                return create_pdf_with_text(combined_text)

    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise Exception(f"PDF processing failed: {str(e)}")