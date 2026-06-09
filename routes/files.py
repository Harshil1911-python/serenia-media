import os
import secrets
import mimetypes
from datetime import datetime, timedelta
from flask import (render_template, redirect, url_for, flash, request,
                   jsonify, send_file, abort, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db
from models.user import User
from models.file import File, Share, Activity, Favorite
from routes import files_bp


ALLOWED_ALL = {
    'png','jpg','jpeg','gif','webp','bmp','svg',
    'mp4','mov','avi','mkv','webm','flv',
    'mp3','wav','aac','ogg','flac','m4a',
    'pdf','doc','docx','xls','xlsx','ppt','pptx',
    'zip','tar','gz','rar','7z',
    'txt','md','csv','json','xml','html','css','js','py','java','c','cpp',
    'ico','m4v','wma','odt','ods','odp','bz2',
}

TYPE_MAP = {
    'png':'image','jpg':'image','jpeg':'image','gif':'image','webp':'image',
    'bmp':'image','svg':'image','ico':'image',
    'mp4':'video','mov':'video','avi':'video','mkv':'video','webm':'video',
    'flv':'video','m4v':'video',
    'mp3':'audio','wav':'audio','aac':'audio','ogg':'audio','flac':'audio',
    'm4a':'audio','wma':'audio',
    'pdf':'document','doc':'document','docx':'document','xls':'document',
    'xlsx':'document','ppt':'document','pptx':'document','odt':'document',
    'ods':'document','odp':'document',
    'zip':'archive','tar':'archive','gz':'archive','rar':'archive',
    '7z':'archive','bz2':'archive',
    'txt':'text','md':'text','csv':'text','json':'text','xml':'text',
    'html':'text','css':'text','js':'text','py':'text','java':'text',
    'c':'text','cpp':'text',
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_ALL


def get_upload_folder():
    folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.isabs(folder):
        folder = os.path.join(current_app.root_path, folder)
    os.makedirs(folder, exist_ok=True)
    return folder


def log_activity(user_id, action, target_type=None, target_id=None, target_name=None, details=None):
    act = Activity(
        user_id=user_id, action=action, target_type=target_type,
        target_id=target_id, target_name=target_name, details=details,
        ip_address=request.remote_addr
    )
    db.session.add(act)


@files_bp.route('/files')
@login_required
def list_files():
    page = request.args.get('page', 1, type=int)
    file_type = request.args.get('type', '')
    sort = request.args.get('sort', 'date')
    q = request.args.get('q', '')

    query = File.query.filter_by(user_id=current_user.id, is_deleted=False)
    if file_type:
        query = query.filter_by(file_type=file_type)
    if q:
        query = query.filter(File.original_filename.ilike(f'%{q}%'))

    if sort == 'name':
        query = query.order_by(File.original_filename)
    elif sort == 'size':
        query = query.order_by(File.file_size.desc())
    elif sort == 'type':
        query = query.order_by(File.file_type)
    else:
        query = query.order_by(File.created_at.desc())

    files = query.paginate(page=page, per_page=24, error_out=False)
    return render_template('files/list.html', files=files, file_type=file_type, sort=sort, q=q)


@files_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        uploaded_files_list = request.files.getlist('files')
        results = []
        upload_folder = get_upload_folder()

        for f in uploaded_files_list:
            if not f or not f.filename:
                continue
            if not allowed_file(f.filename):
                results.append({'name': f.filename, 'error': 'File type not allowed'})
                continue

            # Check storage limit
            f.seek(0, 2)
            file_size = f.tell()
            f.seek(0)

            if current_user.storage_used + file_size > current_user.storage_limit:
                results.append({'name': f.filename, 'error': 'Storage limit exceeded'})
                continue

            original = secure_filename(f.filename)
            ext = original.rsplit('.', 1)[1].lower() if '.' in original else ''
            unique_name = f"{secrets.token_hex(16)}.{ext}" if ext else secrets.token_hex(16)
            file_path = os.path.join(upload_folder, unique_name)
            f.save(file_path)

            mime = mimetypes.guess_type(original)[0] or 'application/octet-stream'
            file_type = TYPE_MAP.get(ext, 'other')

            db_file = File(
                filename=unique_name,
                original_filename=original,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime,
                file_type=file_type,
                extension=ext,
                user_id=current_user.id
            )
            db.session.add(db_file)
            current_user.storage_used += file_size
            log_activity(current_user.id, 'upload', 'file', None, original)
            results.append({'name': original, 'success': True})

        db.session.commit()
        return jsonify({'results': results})

    return render_template('files/upload.html')


@files_bp.route('/files/<int:file_id>')
@login_required
def file_detail(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    f.view_count += 1
    f.last_accessed = datetime.utcnow()
    db.session.commit()
    shares = Share.query.filter_by(file_id=file_id, created_by=current_user.id).all()
    is_fav = Favorite.query.filter_by(user_id=current_user.id, file_id=file_id).first() is not None
    return render_template('files/detail.html', file=f, shares=shares, is_fav=is_fav)


@files_bp.route('/files/<int:file_id>/download')
@login_required
def download(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    if not os.path.exists(f.file_path):
        abort(404)
    f.download_count += 1
    log_activity(current_user.id, 'download', 'file', file_id, f.original_filename)
    db.session.commit()
    return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)


@files_bp.route('/files/<int:file_id>/rename', methods=['POST'])
@login_required
def rename(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id, is_deleted=False).first_or_404()
    new_name = request.json.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Name required'}), 400
    old_name = f.original_filename
    f.original_filename = secure_filename(new_name)
    f.updated_at = datetime.utcnow()
    log_activity(current_user.id, 'rename', 'file', file_id, f"{old_name} → {new_name}")
    db.session.commit()
    return jsonify({'ok': True, 'name': f.original_filename})


@files_bp.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    f.is_deleted = True
    f.updated_at = datetime.utcnow()
    log_activity(current_user.id, 'delete', 'file', file_id, f.original_filename)
    db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/files/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    ids = request.json.get('ids', [])
    count = 0
    for fid in ids:
        f = File.query.filter_by(id=fid, user_id=current_user.id).first()
        if f:
            f.is_deleted = True
            count += 1
    db.session.commit()
    return jsonify({'ok': True, 'count': count})


@files_bp.route('/files/<int:file_id>/tags', methods=['POST'])
@login_required
def update_tags(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    tags = request.json.get('tags', '')
    f.tags = tags
    db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/files/<int:file_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(file_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, file_id=file_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'ok': True, 'favorited': False})
    else:
        fav = Favorite(user_id=current_user.id, file_id=file_id)
        db.session.add(fav)
        db.session.commit()
        return jsonify({'ok': True, 'favorited': True})


# ── Sharing ──────────────────────────────────────────────────────────────────

@files_bp.route('/files/<int:file_id>/share', methods=['POST'])
@login_required
def create_share(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id, is_deleted=False).first_or_404()

    expires_in = request.json.get('expires_in')  # hours or None
    is_public = request.json.get('is_public', True)
    allow_download = request.json.get('allow_download', True)
    max_accesses = request.json.get('max_accesses')

    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(hours=int(expires_in))

    share = Share(
        token=secrets.token_urlsafe(32),
        file_id=file_id,
        created_by=current_user.id,
        is_public=is_public,
        allow_download=allow_download,
        expires_at=expires_at,
        max_accesses=max_accesses,
    )
    db.session.add(share)
    log_activity(current_user.id, 'share', 'file', file_id, f.original_filename)
    db.session.commit()
    share_url = url_for('files.shared_file', token=share.token, _external=True)
    return jsonify({'ok': True, 'url': share_url, 'token': share.token})


@files_bp.route('/share/<token>')
def shared_file(token):
    share = Share.query.filter_by(token=token).first_or_404()
    if not share.is_valid():
        abort(410)
    f = share.file
    if f.is_deleted:
        abort(404)
    share.access_count += 1
    db.session.commit()
    return render_template('files/shared.html', share=share, file=f)


@files_bp.route('/share/<token>/download')
def shared_download(token):
    share = Share.query.filter_by(token=token).first_or_404()
    if not share.is_valid() or not share.allow_download:
        abort(403)
    f = share.file
    if f.is_deleted or not os.path.exists(f.file_path):
        abort(404)
    f.download_count += 1
    db.session.commit()
    return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)


@files_bp.route('/shares')
@login_required
def my_shares():
    shares = Share.query.filter_by(created_by=current_user.id).order_by(Share.created_at.desc()).all()
    return render_template('files/shares.html', shares=shares)


@files_bp.route('/shares/<int:share_id>/delete', methods=['POST'])
@login_required
def delete_share(share_id):
    share = Share.query.filter_by(id=share_id, created_by=current_user.id).first_or_404()
    db.session.delete(share)
    db.session.commit()
    return jsonify({'ok': True})


# ── QR Code ──────────────────────────────────────────────────────────────────

@files_bp.route('/share/<token>/qr')
def share_qr(token):
    import qrcode, io
    from flask import send_file as sf
    share = Share.query.filter_by(token=token).first_or_404()
    url = url_for('files.shared_file', token=token, _external=True)
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return sf(buf, mimetype='image/png')


# ── Preview ───────────────────────────────────────────────────────────────────

@files_bp.route('/files/<int:file_id>/preview')
@login_required
def preview(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    if not os.path.exists(f.file_path):
        abort(404)
    if f.file_type == 'text' and f.file_size < 1048576:
        with open(f.file_path, 'r', errors='replace') as fh:
            content = fh.read()
        return jsonify({'type': 'text', 'content': content})
    return send_file(f.file_path, mimetype=f.mime_type or 'application/octet-stream')
