#!/usr/bin/env python
"""
Script to create a default OpenAI assistant for translation review.
This creates a basic assistant that can be used for translation review.
The assistant ID will be printed to stdout for use in environment variables.
"""

import os
import sys
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default translation review instructions
DEFAULT_INSTRUCTIONS = """
You are a professional translation reviewer helping to refine book translations.

Your task:
1. Review the provided text that has been translated to Swedish (or other target language)
2. Improve the translation by making it more natural, idiomatic, and faithful to the original style
3. Correct any errors, awkward phrasing, or literal translations that don't work well
4. Ensure terms are used consistently throughout the text
5. Preserve the author's original tone, style and voice in the target language
6. If the text already seems high quality, return it unchanged

Important guidelines:
- Focus on making the translation read naturally in the target language
- Preserve cultural references but adapt them when necessary
- Pay special attention to idioms, metaphors, and figurative language
- Maintain consistent tense, perspective, and terminology
- Avoid introducing new information that wasn't in the original
- Respect the text's register (formal/informal) and genre

If you detect any serious errors or misunderstandings in the translation, mark them clearly but always provide a corrected version.

Return ONLY the improved translation text without explanation, notes, or your thinking process.
"""

def create_assistant(api_key, name="Translation Assistant", instructions=DEFAULT_INSTRUCTIONS, model="gpt-4o"):
    """Create a new OpenAI assistant for translation review."""
    try:
        client = OpenAI(api_key=api_key)
        
        # Create the assistant
        assistant = client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=model,
            tools=[]  # No tools needed for translation review
        )
        
        logger.info(f"Successfully created assistant with ID: {assistant.id}")
        return assistant.id
    except Exception as e:
        logger.error(f"Error creating OpenAI assistant: {str(e)}")
        return None

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment or argument
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    if not api_key:
        print("Error: OpenAI API key not provided. Please provide as argument or set OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Create the assistant
    assistant_id = create_assistant(api_key)
    
    if assistant_id:
        print("\nAssistant created successfully!")
        print(f"\nAssistant ID: {assistant_id}")
        print("\nAdd this to your .env file:")
        print(f"OPENAI_ASSISTANT_ID={assistant_id}")
    else:
        print("Failed to create assistant. Check the error log above.")
        sys.exit(1)