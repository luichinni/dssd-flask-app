from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from src.core.enums import RolEnum, TipoRecursoEnum, EstadoActividadEnum
from src.web.decorators.roles_required import roles_required
from src.core.services import inventario, notificaciones, actividades, ofertas, emergencias

ong_bp = Blueprint('ong', __name__, url_prefix='/ong')

# ==============================================================================
# INVENTARIO
# ==============================================================================

@ong_bp.route('/inventario')
@login_required
@roles_required(RolEnum.ONG)
def inventario_index():
    items = inventario.listar_inventario(current_user.id)
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

        inventario.crear_recurso(current_user.id, {
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
    recurso = inventario.obtener_recurso(id, current_user.id)
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

        inventario.actualizar_recurso(id, current_user.id, {
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
    exito = inventario.eliminar_recurso(id, current_user.id)
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
    estado_filtro = request.args.get('estado')
    enum_filtro = None
    if estado_filtro == 'en_ejecucion':
        enum_filtro = EstadoActividadEnum.EN_EJECUCION
    elif estado_filtro == 'finalizada':
        enum_filtro = EstadoActividadEnum.FINALIZADA

    lista = actividades.listar_actividades(current_user.id, estado=enum_filtro)
    en_curso_cant = len([a for a in actividades.listar_actividades(current_user.id, estado=EstadoActividadEnum.EN_EJECUCION)])
    finalizadas_cant = len([a for a in actividades.listar_actividades(current_user.id, estado=EstadoActividadEnum.FINALIZADA)])

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
    actividad = actividades.obtener_actividad(id, current_user.id)
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
            ong_id=current_user.id,
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

    if request.method == 'POST':

        # Info general
        id_emergencia = request.form.get('id_emergencia')

        es_conjunta_str = request.form.get(
            'es_conjunta',
            'false'
        )

        es_conjunta = (
            es_conjunta_str.lower() == 'true'
        )

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
                    url_for('ong.crear_oferta')
                )

            recursos.append({
                'id_recurso': id_recurso,
                'cantidad': cantidad
            })

        # Crear oferta
        try:

            oferta = ofertas.crear_oferta(
                id_emergencia=id_emergencia,
                es_conjunta=es_conjunta,
                recursos=recursos,
                id_ong=current_user.id
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
                url_for('ong.crear_oferta')
            )

    #Lo que sigue con Get
    lista_emergencias = (
        emergencias.listar_todas_las_emergencias()
    )

    inventario_ong = inventario.listar_inventario(
        current_user.id
    )

    return render_template(
        'ofertas/crear_oferta.html',
        emergencias=lista_emergencias,
        inventario=inventario_ong
    )

@ong_bp.route('/ofertas/listado', methods=['GET'])
@login_required
@roles_required(RolEnum.ONG)
def listado_ofertas():
    lista = ofertas.listar_ofertas()

    return render_template('ofertas/listado_ofertas.html', ofertas=lista)

@ong_bp.route('/ofertas/<int:id_oferta>/modificar', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.ONG)
def modificar_oferta(id_oferta):

    # Obtener oferta y verificar que la ONG participe
    try:

        oferta, version_actual = (
            ofertas.obtener_oferta_para_modificar(
                id_oferta=id_oferta,
                id_ong=current_user.id
            )
        )

    except ValueError as e:

        flash(str(e), 'error')

        return redirect(
            url_for('ong.listado_ofertas')
        )

    if request.method == 'POST':

        es_conjunta_str = request.form.get(
            'es_conjunta',
            'false'
        )

        es_conjunta = (
            es_conjunta_str.lower() == 'true'
        )

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
                es_conjunta=es_conjunta,
                recursos=recursos,
                id_ong=current_user.id
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

    inventario_ong = inventario.listar_inventario(
        current_user.id
    )

    return render_template(
        'ofertas/modificar_oferta.html',
        oferta=oferta,
        version_actual=version_actual,
        emergencias=lista_emergencias,
        inventario=inventario_ong
    )