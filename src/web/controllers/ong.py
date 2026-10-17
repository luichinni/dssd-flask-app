from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from src.core.enums import RolEnum, EstadoActividadEnum, EstadoOfertaEnum
from src.web.decorators.roles_required import roles_required
from src.core.services import inventario, notificaciones, actividades, ofertas, emergencias, lotes

ong_bp = Blueprint('ong', __name__, url_prefix='/ong')


def _ong_id_actual():
    ong_id = (current_user.datos_adicionales or {}).get('ong_id')
    try:
        return int(ong_id) if ong_id is not None else None
    except (TypeError, ValueError):
        return None


def _inventario_para_formulario(items):
    return [
        {
            'id': item.id,
            'id_recurso': item.id_recurso,
            'nombre': item.nombre,
            'cantidad_disponible': item.cantidad_disponible,
        }
        for item in items
    ]


def _recursos_desde_formulario(ong_id):
    try:
        recursos = []
        for inventario_id in request.form.getlist(f'recurso_{ong_id}'):
            inventario_id = int(inventario_id)
            cantidad = int(request.form.get(f'cantidad_{ong_id}_{inventario_id}', '0'))
            recursos.append({'id_recurso': inventario_id, 'cantidad': cantidad})
        return recursos
    except (TypeError, ValueError) as error:
        raise ValueError('La selección de recursos o cantidades no es válida.') from error


def _colaboradoras_desde_formulario(ong_id):
    try:
        ids = [int(value) for value in request.form.getlist('ong_colaboradora_id')]
    except (TypeError, ValueError) as error:
        raise ValueError('La selección de ONGs colaboradoras no es válida.') from error
    if ong_id in ids or len(ids) != len(set(ids)):
        raise ValueError('La lista de colaboradoras contiene IDs inválidos o duplicados.')
    return ids


def _colaboradoras_para_formulario(ong_id):
    return [
        {
            'id': item['ong'].id,
            'nombre': item['ong'].nombre,
        }
        for item in ofertas.listar_ongs_colaboradoras(ong_id)
    ]


@ong_bp.get('/convocatorias')
@login_required
@roles_required(RolEnum.ONG)
def convocatorias_activas():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    convocatorias = lotes.listar_convocatorias_activas()
    convocatorias_postuladas = ofertas.convocatorias_postuladas(ong_id)
    return render_template(
        'ong/convocatorias.html',
        convocatorias=convocatorias,
        convocatorias_postuladas=convocatorias_postuladas,
        invitaciones_pendientes=ofertas.invitaciones_pendientes_por_convocatoria(ong_id),
    )


# ==============================================================================
# INVENTARIO
# ==============================================================================

@ong_bp.route('/inventario')
@login_required
@roles_required(RolEnum.ONG)
def inventario_index():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    items = inventario.listar_inventario(ong_id)
    # Contadores para resumen
    total_recursos = len(items)
    stock_total = sum(item.cantidad_total for item in items)
    stock_disponible = sum(item.cantidad_disponible for item in items)
    
    return render_template(
        'ong/inventario/index.html',
        items=items,
        total_recursos=total_recursos,
        stock_total=stock_total,
        stock_disponible=stock_disponible,
    )

@ong_bp.route('/inventario/nuevo', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def inventario_crear():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    if request.method == 'POST':
        try:
            recurso = inventario.crear_recurso(ong_id, {
                'recurso_catalogo_id': request.form.get('recurso_catalogo_id'),
                'cantidad_total': request.form.get('cantidad_total'),
            })
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('ong.inventario_crear'))

        flash(f'Recurso "{recurso.nombre}" agregado exitosamente al inventario.', 'success')
        return redirect(url_for('ong.inventario_index'))

    catalogo_disponible = inventario.listar_catalogo_disponible(ong_id)
    if not catalogo_disponible:
        flash('Ya tienes todos los recursos del catálogo en tu inventario.', 'info')
    return render_template(
        'ong/inventario/form.html',
        modo='crear',
        recurso=None,
        catalogo_disponible=catalogo_disponible,
    )

