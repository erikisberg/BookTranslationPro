# Installation Guide

This guide provides step-by-step instructions for setting up BookTranslationPro for development or production use.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL database (or Supabase account)
- DeepL API key (for translation)
- OpenAI API key (for AI review)
- PostHog API key (optional, for analytics)

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/BookTranslationPro.git
cd BookTranslationPro
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root with the following variables:

```plaintext
# Database Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_KEY=your_supabase_service_key

# Translation APIs
DEEPL_API_KEY=your_deepl_api_key
OPENAI_API_KEY=your_openai_api_key

# Application Settings
SECRET_KEY=your_flask_secret_key
DEBUG=True

# Optional: Analytics
POSTHOG_API_KEY=your_posthog_api_key
```

### 5. Initialize the Database

```bash
python -c "from app import create_tables; create_tables()"
# Or use Supabase SQL Editor to run the setup_tables.sql script
```

### 6. Run the Development Server

```bash
python app.py
```

The application will be available at `http://localhost:5000`.

## Production Deployment

For production deployments, additional configurations are recommended:

### Using Gunicorn

```bash
gunicorn main:app -c gunicorn_config.py
```

### Environment Settings

For production, update your `.env` file:

```plaintext
DEBUG=False
SECRET_KEY=your_secure_secret_key  # Generate a strong key
```

### Database Considerations

- Set up proper database indexes for performance
- Configure database connection pool size in `supabase_config.py`
- Consider setting up database backups

### Security Recommendations

- Use HTTPS via a reverse proxy (Nginx, Apache)
- Set secure cookie settings in production
- Configure proper content security policy headers
- Regularly update dependencies

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify Supabase credentials
   - Check network connectivity to Supabase

2. **API Integration Failures**
   - Validate API keys
   - Check API rate limits
   - Review error logs for specific issues

3. **Document Processing Issues**
   - Install necessary system dependencies for PDF extraction
   - Check file permissions for temporary file directories

### Logging

The application uses Python's logging system. To increase verbosity:

```python
# In app.py or by setting environment variables
import logging
logging.basicConfig(level=logging.DEBUG)
```

Logs can help identify issues with API integrations, file processing, or database operations.