from flask import Blueprint, render_template
from flask_login import login_required

emergencies_bp = Blueprint('emergencias', __name__, url_prefix='/emergencias')


@emergencies_bp.get('/')
@login_required
def index():
    """Muestra el listado de emergencias registradas."""
    # Aquí deberías llamar a un servicio que obtenga las emergencias desde la base de datos
    # Por ejemplo: emergencias = listar_emergencias()
    # emergencias = []  # Esto es solo un placeholder
    return render_template('emergencies/index.html')
    # return render_template('emergencies/index.html', emergencias=emergencias)