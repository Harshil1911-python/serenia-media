import os
import shutil
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db
from models.user import User
from models.file import File, Share, Activity
from routes import admin_bp


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/admin')
@login_required
@admin_required
def dashboard():
    users = User.query.count()
    total_files = File.query.filter_by(is_deleted=False).count()
    deleted_files = File.query.filter_by(is_deleted=True).count()
    total_storage = db.session.query(func.sum(File.file_size)).filter_by(is_deleted=False).scalar() or 0
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_files = File.query.order_by(File.created_at.desc()).limit(10).all()
    type_stats = db.session.query(
        File.file_type, func.count(File.id), func.sum(File.file_size)
    ).filter_by(is_deleted=False).group_by(File.file_type).all()

    return render_template('admin/dashboard.html',
        users=users, total_files=total_files, deleted_files=deleted_files,
        total_storage=total_storage, recent_users=recent_users,
        recent_files=recent_files, type_stats=type_stats
    )


@admin_bp.route('/admin/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users, q=q)


@admin_bp.route('/admin/users/<int:uid>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot disable yourself'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'ok': True, 'active': user.is_active})


@admin_bp.route('/admin/users/<int:uid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({'ok': True})


@admin_bp.route('/admin/files')
@login_required
@admin_required
def files():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    query = File.query
    if q:
        query = query.filter(File.original_filename.ilike(f'%{q}%'))
    files = query.order_by(File.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/files.html', files=files, q=q)


@admin_bp.route('/admin/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    activities = Activity.query.order_by(Activity.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', activities=activities)


@admin_bp.route('/admin/clean-storage', methods=['POST'])
@login_required
@admin_required
def clean_storage():
    from flask import current_app
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, upload_folder)

    # Remove permanently deleted file records older than 30 days
    deleted = File.query.filter_by(is_deleted=True).all()
    freed = 0
    for f in deleted:
        if os.path.exists(f.file_path):
            try:
                os.remove(f.file_path)
                freed += f.file_size
            except:
                pass
        db.session.delete(f)

    # Remove expired shares
    from models.file import Share
    from datetime import datetime
    expired = Share.query.filter(Share.expires_at < datetime.utcnow()).all()
    for s in expired:
        db.session.delete(s)

    db.session.commit()
    return jsonify({'ok': True, 'freed': freed, 'deleted_files': len(deleted), 'removed_shares': len(expired)})


@admin_bp.route('/admin/delete-all-media', methods=['POST'])
@login_required
@admin_required
def delete_all_media():
    confirm = request.json.get('confirm', '')
    if confirm != 'DELETE ALL MEDIA':
        return jsonify({'error': 'Confirmation required'}), 400

    from flask import current_app
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, upload_folder)

    all_files = File.query.all()
    for f in all_files:
        if os.path.exists(f.file_path):
            try:
                os.remove(f.file_path)
            except:
                pass
        db.session.delete(f)

    # Reset storage for all users
    User.query.update({'storage_used': 0})
    db.session.commit()

    return jsonify({'ok': True, 'deleted': len(all_files)})
