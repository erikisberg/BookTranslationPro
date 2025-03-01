# BookTranslationPro

A comprehensive PDF book translation application that extracts text, translates with DeepL, reviews with OpenAI, and exports to multiple formats.

## Features

- **PDF Text Extraction**: Extract text from PDF documents with PyPDF2
- **Professional Translation**: High-quality translation using DeepL API with language selection
- **AI-Powered Review**: Enhanced translation quality with OpenAI review
- **Multiple Export Formats**: PDF, DOCX, HTML and TXT with customizable formatting
- **User Authentication**: Complete user system with Supabase integration
- **Translation History**: Save and browse past translations
- **Export Settings**: Personalized export preferences saved to user profiles
- **Custom API Keys**: Use your own DeepL and OpenAI API keys
- **Language Selection**: Choose source and target languages for translation
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
gunicorn main:app -c gunicorn_config.py
```

## User Guide

### Translation Process
1. Upload your PDF file on the home page
2. Select source and target languages 
3. Choose whether to use OpenAI review (optional)
4. Review the translated text and make any edits
5. Download the finished translation in your preferred format

### API Keys
You can use your own API keys for DeepL and OpenAI:
1. Go to your profile page
2. Click on "API-nycklar" in the settings section
3. Enter your personal API keys
4. Save your settings

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.