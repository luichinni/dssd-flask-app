from flask import Blueprint, abort, current_app, render_template
from flask_login import login_required, current_user
from src.core.services.emergencias import listar_emergencias, crear_emergencia
from src.core.services.prioridades import PrioridadesError
from src.web.decorators.roles_required import roles_required
from src.core.enums import RolEnum, NivelGravedadEnum, TipoDesastreEnum
from flask import request, redirect, url_for, flash
from src.core.services.ofertas import (
    listar_ofertas_aceptadas,
    listar_ofertas_adjudicadas,
    listar_despliegues_oferta,
    obtener_version_vigente,
)
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

    try:
        tipo_desastre = TipoDesastreEnum(request.form.get('tipo_desastre'))
        nivel_gravedad = NivelGravedadEnum(request.form.get('nivel_gravedad', type=int))
        zona_afectada = request.form.get('zona_afectada', '').strip()
        if not 1 <= len(zona_afectada) <= 100:
            raise ValueError("Zona afectada inválida")
    except ValueError:
        flash("Revisá el tipo de desastre, la gravedad y la zona afectada.", "error")
        return new(), 400

    try:
        emergencia = crear_emergencia(
            tipo_desastre=tipo_desastre.value,
            nivel_gravedad=nivel_gravedad.value,
            zona_afectada=zona_afectada,
            descripcion=request.form.get('descripcion', ''),
            reportante_id=current_user.id,
            municipio_id=int(municipio_id),
        )
    except PrioridadesError as error:
        current_app.logger.warning("Falló la asignación de prioridad: %s", error, exc_info=True)
        flash("No se registró la emergencia porque no se pudo asignar la prioridad. Volvé a intentar.", "error")
        return new(), 503

    if emergencia.bonita_case_id is not None:
        flash(
            f"Emergencia registrada con prioridad {emergencia.prioridad}/10. Caso #{emergencia.bonita_case_id} creado en Bonita.",
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
    ofertas_adjudicadas = listar_ofertas_adjudicadas(emergencia_id)
    adjudicadas_con_detalle = [
        (oferta, obtener_version_vigente(oferta), listar_despliegues_oferta(oferta))
        for oferta in ofertas_adjudicadas
    ]

    return render_template(
        'emergencies/show.html',
        emergencia=emergencia,
        ofertas_con_detalle=ofertas_con_detalle,
        adjudicadas_con_detalle=adjudicadas_con_detalle,
    )


from src.core.services.ofertas import adjudicar_oferta

@emergencies_bp.post('/<int:emergencia_id>/ofertas/<int:oferta_id>/adjudicar')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def adjudicar(emergencia_id, oferta_id):
    """Adjudica una oferta aceptada a la emergencia correspondiente."""
    emergencia = Emergencia.query.get_or_404(emergencia_id)

    if emergencia.reportante_id != current_user.id:
        abort(403)

    try:
        adjudicar_oferta(oferta_id, emergencia_id=emergencia_id)
    except ValueError as e:
        # TODO: mostrar un mensaje de error al usuario (flash message) en vez de solo loguearlo
        print(f"Error al adjudicar: {e}")

    return redirect(url_for('emergencias.show', emergencia_id=emergencia_id))
@emergencies_bp.post('/<int:emergencia_id>/confirmar-adjudicaciones')
@login_required
@roles_required(RolEnum.OPERADOR_MUNICIPAL)
def confirmar_adjudicaciones(emergencia_id):
    """Confirma las ofertas adjudicadas y las envia a Bonita para registrar el compromiso y bloqueo de recursos."""
    emergencia = Emergencia.query.get_or_404(emergencia_id)

    if emergencia.reportante_id != current_user.id:
        abort(403)

    try:
        from src.core.services.bonita import enviar_adjudicaciones_a_bonita, BonitaError
        enviar_adjudicaciones_a_bonita(emergencia_id)
        flash('Adjudicaciones confirmadas y enviadas a Bonita exitosamente.', 'success')
    except (BonitaError, ValueError) as e:
        flash(f'Error al registrar adjudicaciones en Bonita: {e}', 'error')

    return redirect(url_for('emergencias.show', emergencia_id=emergencia_id))
