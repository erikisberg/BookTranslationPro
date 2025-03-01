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

def translate_text(text, deepl_api_key):
    translator = deepl.Translator(deepl_api_key)
    try:
        result = translator.translate_text(text, target_lang="SV")
        return result.text
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
    pdf.set_font("Arial", size=12)
    
    # Split text into lines to fit page width
    lines = text_content.split('\n')
    for line in lines:
        pdf.multi_cell(0, 10, line)
    
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