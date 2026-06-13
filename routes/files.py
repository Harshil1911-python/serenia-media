import os, secrets, mimetypes, zipfile, io, tempfile
from datetime import datetime, timedelta
from flask import (render_template, redirect, url_for, flash, request,
                   jsonify, send_file, abort, current_app, after_this_request)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db
from models.user import User
from models.file import File, Share, Activity, Favorite, Folder
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
    'png':'image','jpg':'image','jpeg':'image','gif':'image','webp':'image','bmp':'image','svg':'image','ico':'image',
    'mp4':'video','mov':'video','avi':'video','mkv':'video','webm':'video','flv':'video','m4v':'video',
    'mp3':'audio','wav':'audio','aac':'audio','ogg':'audio','flac':'audio','m4a':'audio','wma':'audio',
    'pdf':'document','doc':'document','docx':'document','xls':'document','xlsx':'document',
    'ppt':'document','pptx':'document','odt':'document','ods':'document','odp':'document',
    'zip':'archive','tar':'archive','gz':'archive','rar':'archive','7z':'archive','bz2':'archive',
    'txt':'text','md':'text','csv':'text','json':'text','xml':'text','html':'text',
    'css':'text','js':'text','py':'text','java':'text','c':'text','cpp':'text',
}

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_ALL

def get_upload_folder():
    folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.isabs(folder):
        folder = os.path.join(current_app.root_path, folder)
    os.makedirs(folder, exist_ok=True)
    return folder

def log_activity(user_id, action, target_type=None, target_id=None, target_name=None):
    act = Activity(user_id=user_id, action=action, target_type=target_type,
                   target_id=target_id, target_name=target_name,
                   ip_address=request.remote_addr)
    db.session.add(act)


# ── File listing ──────────────────────────────────────────────────────────
@files_bp.route('/files')
@login_required
def list_files():
    page      = request.args.get('page', 1, type=int)
    file_type = request.args.get('type', '')
    sort      = request.args.get('sort', 'date')
    q         = request.args.get('q', '')
    folder_id = request.args.get('folder_id', None, type=int)

    # breadcrumb chain
    breadcrumb = []
    current_folder = None
    if folder_id:
        current_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
        f = current_folder
        while f:
            breadcrumb.insert(0, f)
            f = f.parent

    # subfolders in current folder
    subfolders = Folder.query.filter_by(
        user_id=current_user.id,
        parent_id=folder_id,
        is_deleted=False
    ).order_by(Folder.name).all()

    # files query
    query = File.query.filter_by(user_id=current_user.id, is_deleted=False, folder_id=folder_id)
    if file_type: query = query.filter_by(file_type=file_type)
    if q:         query = query.filter(File.original_filename.ilike(f'%{q}%'))
    if sort == 'name': query = query.order_by(File.original_filename)
    elif sort == 'size': query = query.order_by(File.file_size.desc())
    elif sort == 'type': query = query.order_by(File.file_type)
    else: query = query.order_by(File.created_at.desc())

    files = query.paginate(page=page, per_page=24, error_out=False)

    # all user folders for move dropdown
    all_folders = Folder.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Folder.name).all()

    return render_template('files/list.html',
        files=files, file_type=file_type, sort=sort, q=q,
        subfolders=subfolders, current_folder=current_folder,
        breadcrumb=breadcrumb, folder_id=folder_id, all_folders=all_folders)


# ── Folders ───────────────────────────────────────────────────────────────
@files_bp.route('/folders/create', methods=['POST'])
@login_required
def create_folder():
    name      = request.json.get('name', '').strip()
    parent_id = request.json.get('parent_id')
    color     = request.json.get('color', '#87CEEB')
    if not name:
        return jsonify({'error': 'Name required'}), 400
    folder = Folder(name=name, user_id=current_user.id,
                    parent_id=parent_id or None, color=color)
    db.session.add(folder)
    db.session.commit()
    return jsonify({'ok': True, 'id': folder.id, 'name': folder.name, 'color': folder.color})


@files_bp.route('/folders/<int:folder_id>/rename', methods=['POST'])
@login_required
def rename_folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    folder.name = name
    db.session.commit()
    return jsonify({'ok': True, 'name': folder.name})


