from datetime import datetime
import os
from models import db


class Folder(db.Model):
    __tablename__ = 'folders'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(255), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id  = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    color      = db.Column(db.String(20), default='#87CEEB')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children   = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    files      = db.relationship('File', backref='folder', lazy='dynamic')

    def file_count(self):
        return File.query.filter_by(folder_id=self.id, is_deleted=False).count()

    def total_size(self):
        from sqlalchemy import func
        result = db.session.query(func.sum(File.file_size)).filter_by(folder_id=self.id, is_deleted=False).scalar()
        return result or 0

    def size_human(self):
        return _human_size(self.total_size())

    def __repr__(self):
        return f'<Folder {self.name}>'


class File(db.Model):
    __tablename__ = 'files'

    id                = db.Column(db.Integer, primary_key=True)
    filename          = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path         = db.Column(db.String(512), nullable=False)
    file_size         = db.Column(db.BigInteger, default=0)
    mime_type         = db.Column(db.String(100), nullable=True)
    file_type         = db.Column(db.String(50), nullable=True)
    extension         = db.Column(db.String(20), nullable=True)
    description       = db.Column(db.Text, nullable=True)
    tags              = db.Column(db.String(512), nullable=True)
    is_deleted        = db.Column(db.Boolean, default=False)
    is_favorite       = db.Column(db.Boolean, default=False)
    download_count    = db.Column(db.Integer, default=0)
    view_count        = db.Column(db.Integer, default=0)
    version           = db.Column(db.Integer, default=1)
    folder_id         = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed     = db.Column(db.DateTime, nullable=True)

    shares       = db.relationship('Share', backref='file', lazy='dynamic', cascade='all, delete-orphan')
    favorites_rel= db.relationship('Favorite', backref='file', lazy='dynamic', cascade='all, delete-orphan')

    def size_human(self):
        return _human_size(self.file_size)

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []

    def icon_class(self):
        icons = {
            'image':    'fa-image',
            'video':    'fa-video',
            'audio':    'fa-music',
            'document': 'fa-file-alt',
            'archive':  'fa-file-archive',
            'text':     'fa-file-code',
        }
        return icons.get(self.file_type, 'fa-file')

    def is_previewable(self):
        return self.file_type in ('image', 'video', 'audio', 'text') or self.extension == 'pdf'

    def __repr__(self):
        return f'<File {self.original_filename}>'


class Share(db.Model):
    __tablename__ = 'shares'

    id           = db.Column(db.Integer, primary_key=True)
    token        = db.Column(db.String(64), unique=True, nullable=False, index=True)
    file_id      = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shared_with  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_public    = db.Column(db.Boolean, default=True)
    allow_download= db.Column(db.Boolean, default=True)
    password     = db.Column(db.String(128), nullable=True)
    expires_at   = db.Column(db.DateTime, nullable=True)
    access_count = db.Column(db.Integer, default=0)
    max_accesses = db.Column(db.Integer, nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    shared_with_user = db.relationship('User', foreign_keys=[shared_with])

    def is_expired(self):
        return bool(self.expires_at and datetime.utcnow() > self.expires_at)

    def is_valid(self):
        if self.is_expired(): return False
        if self.max_accesses and self.access_count >= self.max_accesses: return False
        return True


class TextSnippet(db.Model):
    __tablename__ = 'text_snippets'

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(255), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    language   = db.Column(db.String(50), nullable=True)
    is_public  = db.Column(db.Boolean, default=False)
    token      = db.Column(db.String(64), unique=True, nullable=True, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(db.Model):
    __tablename__ = 'favorites'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id    = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'file_id', name='unique_favorite'),)


class Activity(db.Model):
    __tablename__ = 'activities'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action      = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id   = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(255), nullable=True)
    details     = db.Column(db.Text, nullable=True)
    ip_address  = db.Column(db.String(45), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Activity {self.action} by user {self.user_id}>'


def _human_size(size):
    if not size: return '0 B'
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024.0: return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
