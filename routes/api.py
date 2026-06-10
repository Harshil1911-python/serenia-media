from flask import jsonify, request
from flask_login import login_required, current_user
from models import db
from models.file import File, Activity
from models.user import User
from routes import api_bp


@api_bp.route('/api/storage-stats')
@login_required
def storage_stats():
    from sqlalchemy import func
    type_counts = db.session.query(
        File.file_type, func.count(File.id), func.sum(File.file_size)
    ).filter_by(user_id=current_user.id, is_deleted=False).group_by(File.file_type).all()
    return jsonify({
        'storage_used': current_user.storage_used,
        'storage_limit': current_user.storage_limit,
        'storage_percent': current_user.storage_percent(),
        'type_breakdown': [{'type': t, 'count': c, 'size': s or 0} for t, c, s in type_counts]
    })


@api_bp.route('/api/recent-files')
@login_required
def recent_files():
    files = File.query.filter_by(user_id=current_user.id, is_deleted=False)\
        .order_by(File.created_at.desc()).limit(5).all()
    return jsonify([{'id': f.id, 'name': f.original_filename, 'type': f.file_type,
                     'size': f.size_human(), 'created_at': f.created_at.isoformat()} for f in files])


@api_bp.route('/api/toggle-dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return jsonify({'dark_mode': current_user.dark_mode})


@api_bp.route('/api/search-users')
@login_required
def search_users():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    users = User.query.filter(
        User.username.ilike(f'%{q}%'),
        User.id != current_user.id,
        User.is_active == True
    ).limit(8).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])
