import os
from flask import render_template, g
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db
from models.user import SiteSettings
from config import config

migrate = Migrate()
csrf    = CSRFProtect()
login_manager = LoginManager()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # ensure folders
    for sub in ('uploads', 'avatars', 'brand'):
        folder = os.path.join(app.root_path, 'static', sub)
        os.makedirs(folder, exist_ok=True)

    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(app.root_path, upload_folder)
    os.makedirs(upload_folder, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    from routes import auth_bp, main_bp, files_bp, admin_bp, api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    csrf.exempt(files_bp)
    csrf.exempt(api_bp)

    # ── inject site settings into every template ──────────────────────────
    @app.context_processor
    def inject_settings():
        try:
            return dict(
                site_name     = SiteSettings.get('site_name', 'Serenia Media'),
                logo_path     = SiteSettings.get('logo_path', ''),
                favicon_path  = SiteSettings.get('favicon_path', ''),
                primary_color = SiteSettings.get('primary_color', '#87CEEB'),
                secondary_color = SiteSettings.get('secondary_color', '#5ba3c9'),
                bg_color      = SiteSettings.get('bg_color', '#f0f7fc'),
            )
        except Exception:
            return dict(site_name='Serenia Media', logo_path='', favicon_path='',
                        primary_color='#87CEEB', secondary_color='#5ba3c9', bg_color='#f0f7fc')

    # ── seed admin account ─────────────────────────────────────────────────
    def seed_admin():
        from models.user import User
        if User.query.filter_by(email='admin@gmail.com').first():
            return
        if User.query.count() == 0:
            u = User(username='admin', email='admin@gmail.com', is_admin=True)
            u.set_password('admin123')
            db.session.add(u)
            db.session.commit()

    # ── template filters ───────────────────────────────────────────────────
    @app.template_filter('human_size')
    def human_size(size):
        if not size: return '0 B'
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0: return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    @app.template_filter('timeago')
    def timeago(dt):
        if not dt: return ''
        from datetime import datetime
        diff = datetime.utcnow() - dt
        s = int(diff.total_seconds())
        if s < 60:   return 'just now'
        if s < 3600: m = s//60;  return f"{m} min{'s' if m>1 else ''} ago"
        if s < 86400: h = s//3600; return f"{h} hr{'s' if h>1 else ''} ago"
        if s < 2592000: d = s//86400; return f"{d} day{'s' if d>1 else ''} ago"
        return dt.strftime('%b %d, %Y')

    # ── error handlers ─────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):   return render_template('errors/403.html'), 403
    @app.errorhandler(404)
    def not_found(e):   return render_template('errors/404.html'), 404
    @app.errorhandler(410)
    def gone(e):        return render_template('errors/410.html'), 410
    @app.errorhandler(413)
    def too_large(e):   return render_template('errors/413.html'), 413
    @app.errorhandler(500)
    def server_error(e):return render_template('errors/500.html'), 500

    with app.app_context():
        db.create_all()
        seed_admin()

    return app


from flask import Flask
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
