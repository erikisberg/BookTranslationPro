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

    logger.info(f"DeepL API Key starting with: {deepl_api_key[:5]}...")
    logger.info(f"Target language: {target_language}")
    
    translator = deepl.Translator(deepl_api_key)
    try:
        logger.info(f"Sending {len(text)} characters to DeepL for translation")
        logger.info(f"Text sample: {text[:100]}...")
        result = translator.translate_text(text, target_lang=target_language)

        if not result.text or result.text.isspace():
            raise ValueError("DeepL returned empty translation")

        logger.info("Text successfully translated with DeepL")
        logger.info(f"Translation sample: {result.text[:100]}...")
        return result.text

    except Exception as e:
        logger.error(f"DeepL translation error: {str(e)}")
        raise Exception(f"Translation failed: {str(e)}")

def review_translation(text, openai_api_key, assistant_id):
    """Second step: Review the Swedish translation using OpenAI Assistant"""
    if not text or text.isspace():
        raise ValueError("Cannot review empty translation")

    logger.info(f"OpenAI API Key starting with: {openai_api_key[:5]}...")
    logger.info(f"Assistant ID: {assistant_id}")
    
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    client = OpenAI(api_key=openai_api_key)

    try:
        logger.info(f"Creating new thread for reviewing {len(text)} characters")
        thread = client.beta.threads.create()
        logger.info(f"Created thread with ID: {thread.id}")

        logger.info("Adding message to thread")
        message_content = f"""Granska och förbättra denna svenska översättning. 
            Texten ska vara tydlig, naturlig och bevara den ursprungliga betydelsen:

            {text}

            Om texten verkar förvirrad eller oklar, returnera ett felmeddelande som börjar med 'TRANSLATION_ERROR:'.
            """
        logger.info(f"Message sample: {message_content[:100]}...")
        
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message_content
        )

        logger.info("Starting assistant run")
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # Simplified exponential backoff
        max_retries = 5  # Increased to give more time for completion
        initial_delay = 10  # Increased initial delay to give more time
        max_delay = 60  # Increased max delay to allow for longer processing

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
    """Legacy function - kept for backward compatibility"""
    return create_pdf_with_formatting(text_content)
    
def create_pdf_with_text_basic(text_content):
    """Simple PDF creation as a fallback method"""
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
        logger.error(f"Error in basic PDF creation: {str(e)}")
        # If even this fails, just create an empty PDF
        pass

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(temp_output.name)
    return temp_output.name

def create_pdf_with_formatting(text_content, font_family='helvetica', font_size=12, page_size='A4', 
                               orientation='portrait', margin=15, line_spacing=1.5, alignment='left',
                               include_page_numbers=True, header_text='', footer_text=''):
    """Create a PDF with the given text content using the specified formatting options"""
    try:
        logger.info(f"Creating PDF with settings: font={font_family}, size={font_size}, page={page_size}, orientation={orientation}")
        
        # Create a custom PDF class with header and footer methods to avoid recursion
        class CustomPDF(FPDF):
            def header(self):
                if header_text:
                    self.set_y(5)
                    self.set_font(font_family, 'I', font_size - 2)
                    self.cell(0, 10, header_text, 0, 1, 'C')
                    self.set_y(margin)
                    self.set_font(font_family, size=font_size)
                    
            def footer(self):
                if footer_text or include_page_numbers:
                    self.set_y(-15)
                    self.set_font(font_family, 'I', font_size - 2)
                    
                    if footer_text and include_page_numbers:
                        footer = f"{footer_text} | Sida {self.page_no()}"
                    elif footer_text:
                        footer = footer_text
                    elif include_page_numbers:
                        footer = f"Sida {self.page_no()}"
                    else:
                        return
                        
                    self.cell(0, 10, footer, 0, 0, 'C')
        
        pdf = CustomPDF(orientation=orientation[0], format=page_size)
        pdf.add_page()
        pdf.set_font(font_family, size=font_size)
        pdf.set_auto_page_break(auto=True, margin=margin)
        
        # Set margins
        pdf.set_margins(margin, margin, margin)
        
        # Footer is now handled by the CustomPDF class
        
        # Set alignment
        align_dict = {
            'left': 'L',
            'center': 'C', 
            'right': 'R',
            'justified': 'J'
        }
        align = align_dict.get(alignment, 'L')
        
        # Calculate line height based on line spacing
        line_height = font_size * 0.5 * line_spacing
        
        paragraphs = text_content.split('\n')
        for paragraph in paragraphs:
            if not paragraph.strip():
                pdf.ln(line_height)
                continue
                
            # Handle text encoding
            cleaned_text = paragraph.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, line_height, cleaned_text, 0, align)
            pdf.ln(font_size * 0.3)  # Small space between paragraphs

        # Footer is now handled by the CustomPDF class

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf.output(temp_output.name)
        return temp_output.name
        
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        # Fallback to basic PDF creation if advanced formatting fails
        return create_pdf_with_text_basic(text_content)