@files_bp.route('/folders/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    # soft-delete all files inside
    File.query.filter_by(folder_id=folder_id, user_id=current_user.id).update({'is_deleted': True})
    folder.is_deleted = True
    db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/folders/<int:folder_id>/color', methods=['POST'])
@login_required
def set_folder_color(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    folder.color = request.json.get('color', '#87CEEB')
    db.session.commit()
    return jsonify({'ok': True})


# ── Upload ────────────────────────────────────────────────────────────────
@files_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        folder_id     = request.form.get('folder_id') or None
        results       = []
        upload_folder = get_upload_folder()

        for f in request.files.getlist('files'):
            if not f or not f.filename: continue
            if not allowed_file(f.filename):
                results.append({'name': f.filename, 'error': 'File type not allowed'}); continue
            f.seek(0, 2); file_size = f.tell(); f.seek(0)
            if current_user.storage_used + file_size > current_user.storage_limit:
                results.append({'name': f.filename, 'error': 'Storage limit exceeded'}); continue

            original    = secure_filename(f.filename)
            ext         = original.rsplit('.', 1)[1].lower() if '.' in original else ''
            unique_name = f"{secrets.token_hex(16)}.{ext}" if ext else secrets.token_hex(16)
            file_path   = os.path.join(upload_folder, unique_name)
            f.save(file_path)

            mime      = mimetypes.guess_type(original)[0] or 'application/octet-stream'
            file_type = TYPE_MAP.get(ext, 'other')

            db_file = File(
                filename=unique_name, original_filename=original,
                file_path=file_path, file_size=file_size,
                mime_type=mime, file_type=file_type, extension=ext,
                user_id=current_user.id,
                folder_id=int(folder_id) if folder_id else None
            )
            db.session.add(db_file)
            current_user.storage_used += file_size
            log_activity(current_user.id, 'upload', 'file', None, original)
            results.append({'name': original, 'success': True})

        db.session.commit()
        return jsonify({'results': results})

    all_folders = Folder.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Folder.name).all()
    return render_template('files/upload.html', all_folders=all_folders)


# ── Move file to folder ───────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>/move', methods=['POST'])
@login_required
def move_file(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    folder_id = request.json.get('folder_id')
    f.folder_id = int(folder_id) if folder_id else None
    db.session.commit()
    return jsonify({'ok': True})


# ── Bulk move ─────────────────────────────────────────────────────────────
@files_bp.route('/files/bulk-move', methods=['POST'])
@login_required
def bulk_move():
    ids       = request.json.get('ids', [])
    folder_id = request.json.get('folder_id')
    for fid in ids:
        f = File.query.filter_by(id=fid, user_id=current_user.id).first()
        if f:
            f.folder_id = int(folder_id) if folder_id else None
    db.session.commit()
    return jsonify({'ok': True, 'count': len(ids)})


# ── Bulk download as ZIP ──────────────────────────────────────────────────
@files_bp.route('/files/bulk-download', methods=['POST'])
@login_required
def bulk_download():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'error': 'No files selected'}), 400

    files = File.query.filter(
        File.id.in_(ids),
        File.user_id == current_user.id,
        File.is_deleted == False
    ).all()

    if not files:
        return jsonify({'error': 'No valid files found'}), 404

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        seen_names = {}
        for f in files:
            if not os.path.exists(f.file_path):
                continue
            # handle duplicate filenames
            name = f.original_filename
            if name in seen_names:
                seen_names[name] += 1
                base, ext = os.path.splitext(name)
                name = f"{base} ({seen_names[name]}){ext}"
            else:
                seen_names[name] = 0
            zf.write(f.file_path, name)
            f.download_count += 1

    log_activity(current_user.id, 'bulk_download', 'files', None, f'{len(files)} files')
    db.session.commit()

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='serenia-download.zip'
    )


# ── Download folder as ZIP ────────────────────────────────────────────────
@files_bp.route('/folders/<int:folder_id>/download')
@login_required
def download_folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    files  = File.query.filter_by(folder_id=folder_id, user_id=current_user.id, is_deleted=False).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if os.path.exists(f.file_path):
                zf.write(f.file_path, f.original_filename)
                f.download_count += 1

    log_activity(current_user.id, 'download_folder', 'folder', folder_id, folder.name)
    db.session.commit()

    zip_buffer.seek(0)
    safe_name = secure_filename(folder.name) or 'folder'
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{safe_name}.zip'
    )


# ── Detail ────────────────────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>')
@login_required
def file_detail(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    f.view_count   += 1
    f.last_accessed = datetime.utcnow()
    db.session.commit()
    shares     = Share.query.filter_by(file_id=file_id, created_by=current_user.id).all()
    is_fav     = Favorite.query.filter_by(user_id=current_user.id, file_id=file_id).first() is not None
    all_folders= Folder.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Folder.name).all()
    return render_template('files/detail.html', file=f, shares=shares,
                           is_fav=is_fav, all_folders=all_folders)


# ── Download single ───────────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>/download')
@login_required
def download(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin: abort(403)
    if not os.path.exists(f.file_path): abort(404)
    f.download_count += 1
    log_activity(current_user.id, 'download', 'file', file_id, f.original_filename)
    db.session.commit()
    return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)


# ── Rename / delete / tags / fav / move ──────────────────────────────────
@files_bp.route('/files/<int:file_id>/rename', methods=['POST'])
@login_required
def rename(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id, is_deleted=False).first_or_404()
    new_name = request.json.get('name', '').strip()
    if not new_name: return jsonify({'error': 'Name required'}), 400
    f.original_filename = secure_filename(new_name)
    db.session.commit()
    return jsonify({'ok': True, 'name': f.original_filename})


@files_bp.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    f.is_deleted = True
    log_activity(current_user.id, 'delete', 'file', file_id, f.original_filename)
    db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/files/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    ids = request.json.get('ids', [])
    for fid in ids:
        f = File.query.filter_by(id=fid, user_id=current_user.id).first()
        if f: f.is_deleted = True
    db.session.commit()
    return jsonify({'ok': True, 'count': len(ids)})


