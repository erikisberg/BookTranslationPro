# InkAssist Guidelines

## Commands
- **Run server**: `python app.py` or `gunicorn main:app -c gunicorn_config.py` for production
- **Environment**: Set up with `pip install -r requirements.txt`
- **Reload server**: `touch main.py` to trigger gunicorn reload

## Code Style
- **Imports**: Group standard lib, third-party, and local imports with blank lines
- **Logging**: Use module logger (`logger = logging.getLogger(__name__)`) for errors and information
- **Error handling**: Use try/except blocks with specific error logging
- **Function structure**: Document with docstrings, validate inputs first, use early returns
- **Naming**: snake_case for functions/variables, CamelCase for classes, UPPER_CASE for constants
- **API handling**: Check for empty responses, validate data, handle API failures gracefully
- **Security**: Never expose API keys in logs or responses, sanitize user inputs

## Architecture
- Flask-based web application with Supabase for authentication and data storage
- Separate modules for authentication (auth.py), database (supabase_config.py), and utilities (utils.py)
- Use environment variables (.env) for configuration and sensitive data