from flask import Blueprint, render_template
from flask_login import login_required

from src.core.services.users import listar_usuarios


users_bp = Blueprint('users', __name__, url_prefix='/usuarios')


@users_bp.get('/')
@login_required
def index():
    """Muestra el listado de usuarios registrados."""
    usuarios = listar_usuarios()
    return render_template('users/index.html', usuarios=usuarios)
