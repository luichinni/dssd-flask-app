from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from src.core.enums import RolEnum, TipoRecursoEnum, EstadoActividadEnum, EstadoOfertaEnum
from src.web.decorators.roles_required import roles_required
from src.core.services import inventario, notificaciones, actividades, ofertas, emergencias, lotes

ong_bp = Blueprint('ong', __name__, url_prefix='/ong')


def _ong_id_actual():
    ong_id = (current_user.datos_adicionales or {}).get('ong_id')
    try:
        return int(ong_id) if ong_id is not None else None
    except (TypeError, ValueError):
        return None


@ong_bp.get('/convocatorias')
@login_required
@roles_required(RolEnum.ONG)
def convocatorias_activas():
    convocatorias = lotes.listar_convocatorias_activas()
    return render_template('ong/convocatorias.html', convocatorias=convocatorias)


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
        tipos_recurso=TipoRecursoEnum.choices()
    )

@ong_bp.route('/inventario/nuevo', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def inventario_crear():
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        tipo_recurso = request.form.get('tipo_recurso', '')
        unidad_medida = request.form.get('unidad_medida', '').strip()
        cantidad_total = request.form.get('cantidad_total', '0')
        descripcion = request.form.get('descripcion', '').strip()

        if not nombre:
            flash('El nombre del recurso es obligatorio.', 'error')
            return redirect(url_for('ong.inventario_crear'))

        try:
            cantidad_int = int(cantidad_total)
            if cantidad_int < 0:
                raise ValueError()
        except ValueError:
            flash('La cantidad debe ser un número entero mayor o igual a 0.', 'error')
            return redirect(url_for('ong.inventario_crear'))

        inventario.crear_recurso(ong_id, {
            'nombre': nombre,
            'tipo_recurso': tipo_recurso,
            'unidad_medida': unidad_medida or 'Unidades',
            'cantidad_total': cantidad_int,
            'descripcion': descripcion,
        })

        flash(f'Recurso "{nombre}" agregado exitosamente al inventario.', 'success')
        return redirect(url_for('ong.inventario_index'))

    return render_template('ong/inventario/form.html', modo='crear', recurso=None, tipos_recurso=TipoRecursoEnum.choices())

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
        nombre = request.form.get('nombre', '').strip()
        tipo_recurso = request.form.get('tipo_recurso', '')
        unidad_medida = request.form.get('unidad_medida', '').strip()
        cantidad_total = request.form.get('cantidad_total', '0')
        descripcion = request.form.get('descripcion', '').strip()

        if not nombre:
            flash('El nombre del recurso es obligatorio.', 'error')
            return redirect(url_for('ong.inventario_editar', id=id))

        try:
            cantidad_int = int(cantidad_total)
            if cantidad_int < 0:
                raise ValueError()
        except ValueError:
            flash('La cantidad debe ser un número entero mayor o igual a 0.', 'error')
            return redirect(url_for('ong.inventario_editar', id=id))

        inventario.actualizar_recurso(id, ong_id, {
            'nombre': nombre,
            'tipo_recurso': tipo_recurso,
            'unidad_medida': unidad_medida or 'Unidades',
            'cantidad_total': cantidad_int,
            'descripcion': descripcion,
        })

        flash(f'Recurso "{nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('ong.inventario_index'))

    return render_template('ong/inventario/form.html', modo='editar', recurso=recurso, tipos_recurso=TipoRecursoEnum.choices())

@ong_bp.route('/inventario/<int:id>/eliminar', methods=['POST'])
@login_required
@roles_required(RolEnum.ONG)
def inventario_eliminar(id):
    ong_id = _ong_id_actual()
    if ong_id is None:
        abort(403)
    exito = inventario.eliminar_recurso(id, ong_id)
    if exito:
        flash('Recurso eliminado del inventario.', 'info')
    else:
        flash('No se pudo eliminar el recurso.', 'error')
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
        id_emergencia = convocatoria.emergencia_id

        # Recursos elegidos
        ids_recursos = request.form.getlist(
            'id_recurso'
        )

        recursos = []

        for id_recurso in ids_recursos:

            try:
                id_recurso = int(id_recurso)

                cantidad = int(
                    request.form.get(
                        f'cantidad_{id_recurso}',
                        '0'
                    )
                )

            except (TypeError, ValueError):

                flash(
                    'La cantidad de los recursos debe ser válida.',
                    'error'
                )

                return redirect(
                    url_for('ong.crear_oferta', convocatoria_id=convocatoria.id)
                )

            recursos.append({
                'id_recurso': id_recurso,
                'cantidad': cantidad
            })

        # Crear oferta
        try:

            oferta = ofertas.crear_oferta(
                id_emergencia=id_emergencia,
                recursos=recursos,
                ong_id=ong_id,
                usuario_id=current_user.id,
            )

            flash(
                f'Oferta #{oferta.id_oferta} creada correctamente.',
                'success'
            )

            return redirect(
                url_for('ong.listado_ofertas')
            )

        except ValueError as e:

            flash(str(e), 'error')

            return redirect(
                url_for('ong.crear_oferta', convocatoria_id=convocatoria.id)
            )

    inventario_ong = inventario.listar_inventario(ong_id)

    return render_template(
        'ofertas/crear_oferta.html',
        inventario=inventario_ong,
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

        oferta, version_actual = (
            ofertas.obtener_oferta_para_modificar(
                id_oferta=id_oferta,
                id_ong=ong_id
            )
        )

    except ValueError as e:

        flash(str(e), 'error')

        return redirect(
            url_for('ong.listado_ofertas')
        )

    if request.method == 'POST':

        # Recursos elegidos
        ids_recursos = request.form.getlist(
            'id_recurso'
        )

        recursos = []

        for id_recurso in ids_recursos:

            try:

                id_recurso = int(id_recurso)

                cantidad = int(
                    request.form.get(
                        f'cantidad_{id_recurso}',
                        '0'
                    )
                )

            except (TypeError, ValueError):

                flash(
                    'La cantidad de los recursos debe ser válida.',
                    'error'
                )

                return redirect(
                    url_for(
                        'ong.modificar_oferta',
                        id_oferta=id_oferta
                    )
                )

            recursos.append({
                'id_recurso': id_recurso,
                'cantidad': cantidad
            })

        # Modificar oferta
        try:

            oferta = ofertas.modificar_oferta(
                id_oferta=id_oferta,
                recursos=recursos,
                ong_id=ong_id,
                usuario_id=current_user.id,
            )

            flash(
                f'Oferta #{oferta.id_oferta} modificada correctamente.',
                'success'
            )

            return redirect(
                url_for('ong.listado_ofertas')
            )

        except ValueError as e:

            flash(str(e), 'error')

            return redirect(
                url_for(
                    'ong.modificar_oferta',
                    id_oferta=id_oferta
                )
            )

    #Lo que queda con GET
    lista_emergencias = (
        emergencias.listar_todas_las_emergencias()
    )

    inventario_ong = inventario.listar_inventario(ong_id)

    return render_template(
        'ofertas/modificar_oferta.html',
        oferta=oferta,
        version_actual=version_actual,
        emergencias=lista_emergencias,
        inventario=inventario_ong
    )