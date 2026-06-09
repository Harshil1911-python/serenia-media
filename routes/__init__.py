from flask import Blueprint

auth_bp = Blueprint('auth', __name__)
main_bp = Blueprint('main', __name__)
files_bp = Blueprint('files', __name__)
admin_bp = Blueprint('admin', __name__)
api_bp = Blueprint('api', __name__)

from routes import auth, main, files, admin, api
