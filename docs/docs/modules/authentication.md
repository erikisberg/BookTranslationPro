# Authentication Module

The authentication module in BookTranslationPro handles user identity management, authorization, and session control using Supabase Auth.

## Architecture

The authentication system consists of several components:

```
┌───────────────────────────────────────────────────┐
│                Authentication Module               │
├─────────────┬───────────────┬────────────────────┤
│ User        │  Session      │  Permission        │
│ Management  │  Management   │  Control           │
├─────────────┼───────────────┼────────────────────┤
│ Password    │  Email        │  Security          │
│ Management  │  Verification │  Features          │
└─────────────┴───────────────┴────────────────────┘
```

## Implementation

The authentication module is implemented in `auth.py` and integrates with Supabase's authentication services.

### User Management

```python
def sign_up(email, password, name):
    """
    Register a new user
    
    Args:
        email (str): User's email address
        password (str): User's password
        name (str): User's display name
        
    Returns:
        dict: User data on success or error message
    """
    try:
        # Register user with Supabase
        result = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        # Get the new user ID
        user_id = result.user.id
        
        # Store additional user information in the profile table
        supabase.table("profiles").insert({
            "id": user_id,
            "name": name,
            "email": email,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return {"success": True, "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Sign-up error: {e}")
        return {"success": False, "error": str(e)}
```

### Session Management

```python
def sign_in(email, password):
    """
    Authenticate a user and create a session
    
    Args:
        email (str): User's email address
        password (str): User's password
        
    Returns:
        dict: Session data on success or error message
    """
    try:
        # Authenticate with Supabase
        result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Set session data in Flask
        session['access_token'] = result.session.access_token
        session['user_id'] = result.user.id
        session['email'] = result.user.email
        
        return {"success": True, "user_id": result.user.id}
        
    except Exception as e:
        logger.error(f"Sign-in error: {e}")
        return {"success": False, "error": str(e)}
```

### Authorization Decorator

The module provides a decorator for route protection:

```python
def login_required(view_function):
    """
    Decorator to require login for a route
    
    Args:
        view_function: The route function to protect
        
    Returns:
        function: Wrapped function that checks authentication
    """
    @functools.wraps(view_function)
    def wrapped_view(*args, **kwargs):
        # Check if user is logged in
        if 'user_id' not in session:
            # Redirect to login page
            return redirect(url_for('login', next=request.url))
            
        # User is authenticated, proceed
        return view_function(*args, **kwargs)
        
    return wrapped_view
```

### Password Management

```python
def reset_password(email):
    """
    Initiate password reset process
    
    Args:
        email (str): User's email address
        
    Returns:
        dict: Success or error message
    """
    try:
        # Send password reset email via Supabase
        supabase.auth.reset_password_email(email)
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        return {"success": False, "error": str(e)}
```

### Session Expiry and Refresh

```python
def refresh_session():
    """
    Refresh the user's session token
    
    Returns:
        bool: True if refreshed successfully
    """
    try:
        # Check for existing session
        if 'access_token' not in session:
            return False
            
        # Refresh the session with Supabase
        result = supabase.auth.refresh_session()
        
        # Update session data
        session['access_token'] = result.session.access_token
        return True
        
    except Exception as e:
        logger.error(f"Session refresh error: {e}")
        # Clear invalid session
        session.clear()
        return False
```

## Security Features

### CSRF Protection

```python
# In app.py
csrf = CSRFProtect()
csrf.init_app(app)

# In forms
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
```

### Password Security

- Passwords are never stored in plaintext
- Supabase handles password hashing and security
- Password complexity requirements are enforced:
  - Minimum 8 characters
  - Mix of uppercase, lowercase, and numbers

### Session Security

```python
# In app.py
app.config['SESSION_COOKIE_SECURE'] = True  # For HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript access
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session timeout
```

## Error Handling

The auth module implements robust error handling for authentication failures:

```python
def handle_auth_errors(error_message):
    """
    Process authentication error messages
    
    Args:
        error_message (str): Raw error message
        
    Returns:
        str: User-friendly error message
    """
    if "invalid login credentials" in error_message.lower():
        return "Invalid email or password. Please try again."
    elif "user already registered" in error_message.lower():
        return "This email address is already registered."
    elif "email not confirmed" in error_message.lower():
        return "Please confirm your email address before logging in."
    else:
        # Log the unexpected error
        logger.error(f"Unexpected authentication error: {error_message}")
        return "An authentication error occurred. Please try again later."
```

## Integration Points

The authentication module integrates with several other components:

- **Flask Application**: Provides session management and route protection
- **Supabase**: Handles the actual authentication logic and user storage
- **User Interface**: Login, signup, and password reset forms
- **Profile System**: User profile data linked to authentication records

## User Flows

### Sign-up Flow

1. User submits signup form with email, password, and name
2. System validates input and checks for existing accounts
3. Supabase creates the user and sends verification email
4. User profile record is created in database
5. User is redirected to email verification notice

### Login Flow

1. User submits login form with email and password
2. System validates credentials against Supabase
3. On success, session is created with appropriate tokens
4. User is redirected to their dashboard
5. On failure, appropriate error message is displayed

### Password Reset Flow

1. User requests password reset with email
2. System sends reset email via Supabase
3. User clicks link in email
4. User sets new password
5. Session is updated with new credentials