@files_bp.route('/files/<int:file_id>/tags', methods=['POST'])
@login_required
def update_tags(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    f.tags = request.json.get('tags', '')
    db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/files/<int:file_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(file_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, file_id=file_id).first()
    if fav:
        db.session.delete(fav); db.session.commit()
        return jsonify({'ok': True, 'favorited': False})
    db.session.add(Favorite(user_id=current_user.id, file_id=file_id))
    db.session.commit()
    return jsonify({'ok': True, 'favorited': True})


# ── Sharing ───────────────────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>/share', methods=['POST'])
@login_required
def create_share(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id, is_deleted=False).first_or_404()
    expires_in   = request.json.get('expires_in')
    allow_dl     = request.json.get('allow_download', True)
    max_accesses = request.json.get('max_accesses')
    expires_at   = datetime.utcnow() + timedelta(hours=int(expires_in)) if expires_in else None
    share = Share(token=secrets.token_urlsafe(32), file_id=file_id,
                  created_by=current_user.id, is_public=True,
                  allow_download=allow_dl, expires_at=expires_at, max_accesses=max_accesses)
    db.session.add(share)
    log_activity(current_user.id, 'share', 'file', file_id, f.original_filename)
    db.session.commit()
    return jsonify({'ok': True,
                    'url': url_for('files.shared_file', token=share.token, _external=True),
                    'token': share.token})


@files_bp.route('/share/<token>')
def shared_file(token):
    share = Share.query.filter_by(token=token).first_or_404()
    if not share.is_valid(): abort(410)
    f = share.file
    if f.is_deleted: abort(404)
    share.access_count += 1
    db.session.commit()
    sender = User.query.get(share.created_by)
    text_content = None
    if f.file_type == 'text' and f.file_size < 1048576 and os.path.exists(f.file_path):
        try:
            with open(f.file_path, 'r', errors='replace') as fh:
                text_content = fh.read()
        except: pass
    return render_template('files/shared.html', share=share, file=f,
                           sender=sender, text_content=text_content)


@files_bp.route('/share/<token>/download')
def shared_download(token):
    share = Share.query.filter_by(token=token).first_or_404()
    if not share.is_valid() or not share.allow_download: abort(403)
    f = share.file
    if f.is_deleted or not os.path.exists(f.file_path): abort(404)
    f.download_count += 1
    db.session.commit()
    return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)


@files_bp.route('/shares')
@login_required
def my_shares():
    shares = Share.query.filter_by(created_by=current_user.id)\
              .order_by(Share.created_at.desc()).all()
    return render_template('files/shares.html', shares=shares)


@files_bp.route('/shares/<int:share_id>/delete', methods=['POST'])
@login_required
def delete_share(share_id):
    share = Share.query.filter_by(id=share_id, created_by=current_user.id).first_or_404()
    db.session.delete(share); db.session.commit()
    return jsonify({'ok': True})


@files_bp.route('/share/<token>/qr')
def share_qr(token):
    import qrcode, io
    share = Share.query.filter_by(token=token).first_or_404()
    url   = url_for('files.shared_file', token=token, _external=True)
    img   = qrcode.make(url)
    buf   = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
    return send_file(buf, mimetype='image/png')


@files_bp.route('/files/<int:file_id>/preview')
@login_required
def preview(file_id):
    f = File.query.filter_by(id=file_id, is_deleted=False).first_or_404()
    if f.user_id != current_user.id and not current_user.is_admin: abort(403)
    if not os.path.exists(f.file_path): abort(404)
    if f.file_type == 'text' and f.file_size < 1048576:
        with open(f.file_path, 'r', errors='replace') as fh:
            return jsonify({'type': 'text', 'content': fh.read()})
    return send_file(f.file_path, mimetype=f.mime_type or 'application/octet-stream')


@files_bp.route('/files/<int:file_id>/share-with-user', methods=['POST'])
@login_required
def share_with_user(file_id):
    f = File.query.filter_by(id=file_id, user_id=current_user.id, is_deleted=False).first_or_404()
    username = request.json.get('username', '').strip()
    target   = User.query.filter_by(username=username).first()
    if not target: return jsonify({'error': f'User "{username}" not found'}), 404
    if target.id == current_user.id: return jsonify({'error': 'Cannot share with yourself'}), 400
    share = Share(token=secrets.token_urlsafe(32), file_id=file_id,
                  created_by=current_user.id, shared_with=target.id,
                  is_public=False, allow_download=True)
    db.session.add(share)
    log_activity(current_user.id, 'share', 'file', file_id, f'{f.original_filename} → {username}')
    db.session.commit()
    return jsonify({'ok': True, 'url': url_for('files.shared_file', token=share.token, _external=True)})


@files_bp.route('/shared-with-me')
@login_required
def shared_with_me():
    shares = Share.query.filter_by(shared_with=current_user.id)\
              .order_by(Share.created_at.desc()).all()
    return render_template('files/shared_with_me.html', shares=shares)