def create_docx_with_text(text_content, font_family='helvetica', font_size=12, page_size='A4',
                         orientation='portrait', margin=15, line_spacing=1.5, alignment='left',
                         include_page_numbers=True, header_text='', footer_text=''):
    """Create a Word document with the given text content using the specified formatting options"""
    try:
        # Import python-docx library
        from docx import Document
        from docx.shared import Pt, Inches, Mm
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
        
        # Create a new document
        doc = Document()
        
        # Set page size and orientation
        section = doc.sections[0]
        if page_size == 'A4':
            if orientation == 'portrait':
                section.page_width, section.page_height = Mm(210), Mm(297)
            else:
                section.page_width, section.page_height = Mm(297), Mm(210)
        elif page_size == 'Letter':
            if orientation == 'portrait':
                section.page_width, section.page_height = Inches(8.5), Inches(11)
            else:
                section.page_width, section.page_height = Inches(11), Inches(8.5)
        
        # Set margins
        section.left_margin = Mm(margin)
        section.right_margin = Mm(margin)
        section.top_margin = Mm(margin)
        section.bottom_margin = Mm(margin)
        
        # Add header if specified
        if header_text:
            header = section.header
            header_para = header.paragraphs[0]
            header_para.text = header_text
            header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            header_para.style.font.size = Pt(font_size - 2)
            header_para.style.font.italic = True
        
        # Add footer if specified
        if footer_text or include_page_numbers:
            footer = section.footer
            footer_para = footer.paragraphs[0]
            
            if footer_text and include_page_numbers:
                footer_para.text = f"{footer_text} | "
                footer_para.add_run().add_field('PAGE')
            elif footer_text:
                footer_para.text = footer_text
            elif include_page_numbers:
                footer_para.add_run().add_field('PAGE')
                
            footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            footer_para.style.font.size = Pt(font_size - 2)
            footer_para.style.font.italic = True
        
        # Set paragraph alignment
        align_dict = {
            'left': WD_ALIGN_PARAGRAPH.LEFT,
            'center': WD_ALIGN_PARAGRAPH.CENTER,
            'right': WD_ALIGN_PARAGRAPH.RIGHT,
            'justified': WD_ALIGN_PARAGRAPH.JUSTIFY
        }
        para_align = align_dict.get(alignment, WD_ALIGN_PARAGRAPH.LEFT)
        
        # Add text content
        paragraphs = text_content.split('\n')
        for paragraph in paragraphs:
            if not paragraph.strip():
                doc.add_paragraph()
                continue
                
            para = doc.add_paragraph(paragraph)
            para.alignment = para_align
            
            # Set font properties
            for run in para.runs:
                run.font.size = Pt(font_size)
                if font_family == 'helvetica':
                    run.font.name = 'Arial'
                elif font_family == 'times':
                    run.font.name = 'Times New Roman'
                elif font_family == 'courier':
                    run.font.name = 'Courier New'
            
            # Set line spacing
            if line_spacing == 1.0:
                para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            elif line_spacing == 1.5:
                para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            elif line_spacing == 2.0:
                para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
            else:
                para.paragraph_format.line_spacing = line_spacing
        
        # Save the document
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
        doc.save(temp_output.name)
        return temp_output.name
        
    except ImportError:
        logger.error("python-docx library not installed. Creating PDF instead.")
        # Fall back to PDF if python-docx is not available
        return create_pdf_with_formatting(
            text_content, font_family, font_size, page_size, 
            orientation, margin, line_spacing, alignment,
            include_page_numbers, header_text, footer_text
        )
    except Exception as e:
        logger.error(f"Error creating DOCX: {str(e)}")
        raise Exception(f"Failed to create Word document: {str(e)}")

