from flask import Blueprint, render_template
from flask_login import login_required, current_user
from src.core.services.emergencias import listar_emergencias
from src.web.decorators.roles_required import roles_required
from src.core.enums import RolEnum, NivelGravedadEnum

emergencies_bp = Blueprint('emergencias', __name__, url_prefix='/emergencias')


@emergencies_bp.get('/')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def index():
    """Muestra el listado de emergencias registradas por el operador municipal."""
    
    emergencias = listar_emergencias(current_user.id)
    
    return render_template('emergencies/index.html', emergencias=emergencias, NivelGravedadEnum=NivelGravedadEnum)
    