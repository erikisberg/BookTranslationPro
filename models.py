from datetime import datetime
from database import db

class TranslationMemory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    source_language = db.Column(db.String(10), default='EN')
    target_language = db.Column(db.String(10), default='SV')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    use_count = db.Column(db.Integer, default=1)

    def __repr__(self):
        return f'<TranslationMemory {self.id}>'