@ong_bp.route('/inventario/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def inventario_editar(id):
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    recurso = inventario.obtener_recurso(id, ong_id)
    if not recurso:
        flash('Recurso no encontrado.', 'error')
        return redirect(url_for('ong.inventario_index'))

    if request.method == 'POST':
        try:
            inventario.actualizar_recurso(id, ong_id, {
                'cantidad_total': request.form.get('cantidad_total'),
            })
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('ong.inventario_editar', id=id))

        flash(f'Recurso "{recurso.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('ong.inventario_index'))

    cantidad_comprometida = inventario.cantidad_comprometida(ong_id, recurso.id_recurso)
    return render_template(
        'ong/inventario/form.html',
        modo='editar',
        recurso=recurso,
        cantidad_comprometida=cantidad_comprometida,
        minimo_cantidad=cantidad_comprometida,
    )

@ong_bp.route('/inventario/<int:id>/eliminar', methods=['POST'])
@login_required
@roles_required(RolEnum.ONG)
def inventario_eliminar(id):
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    try:
        exito = inventario.eliminar_recurso(id, ong_id)
        if exito:
            flash('Recurso eliminado del inventario.', 'info')
        else:
            flash('No se pudo encontrar el recurso a eliminar.', 'error')
    except ValueError as error:
        flash(str(error), 'error')
    return redirect(url_for('ong.inventario_index'))


# ==============================================================================
# NOTIFICACIONES
# ==============================================================================

@ong_bp.route('/notificaciones')
@login_required
@roles_required(RolEnum.ONG)
def notificaciones_index():
    solo_no_leidas = request.args.get('filtro') == 'no_leidas'
    lista = notificaciones.listar_notificaciones(current_user.id, solo_no_leidas=solo_no_leidas)
    total_no_leidas = notificaciones.contar_no_leidas(current_user.id)

    return render_template(
        'ong/notificaciones/index.html',
        notificaciones=lista,
        total_no_leidas=total_no_leidas,
        filtro_actual='no_leidas' if solo_no_leidas else 'todas'
    )

@ong_bp.route('/notificaciones/<int:id>/leer', methods=['POST'])
@login_required
@roles_required(RolEnum.ONG)
def notificacion_marcar_leida(id):
    notificaciones.marcar_leida(id, current_user.id)
    flash('Notificación marcada como leída.', 'info')
    return redirect(url_for('ong.notificaciones_index'))

@ong_bp.route('/notificaciones/leer-todas', methods=['POST'])
@login_required
@roles_required(RolEnum.ONG)
def notificaciones_marcar_todas():
    cant = notificaciones.marcar_todas_leidas(current_user.id)
    flash(f'{cant} notificaciones marcadas como leídas.', 'info')
    return redirect(url_for('ong.notificaciones_index'))


# ==============================================================================
# ACTIVIDADES Y CIERRE
# ==============================================================================

@ong_bp.route('/actividades')
@login_required
@roles_required(RolEnum.ONG)
def actividades_index():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    estado_filtro = request.args.get('estado')
    enum_filtro = None
    if estado_filtro == 'en_ejecucion':
        enum_filtro = EstadoActividadEnum.EN_EJECUCION
    elif estado_filtro == 'finalizada':
        enum_filtro = EstadoActividadEnum.FINALIZADA

    lista = actividades.listar_actividades(ong_id, estado=enum_filtro)
    en_curso_cant = len(actividades.listar_actividades(ong_id, estado=EstadoActividadEnum.EN_EJECUCION))
    finalizadas_cant = len(actividades.listar_actividades(ong_id, estado=EstadoActividadEnum.FINALIZADA))

    return render_template(
        'ong/actividades/index.html',
        actividades=lista,
        en_curso_cant=en_curso_cant,
        finalizadas_cant=finalizadas_cant,
        filtro_actual=estado_filtro or 'todas'
    )

@ong_bp.route('/actividades/<int:id>/finalizar', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def actividad_finalizar(id):
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    actividad = actividades.obtener_actividad(id, ong_id)
    if not actividad:
        flash('Actividad no encontrada.', 'error')
        return redirect(url_for('ong.actividades_index'))

    if actividad.estado == EstadoActividadEnum.FINALIZADA:
        flash('Esta actividad ya se encuentra marcada como finalizada.', 'info')
        return redirect(url_for('ong.actividades_index'))

    if request.method == 'POST':
        informe_cierre = request.form.get('informe_cierre', '').strip()
        recursos_utilizados = request.form.get('recursos_utilizados', '').strip()

        if not informe_cierre:
            flash('Debe ingresar un informe o detalle de cierre de las labores realizadas.', 'error')
            return render_template('ong/actividades/finalizar.html', actividad=actividad)

        actividades.finalizar_actividad(
            actividad_id=id,
            ong_id=ong_id,
            informe_cierre=informe_cierre,
            recursos_utilizados=recursos_utilizados
        )

        flash(f'Actividad "{actividad.titulo}" finalizada con éxito. Labores registradas formalmente.', 'success')
        return redirect(url_for('ong.actividades_index'))

    return render_template('ong/actividades/finalizar.html', actividad=actividad)

# ==============================================================================
# OFERTAS
# ==============================================================================

@ong_bp.route('/ofertas/crear', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def crear_oferta():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)

    convocatoria_id = request.values.get('convocatoria_id', type=int)
    if convocatoria_id is None:
        abort(400)

    convocatoria = lotes.obtener_lote(convocatoria_id)
    if not convocatoria or lotes.estado_lote(convocatoria) != 'publicado':
        abort(404)

    if request.method == 'POST':
        try:
            recursos = _recursos_desde_formulario(ong_id)
            colaboradoras_ids = _colaboradoras_desde_formulario(ong_id)
            oferta = ofertas.crear_oferta(
                convocatoria_id=convocatoria.id,
                recursos=recursos,
                ong_id=ong_id,
                usuario_id=current_user.id,
                colaboradoras_ids=colaboradoras_ids,
            )

            flash(
                f'Oferta #{oferta.id_oferta} creada correctamente.',
                'success'
            )

            return redirect(
                url_for('ong.listado_ofertas')
            )

        except ValueError as error:
            flash(str(error), 'error')

            return redirect(
                url_for('ong.crear_oferta', convocatoria_id=convocatoria.id)
            )

    recurso_ids_solicitados = {detalle.id_recurso for detalle in convocatoria.detalles}
    inventario_ong = inventario.listar_inventario(ong_id, recurso_ids_solicitados)

    return render_template(
        'ofertas/crear_oferta.html',
        inventario_data=_inventario_para_formulario(inventario_ong),
        recursos_disponibles=bool(inventario_ong),
        colaboradoras_data=_colaboradoras_para_formulario(ong_id),
        participantes_iniciales=[],
        ong_id=ong_id,
        ong_nombre=(current_user.datos_adicionales or {}).get('organizacion', current_user.nombre),
        convocatoria=convocatoria,
    )

@ong_bp.route('/ofertas/listado', methods=['GET'])
@login_required
@roles_required(RolEnum.ONG)
def listado_ofertas():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    lista = ofertas.listar_ofertas(ong_id)

    return render_template('ofertas/listado_ofertas.html', ofertas=lista, EstadoOfertaEnum=EstadoOfertaEnum)

@ong_bp.route('/ofertas/<int:id_oferta>/modificar', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def modificar_oferta(id_oferta):
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)

    # Obtener oferta y verificar que la ONG participe
    try:
        oferta, version_actual, participacion = ofertas.obtener_oferta_para_modificar(
            id_oferta=id_oferta,
            id_ong=ong_id,
        )

    except ValueError as e:

        flash(str(e), 'error')

        return redirect(
            url_for('ong.listado_ofertas')
        )

    if request.method == 'POST':
        try:
            recursos = _recursos_desde_formulario(ong_id)
            colaboradoras_ids = _colaboradoras_desde_formulario(ong_id) if oferta.creada_por_ong_id == ong_id else []
            oferta = ofertas.modificar_oferta(
                id_oferta=id_oferta,
                recursos=recursos,
                ong_id=ong_id,
                usuario_id=current_user.id,
                colaboradoras_ids=colaboradoras_ids,
            )

            flash(
                f'Oferta #{oferta.id_oferta} modificada correctamente.',
                'success'
            )

            return redirect(
                url_for('ong.listado_ofertas')
            )

        except ValueError as error:
            flash(str(error), 'error')

            return redirect(
                url_for(
                    'ong.modificar_oferta',
                    id_oferta=id_oferta
                )
            )

    #Lo que queda con GET
    recurso_ids_solicitados = (
        {detalle.id_recurso for detalle in oferta.convocatoria.detalles}
        if oferta.convocatoria is not None
        else set()
    )
    inventario_ong = inventario.listar_inventario(ong_id, recurso_ids_solicitados)
    detalles_propios = {
        str(item.id): detalle.cantidad
        for detalle in version_actual.detalles
        if detalle.id_ong == ong_id
        for item in inventario_ong
        if item.id_recurso == detalle.id_recurso
    }
    colaboradoras_actuales = [
        {'id': item.ong_id, 'nombre': item.ong.nombre, 'estado': item.estado}
        for item in oferta.participaciones
        if item.ong_id != ong_id
    ]
    es_creadora = oferta.creada_por_ong_id == ong_id

    return render_template(
        'ofertas/modificar_oferta.html',
        oferta=oferta,
        version_actual=version_actual,
        inventario_data=_inventario_para_formulario(inventario_ong),
        colaboradoras_data=_colaboradoras_para_formulario(ong_id) if es_creadora else [],
        colaboradoras_actuales=colaboradoras_actuales,
        cantidades_propias=detalles_propios,
        recursos_disponibles=bool(inventario_ong),
        es_creadora=es_creadora,
        ong_id=ong_id,
        ong_nombre=(current_user.datos_adicionales or {}).get('organizacion', current_user.nombre),
    )