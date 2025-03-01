# Models for BookTranslationPro application

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class Assistant:
    """Model representing an OpenAI assistant configuration for a specific author"""
    def __init__(self, id, user_id, name, assistant_id, author, genre, instructions, created_at=None, updated_at=None):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.assistant_id = assistant_id
        self.author = author
        self.genre = genre
        self.instructions = instructions
        self.created_at = created_at
        self.updated_at = updated_at
        
    def to_dict(self):
        """Convert assistant object to dictionary for storage"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'assistant_id': self.assistant_id,
            'author': self.author,
            'genre': self.genre,
            'instructions': self.instructions,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
    @classmethod
    def from_dict(cls, data):
        """Create assistant object from dictionary"""
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            name=data.get('name'),
            assistant_id=data.get('assistant_id'),
            author=data.get('author'),
            genre=data.get('genre'),
            instructions=data.get('instructions'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )