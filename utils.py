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

def extract_text_from_page(pdf_reader, page_num):
    page = pdf_reader.pages[page_num]
    return page.extract_text()

def translate_text(text, deepl_api_key, target_language='SV'):
    translator = deepl.Translator(deepl_api_key)
    try:
        result = translator.translate_text(text, target_lang=target_language)
        return result.text
    except Exception as e:
        logger.error(f"DeepL translation error: {str(e)}")
        raise Exception(f"Translation failed: {str(e)}")

def update_assistant_config(api_key, assistant_id, instructions, target_language, review_style):
    client = OpenAI(api_key=api_key)

    # Format instructions based on review style
    style_instructions = {
        'conservative': "Make minimal changes while fixing only clear errors.",
        'balanced': "Make moderate improvements while maintaining the original style.",
        'creative': "Enhance the text significantly while keeping the core meaning."
    }

    full_instructions = f"""
{instructions}

Target Language: {target_language}
Review Style: {style_instructions[review_style]}
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

def review_translation(text, openai_api_key, assistant_id):
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

    try:
        thread = client.beta.threads.create()

        # Add the message to the thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=text
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
            # Encode as UTF-8 to handle special characters
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

def process_pdf(input_path, deepl_api_key, openai_api_key, assistant_id, 
               instructions=None, target_language='SV', review_style='balanced'):
    try:
        with open(input_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            translated_pages = []

            for page_num in range(len(pdf_reader.pages)):
                # Extract text from page
                text = extract_text_from_page(pdf_reader, page_num)

                # Translate text
                translated_text = translate_text(text, deepl_api_key, target_language)

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