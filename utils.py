import os
import PyPDF2
from fpdf import FPDF
import deepl
from openai import OpenAI
import tempfile
import logging
from datetime import datetime
from database import db
from models import TranslationMemory

logger = logging.getLogger(__name__)

def is_allowed_file(filename):
    return filename.lower().endswith('.pdf')

def get_from_translation_memory(text):
    """Check if a translation exists in memory"""
    try:
        logger.info("Checking translation memory for text...")
        memory = TranslationMemory.query.filter_by(source_text=text).first()
        if memory:
            # Update usage statistics
            memory.last_used_at = datetime.utcnow()
            memory.use_count += 1
            db.session.commit()
            logger.info(f"Translation found in memory (ID: {memory.id}), used {memory.use_count} times")
            return memory.translated_text
        logger.info("No translation found in memory, proceeding with new translation")
        return None
    except Exception as e:
        logger.error(f"Error accessing translation memory: {str(e)}")
        return None

def store_in_translation_memory(source_text, translated_text):
    """Store a new translation in memory"""
    try:
        memory = TranslationMemory(
            source_text=source_text,
            translated_text=translated_text,
            source_language='EN',
            target_language='SV'
        )
        db.session.add(memory)
        db.session.commit()
        logger.info(f"New translation stored in memory with ID: {memory.id}")
    except Exception as e:
        logger.error(f"Failed to store translation in memory: {str(e)}")
        db.session.rollback()

def extract_text_from_page(pdf_reader, page_num):
    page = pdf_reader.pages[page_num]
    return page.extract_text()

def translate_text(text, deepl_api_key):
    # First check translation memory
    logger.info("Checking translation memory for existing translation")
    cached_translation = get_from_translation_memory(text)
    if cached_translation:
        logger.info("Using cached translation from memory")
        return cached_translation

    # If not in memory, translate with DeepL
    logger.info("No cached translation found, using DeepL API")
    translator = deepl.Translator(deepl_api_key)
    try:
        result = translator.translate_text(text, target_lang="SV")
        translated_text = result.text

        # Store the new translation in memory
        logger.info("Storing new translation in memory")
        store_in_translation_memory(text, translated_text)

        return translated_text
    except Exception as e:
        logger.error(f"DeepL translation error: {str(e)}")
        raise Exception(f"Translation failed: {str(e)}")

def review_translation(text, openai_api_key, assistant_id):
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

    try:
        thread = client.beta.threads.create()

        # Add the message to the thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"Please review and improve this Swedish translation while maintaining its meaning: {text}"
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # Wait for completion
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        # Extract the text content from the first message (most recent)
        first_message = messages.data[0]
        # The content is a list of MessageContent objects, get the text content
        text_content = next(
            content.text.value
            for content in first_message.content
            if hasattr(content, 'text')
        )
        return text_content

    except Exception as e:
        logger.error(f"OpenAI review error: {str(e)}")
        raise Exception(f"Review failed: {str(e)}")

def create_pdf_with_text(text_content):
    pdf = FPDF()
    pdf.add_page()

    # Set basic font configuration
    pdf.set_font('helvetica', size=12)

    # Handle text encoding properly
    # Split text into lines to fit page width
    pdf.set_auto_page_break(auto=True, margin=15)

    try:
        # Split text into paragraphs
        paragraphs = text_content.split('\n')
        for paragraph in paragraphs:
            # Write each paragraph
            # Encode as latin-1 to handle special characters
            cleaned_text = paragraph.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 10, cleaned_text)
            # Add some space between paragraphs
            pdf.ln(5)
    except Exception as e:
        logger.error(f"Error writing text to PDF: {str(e)}")
        raise Exception(f"Failed to create PDF: {str(e)}")

    # Save to temporary file
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(temp_output.name)
    return temp_output.name

def process_pdf(input_path, deepl_api_key, openai_api_key, assistant_id):
    try:
        with open(input_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            translated_pages = []

            for page_num in range(len(pdf_reader.pages)):
                # Extract text from page
                text = extract_text_from_page(pdf_reader, page_num)

                # Translate text
                translated_text = translate_text(text, deepl_api_key)

                # Review translation
                reviewed_text = review_translation(
                    translated_text,
                    openai_api_key,
                    assistant_id
                )

                translated_pages.append(reviewed_text)

            # Combine all pages into a single PDF
            combined_text = '\n\n'.join(translated_pages)
            output_path = create_pdf_with_text(combined_text)

            return output_path

    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise Exception(f"PDF processing failed: {str(e)}")