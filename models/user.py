from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    avatar_path = db.Column(db.String(512), nullable=True)   # stored filename under static/avatars/
    bio = db.Column(db.Text, nullable=True)
    storage_used = db.Column(db.BigInteger, default=0)
    storage_limit = db.Column(db.BigInteger, default=1073741824)  # 1 GB
    dark_mode = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    files = db.relationship('File', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    shares_created = db.relationship('Share', backref='creator', lazy='dynamic', foreign_keys='Share.created_by')
    snippets = db.relationship('TextSnippet', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def storage_percent(self):
        if self.storage_limit == 0:
            return 0
        return min(int((self.storage_used / self.storage_limit) * 100), 100)

    def storage_used_human(self):
        return _human_size(self.storage_used)

    def storage_limit_human(self):
        return _human_size(self.storage_limit)

    def avatar_url(self):
        if self.avatar_path:
            return f'/static/avatars/{self.avatar_path}'
        return None

    def __repr__(self):
        return f'<User {self.username}>'


class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        row = SiteSettings.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SiteSettings.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            row = SiteSettings(key=key, value=value)
            db.session.add(row)
        db.session.commit()


def _human_size(size):
    if not size:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
