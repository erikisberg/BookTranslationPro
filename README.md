# BookTranslationPro

A comprehensive PDF book translation application that extracts text, translates with DeepL, reviews with OpenAI, and exports to multiple formats.

## Features

- **PDF Text Extraction**: Extract text from PDF documents with PyPDF2
- **Professional Translation**: High-quality translation using DeepL API
- **AI-Powered Review**: Enhanced translation quality with OpenAI review
- **Multiple Export Formats**: PDF, DOCX, HTML and TXT with customizable formatting
- **User Authentication**: Complete user system with Supabase integration
- **Translation History**: Save and browse past translations
- **Export Settings**: Personalized export preferences saved to user profiles
- **Usage Analytics**: User behavior tracking with PostHog

## Setup

1. Install dependencies
```
pip install -r requirements.txt
```

2. Set environment variables
```
# API Keys
DEEPL_API_KEY=your_deepl_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_ASSISTANT_ID=your_openai_assistant_id

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_API_KEY=your_supabase_key

# Session Security
SESSION_SECRET=your_session_secret_key

# PostHog Analytics (optional)
POSTHOG_API_KEY=your_posthog_key
POSTHOG_HOST=https://app.posthog.com
```

3. Run the application
```
python app.py
```

For production deployment, use Gunicorn:
```
gunicorn -c gunicorn_config.py app:app
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.