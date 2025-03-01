from functools import wraps
from flask import session, redirect, url_for, flash, request
from supabase_config import supabase

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Logga in för att fortsätta', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user from session"""
    return session.get('user', None)

def get_user_id():
    """Get current user ID"""
    user = get_current_user()
    return user.get('id') if user else None

def sign_up(email, password, metadata=None):
    """Register a new user"""
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": metadata or {}
            }
        })
        return response
    except Exception as e:
        print(f"Error signing up: {e}")
        return None

def sign_in(email, password):
    """Sign in an existing user"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response
    except Exception as e:
        print(f"Error signing in: {e}")
        return None

def sign_out():
    """Sign out the current user"""
    try:
        supabase.auth.sign_out()
        return True
    except Exception as e:
        print(f"Error signing out: {e}")
        return False
        
def reset_password(email):
    """Send password reset email"""
    try:
        supabase.auth.reset_password_for_email(email)
        return True
    except Exception as e:
        print(f"Error resetting password: {e}")
        return False