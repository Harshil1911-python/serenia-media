import os, secrets
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db
from models.user import User, SiteSettings
from models.file import Activity, File, Share, TextSnippet, Favorite
from routes import auth_bp

AVATAR_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _log(user_id, action, target_type=None, target_id=None, target_name=None, ip=None):
    act = Activity(user_id=user_id, action=action, target_type=target_type,
                   target_id=target_id, target_name=target_name, ip_address=ip)
    db.session.add(act)


def _avatar_folder():
    folder = os.path.join(current_app.root_path, 'static', 'avatars')
    os.makedirs(folder, exist_ok=True)
    return folder


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('Valid email required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')
        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html', username=username, email=email)
        user = User(username=username, email=email)
        user.set_password(password)
        if User.query.count() == 0:
            user.is_admin = True
        db.session.add(user)
        db.session.commit()
        _log(user.id, 'register', 'user', user.id, user.username)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')
        remember   = request.form.get('remember', False)
        user = User.query.filter(
            (User.email == identifier.lower()) | (User.username == identifier)
        ).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=bool(remember))
            user.last_login = datetime.utcnow()
            db.session.commit()
            _log(user.id, 'login', ip=request.remote_addr)
            db.session.commit()
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        flash('Invalid credentials or account disabled.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    _log(current_user.id, 'logout')
    db.session.commit()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(f'Reset link (demo): {reset_url}', 'info')
        else:
            flash('If that email exists, a reset link was sent.', 'info')
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expiry or datetime.utcnow() > user.reset_token_expiry:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif pw != request.form.get('confirm_password', ''):
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(pw)
            user.reset_token = None
            user.reset_token_expiry = None
            db.session.commit()
            flash('Password reset! Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action', 'profile')

        if action == 'profile':
            bio       = request.form.get('bio', '').strip()
            dark_mode = request.form.get('dark_mode') == 'on'
            current_user.bio       = bio
            current_user.dark_mode = dark_mode

            # avatar upload
            avatar = request.files.get('avatar')
            if avatar and avatar.filename:
                ext = avatar.filename.rsplit('.', 1)[-1].lower()
                if ext in AVATAR_EXTS:
                    fname = f"user_{current_user.id}.{ext}"
                    avatar.save(os.path.join(_avatar_folder(), fname))
                    current_user.avatar_path = fname
                else:
                    flash('Avatar must be an image (png/jpg/gif/webp).', 'error')
            db.session.commit()
            flash('Profile updated.', 'success')

        elif action == 'password':
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
                flash('Password changed.', 'success')

        elif action == 'delete_account':
            pw = request.form.get('verify_password', '')
            if not current_user.check_password(pw):
                flash('Incorrect password. Account not deleted.', 'error')
            else:
                # delete all physical files
                for f in current_user.files.all():
                    if os.path.exists(f.file_path):
                        try: os.remove(f.file_path)
                        except: pass
                # delete avatar
                if current_user.avatar_path:
                    ap = os.path.join(_avatar_folder(), current_user.avatar_path)
                    if os.path.exists(ap):
                        try: os.remove(ap)
                        except: pass
                uid = current_user.id
                logout_user()
                User.query.filter_by(id=uid).delete()
                db.session.commit()
                flash('Your account and all data have been permanently deleted.', 'info')
                return redirect(url_for('main.index'))

    privacy = SiteSettings.get('privacy_policy', '')
    terms   = SiteSettings.get('terms_of_use', '')
    return render_template('auth/profile.html', privacy=privacy, terms=terms)
