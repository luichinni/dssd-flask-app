from flask import Blueprint, abort, render_template
from flask_login import login_required, current_user
from src.core.services.emergencias import listar_emergencias, crear_emergencia
from src.web.decorators.roles_required import roles_required
from src.core.enums import RolEnum, NivelGravedadEnum, TipoDesastreEnum
from flask import request, redirect, url_for, flash
from src.core.services.ofertas import listar_ofertas_aceptadas, obtener_version_vigente
from src.core.models.emergencia import Emergencia

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
    municipio_id = (current_user.datos_adicionales or {}).get('municipio_id')
    if municipio_id is None:
        abort(400)

    emergencia = crear_emergencia(
        tipo_desastre=request.form['tipo_desastre'],
        nivel_gravedad=int(request.form['nivel_gravedad']),
        zona_afectada=request.form['zona_afectada'],
        descripcion=request.form.get('descripcion', ''),
        reportante_id=current_user.id,
        municipio_id=int(municipio_id),
    )

    if emergencia.bonita_case_id is not None:
        flash(
            f"Emergencia registrada. Caso #{emergencia.bonita_case_id} creado en Bonita.",
            "success",
        )
    else:
        flash(
            f"La emergencia #{emergencia.id} quedó guardada, pero no se confirmó "
            "la creación del caso en Bonita. Revisá los casos y el log antes de "
            "volver a registrarla.",
            "error",
        )
    return redirect(url_for('emergencias.index'))

@emergencies_bp.get('/<int:emergencia_id>')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def show(emergencia_id):
    """Muestra el detalle de una emergencia y las ofertas aceptadas para adjudicar."""
    emergencia = Emergencia.query.get_or_404(emergencia_id)
     #para verificar que la emergencia con el id que se pasa por parámetro pertenece al operador municipal que está logueado
    if emergencia.reportante_id != current_user.id: 
        abort(403)

    ofertas = listar_ofertas_aceptadas(emergencia_id)
    ofertas_con_detalle = [
        (oferta, obtener_version_vigente(oferta))
        for oferta in ofertas
    ]

    return render_template('emergencies/show.html', emergencia=emergencia, ofertas_con_detalle=ofertas_con_detalle)


from src.core.services.ofertas import listar_ofertas_aceptadas, obtener_version_vigente, adjudicar_oferta

@emergencies_bp.post('/<int:emergencia_id>/ofertas/<int:oferta_id>/adjudicar')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def adjudicar(emergencia_id, oferta_id):
    """Adjudica una oferta aceptada a la emergencia correspondiente."""
    emergencia = Emergencia.query.get_or_404(emergencia_id)

    if emergencia.reportante_id != current_user.id:
        abort(403)

    try:
        adjudicar_oferta(oferta_id)
    except ValueError as e:
        # TODO: mostrar un mensaje de error al usuario (flash message) en vez de solo loguearlo
        print(f"Error al adjudicar: {e}")

    return redirect(url_for('emergencias.show', emergencia_id=emergencia_id))