def create_html_with_text(text_content, font_family='helvetica', font_size=12, 
                         line_spacing=1.5, alignment='left',
                         include_page_numbers=False, header_text='', footer_text=''):
    """Create an HTML file with the given text content using the specified formatting options"""
    # Map font families to CSS equivalents
    font_map = {
        'helvetica': 'Arial, Helvetica, sans-serif',
        'times': 'Times New Roman, Times, serif',
        'courier': 'Courier New, Courier, monospace'
    }
    font_css = font_map.get(font_family, 'Arial, Helvetica, sans-serif')
    
    # Map alignment to CSS
    align_css = alignment
    
    # Create HTML content
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Translated Document</title>
    <style>
        body {{
            font-family: {font_css};
            font-size: {font_size}pt;
            line-height: {line_spacing};
            text-align: {align_css};
            margin: 30px;
        }}
        .header {{
            text-align: center;
            font-style: italic;
            margin-bottom: 30px;
            font-size: {font_size - 2}pt;
        }}
        .footer {{
            text-align: center;
            font-style: italic;
            margin-top: 30px;
            font-size: {font_size - 2}pt;
        }}
        p {{
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
"""

    # Add header if specified
    if header_text:
        html_content += f'<div class="header">{header_text}</div>\n'
    
    # Add content
    paragraphs = text_content.split('\n')
    for paragraph in paragraphs:
        if paragraph.strip():
            html_content += f'<p>{paragraph}</p>\n'
        else:
            html_content += '<p>&nbsp;</p>\n'  # Empty paragraph
    
    # Add footer if specified
    if footer_text:
        html_content += f'<div class="footer">{footer_text}</div>\n'
    
    html_content += """
</body>
</html>
"""
    
    # Write to file
    try:
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        with open(temp_output.name, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return temp_output.name
    except Exception as e:
        logger.error(f"Error creating HTML: {str(e)}")
        raise Exception(f"Failed to create HTML document: {str(e)}")

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
                    try:
                        translated_text = translate_text(original_text, deepl_api_key)
                        if not translated_text:
                            logger.error("Translation returned empty result")
                            translated_text = original_text
                            raise ValueError("Translation returned empty result")
                    except Exception as e:
                        logger.error(f"DeepL translation error for page {page_num + 1}: {str(e)}")
                        translated_text = original_text  # Fallback to original text
                        raise ValueError(f"DeepL translation failed: {str(e)}")

                    # Step 3: Review translation using OpenAI (if enabled)
                    reviewed_text = translated_text  # Default to DeepL translation
                    
                    if openai_api_key and assistant_id:
                        logger.info(f"Reviewing translation for page {page_num + 1} with OpenAI")
                        try:
                            reviewed_text = review_translation(
                                translated_text,
                                openai_api_key,
                                assistant_id
                            )
                        except Exception as e:
                            logger.error(f"OpenAI review error for page {page_num + 1}: {str(e)}")
                            # Keep using the DeepL translation (no need to raise an error)
                            logger.info(f"Using DeepL translation without OpenAI review for page {page_num + 1}")
                    else:
                        logger.info(f"OpenAI review skipped for page {page_num + 1} (using DeepL translation only)")

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