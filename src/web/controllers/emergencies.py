from flask import Blueprint, render_template
from flask_login import login_required, current_user
from src.core.services.emergencias import listar_emergencias, crear_emergencia
from src.web.decorators.roles_required import roles_required
from src.core.enums import RolEnum, NivelGravedadEnum, TipoDesastreEnum
from flask import request, redirect, url_for

emergencies_bp = Blueprint('emergencias', __name__, url_prefix='/emergencias')


@emergencies_bp.get('/')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def index():
    """Muestra el listado de emergencias registradas por el operador municipal."""
    
    emergencias = listar_emergencias(current_user.id)
    
    return render_template('emergencies/index.html', emergencias=emergencias, NivelGravedadEnum=NivelGravedadEnum)
    
@emergencies_bp.get('/create')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def new():
    """Muestra el formulario para crear una nueva emergencia."""

    return render_template('emergencies/create.html', tipos_desastre=TipoDesastreEnum, niveles_gravedad=NivelGravedadEnum)

@emergencies_bp.post('/create')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def create():
    """Procesa el formulario para crear una nueva emergencia."""
    
    # Aquí iría la lógica para procesar el formulario y crear la emergencia.
    # Por ahora, simplemente redirigimos al listado de emergencias.
    crear_emergencia(
        tipo_desastre=request.form['tipo_desastre'],
        nivel_gravedad=int(request.form['nivel_gravedad']),
        zona_afectada=request.form['zona_afectada'],
        descripcion=request.form['descripcion'],
        reportante_id=current_user.id
    )
    emergencias = listar_emergencias(current_user.id)

    return redirect(url_for('emergencias.index'))