from flask import render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db
from models.user import User, SiteSettings
from models.file import File, Share, TextSnippet, Activity, Favorite
from routes import main_bp
import secrets as sec


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    settings = {
        'site_name':    SiteSettings.get('site_name', 'Serenia Media'),
        'landing_hero_title': SiteSettings.get('landing_hero_title', ''),
        'landing_hero_desc':  SiteSettings.get('landing_hero_desc', ''),
        'logo_path':    SiteSettings.get('logo_path', ''),
    }
    return render_template('main/index.html', settings=settings)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    total_files  = File.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    total_shares = Share.query.filter_by(created_by=current_user.id).count()
    recent_files = File.query.filter_by(user_id=current_user.id, is_deleted=False)\
                    .order_by(File.created_at.desc()).limit(8).all()
    type_counts  = db.session.query(File.file_type, func.count(File.id))\
                    .filter_by(user_id=current_user.id, is_deleted=False)\
                    .group_by(File.file_type).all()
    activities   = Activity.query.filter_by(user_id=current_user.id)\
                    .order_by(Activity.created_at.desc()).limit(10).all()
    fav_ids      = [f.file_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    fav_files    = File.query.filter(File.id.in_(fav_ids), File.is_deleted==False).all() if fav_ids else []
    shared_with_me = Share.query.filter_by(shared_with=current_user.id)\
                      .order_by(Share.created_at.desc()).limit(5).all()
    return render_template('main/dashboard.html',
        total_files=total_files, total_shares=total_shares,
        recent_files=recent_files, type_counts=dict(type_counts),
        activities=activities, fav_files=fav_files,
        shared_with_me=shared_with_me,
        storage_used=current_user.storage_used,
        storage_limit=current_user.storage_limit,
        storage_percent=current_user.storage_percent())


@main_bp.route('/search')
@login_required
def search():
    q         = request.args.get('q', '').strip()
    file_type = request.args.get('type', '')
    sort      = request.args.get('sort', 'date')
    page      = request.args.get('page', 1, type=int)
    query = File.query.filter_by(user_id=current_user.id, is_deleted=False)
    if q:
        query = query.filter(
            File.original_filename.ilike(f'%{q}%') |
            File.tags.ilike(f'%{q}%') |
            File.description.ilike(f'%{q}%'))
    if file_type: query = query.filter_by(file_type=file_type)
    if sort == 'name': query = query.order_by(File.original_filename)
    elif sort == 'size': query = query.order_by(File.file_size.desc())
    elif sort == 'type': query = query.order_by(File.file_type)
    else: query = query.order_by(File.created_at.desc())
    files = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('main/search.html', files=files, q=q, file_type=file_type, sort=sort)


@main_bp.route('/snippets')
@login_required
def snippets():
    snips = TextSnippet.query.filter_by(user_id=current_user.id)\
             .order_by(TextSnippet.created_at.desc()).all()
    return render_template('main/snippets.html', snippets=snips)


@main_bp.route('/snippets/create', methods=['POST'])
@login_required
def create_snippet():
    title    = request.form.get('title', 'Untitled').strip()
    content  = request.form.get('content', '').strip()
    language = request.form.get('language', '').strip()
    is_public= request.form.get('is_public') == 'on'
    if not content:
        flash('Content cannot be empty.', 'error')
        return redirect(url_for('main.snippets'))
    snip = TextSnippet(title=title, content=content, language=language,
                       is_public=is_public, user_id=current_user.id,
                       token=sec.token_urlsafe(16))
    db.session.add(snip); db.session.commit()
    flash('Snippet created!', 'success')
    return redirect(url_for('main.snippets'))


@main_bp.route('/snippets/<int:snip_id>/delete', methods=['POST'])
@login_required
def delete_snippet(snip_id):
    snip = TextSnippet.query.filter_by(id=snip_id, user_id=current_user.id).first_or_404()
    db.session.delete(snip); db.session.commit()
    return jsonify({'ok': True})


@main_bp.route('/s/<token>')
def public_snippet(token):
    snip = TextSnippet.query.filter_by(token=token, is_public=True).first_or_404()
    snip.view_count += 1; db.session.commit()
    return render_template('main/public_snippet.html', snip=snip)


@main_bp.route('/activity')
@login_required
def activity():
    page = request.args.get('page', 1, type=int)
    activities = Activity.query.filter_by(user_id=current_user.id)\
                  .order_by(Activity.created_at.desc())\
                  .paginate(page=page, per_page=30, error_out=False)
    return render_template('main/activity.html', activities=activities)


@main_bp.route('/favorites')
@login_required
def favorites():
    fav_ids = [f.file_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    files   = File.query.filter(File.id.in_(fav_ids), File.is_deleted==False).all() if fav_ids else []
    return render_template('main/favorites.html', files=files)


@main_bp.route('/privacy')
def privacy():
    policy = SiteSettings.get('privacy_policy', 'No privacy policy has been set yet.')
    site_name = SiteSettings.get('site_name', 'Serenia Media')
    return render_template('main/legal.html', title='Privacy Policy', content=policy, site_name=site_name)


@main_bp.route('/terms')
def terms():
    terms = SiteSettings.get('terms_of_use', 'No terms of use have been set yet.')
    site_name = SiteSettings.get('site_name', 'Serenia Media')
    return render_template('main/legal.html', title='Terms of Use', content=terms, site_name=site_name)
