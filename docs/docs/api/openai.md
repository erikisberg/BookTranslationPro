# OpenAI Integration

BookTranslationPro uses OpenAI's API for AI-assisted translation review and quality improvement.

## Overview

The OpenAI integration enables:

1. AI-assisted review of translated content
2. Consistency checking across translations
3. Terminology validation against glossaries
4. Style and tone suggestions for literary translations

## API Configuration

### Required Environment Variables

```
OPENAI_API_KEY=your_openai_api_key
```

### OpenAI Assistant Configuration

The application uses OpenAI's Assistants API to create specialized translation reviewers:

```python
def create_assistant(user_id, name, instructions, author=None, genre=None):
    """
    Creates an OpenAI assistant configured for translation review
    
    Args:
        user_id (str): User ID who owns this assistant
        name (str): Name of the assistant
        instructions (str): Instructions for the assistant
        author (str, optional): Author style to emulate
        genre (str, optional): Genre of content being translated
        
    Returns:
        str: Assistant ID from OpenAI
    """
    client = OpenAI()
    
    # Construct full instructions with translation-specific guidance
    full_instructions = f"""
    You are a translation reviewer specialized in {genre or 'general'} content.
    {f'Please review translations in the style of {author}.' if author else ''}
    
    {instructions}
    
    When reviewing translations:
    1. Check for accuracy against the source text
    2. Verify terminology consistency
    3. Evaluate stylistic appropriateness
    4. Suggest improvements where needed
    """
    
    # Create the assistant via OpenAI API
    assistant = client.beta.assistants.create(
        name=name,
        instructions=full_instructions,
        model="gpt-4-turbo-preview",
    )
    
    # Store assistant information in database
    assistant_id = assistant.id
    # [Database operations here]
    
    return assistant_id
```

## Review Process Implementation

The review process follows these steps:

1. User requests a review of a translated page
2. System retrieves original and translated text
3. Creates a thread with the OpenAI Assistant
4. Sends the content for review with appropriate instructions
5. Processes and displays the feedback to the user

```python
def review_translation(page_id, user_id):
    """
    Reviews a translation using OpenAI assistant
    
    Args:
        page_id (str): ID of the page to review
        user_id (str): User ID requesting the review
        
    Returns:
        dict: Review results with suggestions and score
    """
    # Get page content and assistant configuration
    page = get_page_by_id(page_id)
    assistant_config = get_user_assistant(user_id)
    
    # Create thread and run review
    client = OpenAI()
    thread = client.beta.threads.create()
    
    # Add messages to thread
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"""
        Please review this translation:
        
        Source text (original):
        {page['source_text']}
        
        Translated text:
        {page['translated_text']}
        
        Focus on accuracy, style, and terminology.
        """
    )
    
    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_config.assistant_id,
    )
    
    # Wait for completion and get results
    run = wait_for_run_completion(client, thread.id, run.id)
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    
    # Process and return results
    return process_review_results(messages.data)
```

## Error Handling

The OpenAI integration includes robust error handling:

```python
def send_to_openai_with_retry(func, *args, max_retries=3, **kwargs):
    """
    Execute an OpenAI API call with retry logic
    
    Args:
        func: The OpenAI API function to call
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response from the API call
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            return func(*args, **kwargs)
        except RateLimitError:
            retry_count += 1
            sleep_time = 2 ** retry_count  # Exponential backoff
            time.sleep(sleep_time)
        except APIError as e:
            if e.http_status == 500:
                retry_count += 1
                time.sleep(1)
            else:
                raise
    
    # If we've exhausted retries
    raise Exception(f"Failed after {max_retries} retries")
```

## API Limits and Performance

To prevent excessive API usage and costs:

1. Reviews are rate-limited per user
2. Cached responses are used for similar content
3. Batch processing is used for multi-page reviews
4. Results are stored in the database to avoid redundant calls

## Response Processing

The system processes OpenAI's responses to extract actionable feedback:

```python
def process_review_results(messages):
    """
    Process OpenAI assistant messages into structured feedback
    
    Args:
        messages: List of messages from the assistant
        
    Returns:
        dict: Structured review data
    """
    # Extract assistant's response (last message from assistant)
    assistant_messages = [m for m in messages if m.role == "assistant"]
    if not assistant_messages:
        return {"error": "No response from assistant"}
    
    review_text = assistant_messages[-1].content[0].text.value
    
    # Parse the review into categories
    review_data = {
        "accuracy": extract_category(review_text, "Accuracy"),
        "style": extract_category(review_text, "Style"),
        "terminology": extract_category(review_text, "Terminology"),
        "suggestions": extract_suggestions(review_text),
        "overall_score": extract_score(review_text)
    }
    
    return review_data
```

## Related Components

- **Translation Module**: Provides context and source/target text for review
- **User Interface**: Displays review results and suggestions
- **Assistant Configuration**: Allows customization of review parameters