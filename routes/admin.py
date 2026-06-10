import os, secrets
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db
from models.user import User, SiteSettings
from models.file import File, Share, Activity, TextSnippet, Favorite
from routes import admin_bp


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort; abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────
@admin_bp.route('/admin')
@login_required
@admin_required
def dashboard():
    users        = User.query.count()
    total_files  = File.query.filter_by(is_deleted=False).count()
    deleted_files= File.query.filter_by(is_deleted=True).count()
    total_storage= db.session.query(func.sum(File.file_size)).filter_by(is_deleted=False).scalar() or 0
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_files = File.query.order_by(File.created_at.desc()).limit(10).all()
    type_stats   = db.session.query(File.file_type, func.count(File.id), func.sum(File.file_size))\
                    .filter_by(is_deleted=False).group_by(File.file_type).all()
    settings = {
        'site_name':    SiteSettings.get('site_name', 'Serenia Media'),
        'primary_color':SiteSettings.get('primary_color', '#87CEEB'),
        'logo_path':    SiteSettings.get('logo_path', ''),
        'favicon_path': SiteSettings.get('favicon_path', ''),
        'landing_hero_title': SiteSettings.get('landing_hero_title', ''),
        'landing_hero_desc':  SiteSettings.get('landing_hero_desc', ''),
        'privacy_policy':     SiteSettings.get('privacy_policy', ''),
        'terms_of_use':       SiteSettings.get('terms_of_use', ''),
    }
    return render_template('admin/dashboard.html',
        users=users, total_files=total_files, deleted_files=deleted_files,
        total_storage=total_storage, recent_users=recent_users,
        recent_files=recent_files, type_stats=type_stats, settings=settings)


# ── Users ─────────────────────────────────────────────────────────────────
@admin_bp.route('/admin/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '')
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
    for f in user.files.all():
        if os.path.exists(f.file_path):
            try: os.remove(f.file_path)
            except: pass
    db.session.delete(user)
    db.session.commit()
    return jsonify({'ok': True})


@admin_bp.route('/admin/users/<int:uid>/storage', methods=['POST'])
@login_required
@admin_required
def set_storage(uid):
    user = User.query.get_or_404(uid)
    gb   = request.json.get('gb', 1)
    try:
        gb = float(gb)
        user.storage_limit = int(gb * 1073741824)
        db.session.commit()
        return jsonify({'ok': True, 'limit': user.storage_limit_human()})
    except:
        return jsonify({'error': 'Invalid value'}), 400


@admin_bp.route('/admin/users/<int:uid>/password', methods=['POST'])
@login_required
@admin_required
def set_user_password(uid):
    user = User.query.get_or_404(uid)
    pw   = request.json.get('password', '')
    if len(pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    user.set_password(pw)
    db.session.commit()
    return jsonify({'ok': True})


# ── Admin own password ─────────────────────────────────────────────────────
@admin_bp.route('/admin/change-password', methods=['POST'])
@login_required
@admin_required
def change_own_password():
    cur = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    con = request.form.get('confirm_password', '')
    if not current_user.check_password(cur):
        flash('Current password incorrect.', 'error')
    elif len(new) < 8:
        flash('New password must be at least 8 characters.', 'error')
    elif new != con:
        flash('Passwords do not match.', 'error')
    else:
        current_user.set_password(new)
        db.session.commit()
        flash('Password updated.', 'success')
    return redirect(url_for('admin.dashboard') + '#security')


# ── Files ─────────────────────────────────────────────────────────────────
@admin_bp.route('/admin/files')
@login_required
@admin_required
def files():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '')
    query = File.query
    if q:
        query = query.filter(File.original_filename.ilike(f'%{q}%'))
    files = query.order_by(File.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/files.html', files=files, q=q)


# ── Logs ──────────────────────────────────────────────────────────────────
@admin_bp.route('/admin/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    activities = Activity.query.order_by(Activity.created_at.desc())\
                  .paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', activities=activities)


# ── DataVault ─────────────────────────────────────────────────────────────
@admin_bp.route('/admin/datavault')
@login_required
@admin_required
def datavault():
    users = User.query.order_by(User.created_at.desc()).all()
    vault = []
    for u in users:
        files   = File.query.filter_by(user_id=u.id, is_deleted=False).all()
        shares  = Share.query.filter_by(created_by=u.id).all()
        snips   = TextSnippet.query.filter_by(user_id=u.id).all()
        acts    = Activity.query.filter_by(user_id=u.id).order_by(Activity.created_at.desc()).limit(5).all()
        vault.append({'user': u, 'files': files, 'shares': shares, 'snippets': snips, 'activities': acts})
    return render_template('admin/datavault.html', vault=vault)


# ── Site Settings ─────────────────────────────────────────────────────────
@admin_bp.route('/admin/settings', methods=['POST'])
@login_required
@admin_required
def save_settings():
    action = request.form.get('action', '')

    if action == 'branding':
        SiteSettings.set('site_name',    request.form.get('site_name', 'Serenia Media'))
        SiteSettings.set('primary_color',request.form.get('primary_color', '#87CEEB'))
        SiteSettings.set('landing_hero_title', request.form.get('landing_hero_title', ''))
        SiteSettings.set('landing_hero_desc',  request.form.get('landing_hero_desc', ''))

        # Logo upload
        logo = request.files.get('logo')
        if logo and logo.filename:
            ext   = logo.filename.rsplit('.', 1)[-1].lower()
            fname = f'logo.{ext}'
            folder = os.path.join(current_app.root_path, 'static', 'brand')
            os.makedirs(folder, exist_ok=True)
            logo.save(os.path.join(folder, fname))
            SiteSettings.set('logo_path', fname)

        # Favicon upload
        fav = request.files.get('favicon')
        if fav and fav.filename:
            ext   = fav.filename.rsplit('.', 1)[-1].lower()
            fname = f'favicon.{ext}'
            folder = os.path.join(current_app.root_path, 'static', 'brand')
            os.makedirs(folder, exist_ok=True)
            fav.save(os.path.join(folder, fname))
            SiteSettings.set('favicon_path', fname)

        flash('Branding settings saved.', 'success')

    elif action == 'legal':
        SiteSettings.set('privacy_policy', request.form.get('privacy_policy', ''))
        SiteSettings.set('terms_of_use',   request.form.get('terms_of_use', ''))
        flash('Legal pages saved.', 'success')

    elif action == 'theme':
        SiteSettings.set('primary_color', request.form.get('primary_color', '#87CEEB'))
        SiteSettings.set('secondary_color', request.form.get('secondary_color', '#5ba3c9'))
        SiteSettings.set('bg_color',       request.form.get('bg_color', '#f0f7fc'))
        flash('Theme saved.', 'success')

    return redirect(url_for('admin.dashboard') + '#settings')


# ── Storage cleanup ────────────────────────────────────────────────────────
@admin_bp.route('/admin/clean-storage', methods=['POST'])
@login_required
@admin_required
def clean_storage():
    deleted = File.query.filter_by(is_deleted=True).all()
    freed = 0
    for f in deleted:
        if os.path.exists(f.file_path):
            try: os.remove(f.file_path); freed += f.file_size
            except: pass
        db.session.delete(f)
    expired = Share.query.filter(Share.expires_at < datetime.utcnow()).all()
    for s in expired:
        db.session.delete(s)
    db.session.commit()
    return jsonify({'ok': True, 'freed': freed, 'deleted_files': len(deleted), 'removed_shares': len(expired)})


@admin_bp.route('/admin/delete-all-media', methods=['POST'])
@login_required
@admin_required
def delete_all_media():
    if request.json.get('confirm') != 'DELETE ALL MEDIA':
        return jsonify({'error': 'Confirmation required'}), 400
    all_files = File.query.all()
    for f in all_files:
        if os.path.exists(f.file_path):
            try: os.remove(f.file_path)
            except: pass
        db.session.delete(f)
    User.query.update({'storage_used': 0})
    db.session.commit()
    return jsonify({'ok': True, 'deleted': len(all_files)})
