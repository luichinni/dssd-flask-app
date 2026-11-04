from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from src.core.enums import RolEnum
from src.core.models.recurso_catalogo import RecursoCatalogo
from src.core.services.lotes import (
    cantidades_ofertadas_por_recurso,
    continuar_con_ofertas_disponibles,
    emergencia_activa,
    estado_lote,
    evaluar_minimos_lote,
    listar_emergencias_activas,
    listar_emergencias,
    listar_lotes,
    lote_requiere_decision,
    obtener_lote,
    publicar_lote,
    reabrir_convocatoria,
    reformular_lote,
    reintentar_lote,
)
from src.web.decorators.roles_required import roles_required
from src.core.enums import AccionPostOfertaEnum
from src.core.services.bonita import BonitaError, completar_decision_post_convocatoria
from src.core.services.lotes import _utc

ccr_bp = Blueprint('ccr', __name__, url_prefix='/ccr')


@ccr_bp.get('/')
@login_required
@roles_required(RolEnum.CENTRO_COORDINADOR)
def dashboard():
    emergencias = listar_emergencias()
    estados_emergencias = {
        emergencia.id: 'activa' if emergencia_activa(emergencia) else 'inactiva'
        for emergencia in emergencias
    }
    lotes_vigentes = [
        lote for lote in listar_lotes()
        if estado_lote(lote) == 'publicado'
    ]
    return render_template(
        'ccr/dashboard.html',
        emergencias=emergencias,
        estados_emergencias=estados_emergencias,
        lotes_vigentes=lotes_vigentes,
    )


@ccr_bp.route('/lotes', methods=['GET', 'POST'])
@login_required
@roles_required(RolEnum.CENTRO_COORDINADOR)
def lotes():
    emergencias = listar_emergencias_activas()
    recursos = RecursoCatalogo.query.order_by(RecursoCatalogo.nombre.asc()).all()
    publicaciones = listar_lotes()
    estados = {lote.id: estado_lote(lote) for lote in publicaciones}
    reintento_cierres = {
        lote.id: (datetime.now(timezone.utc) + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M')
        for lote in publicaciones
    }

    if request.method == 'POST':
        try:
            emergencia_id = int(request.form.get('emergencia_id', ''))
            recurso_ids = request.form.getlist('recurso_id')
            cantidades = request.form.getlist('cantidad_necesaria')
            minimos = request.form.getlist('min_r')
            if not (len(recurso_ids) == len(cantidades) == len(minimos)):
                raise ValueError('Completa recurso, cantidad y mínimo requerido para cada fila.')
            detalles = [
                {
                    'recurso_id': recurso_id,
                    'cantidad_necesaria': cantidad,
                    'min_r': min_r,
                }
                for recurso_id, cantidad, min_r in zip(recurso_ids, cantidades, minimos)
            ]
            fecha_cierre = datetime.fromisoformat(request.form.get('fecha_cierre_ofertas', ''))
            lote = publicar_lote(
                emergencia_id=emergencia_id,
                detalles=detalles,
                fecha_cierre_ofertas=fecha_cierre,
            )
        except ValueError as error:
            flash(str(error), 'error')
        except SQLAlchemyError:
            flash('No se pudo publicar el lote. Inténtalo nuevamente.', 'error')
        else:
            if lote.bonita_estado == "sincronizado":
                flash(f'Lote #{lote.id} publicado. Crear lotes de necesidades y Publicar convocatoria completadas en Bonita.', 'success')
            else:
                flash(f'Lote #{lote.id} guardado y publicado en la app, pero el avance en Bonita no quedó confirmado. Revisá el caso y los logs antes de volver a publicarlo.', 'error')
            return redirect(url_for('ccr.lotes'))

    default_cierre = (datetime.now(timezone.utc) + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M')
    return render_template(
        'ccr/lotes.html',
        emergencias=emergencias,
        recursos=recursos,
        default_cierre=default_cierre,
        publicaciones=publicaciones,
        estados=estados,
        reintento_cierres=reintento_cierres,
    )


@ccr_bp.get('/lotes/<int:lote_id>/evaluar')
@login_required
@roles_required(RolEnum.CENTRO_COORDINADOR)
def evaluar_convocatoria(lote_id: int):
    lote = obtener_lote(lote_id)
    if lote is None:
        flash('La convocatoria seleccionada no existe.', 'error')
        return redirect(url_for('ccr.lotes'))

    estado = estado_lote(lote)
    if estado != 'vencido':
        flash('La convocatoria todavía no finalizó.', 'info')
        return redirect(url_for('ccr.lotes'))

    cantidades = cantidades_ofertadas_por_recurso(lote.emergencia_id)
    evaluacion = evaluar_minimos_lote(lote, cantidades)
    return render_template(
        'ccr/evaluar_convocatoria.html',
        lote=lote,
        evaluacion=evaluacion,
        requiere_decision=lote_requiere_decision(lote, cantidades),
        reintento_cierre=(datetime.now(timezone.utc) + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M'),
        recursos=RecursoCatalogo.query.order_by(RecursoCatalogo.nombre.asc()).all(),
    )


@ccr_bp.post('/lotes/<int:lote_id>/decision')
@login_required
@roles_required(RolEnum.CENTRO_COORDINADOR)
def decidir_lote(lote_id: int):
    decision_enum = None
    lote = None

    try:
        decision = request.form.get('decision', '').strip().lower()

        if decision == 'reabrir':
            decision_enum = AccionPostOfertaEnum.REABRIR
            fecha_cierre = datetime.fromisoformat(request.form.get('fecha_cierre_ofertas', ''))
            fecha_cierre = _utc(fecha_cierre)
            lote = reabrir_convocatoria(lote_id, fecha_cierre)
            mensaje = f'Convocatoria del lote #{lote.id} reabierta sin modificar sus recursos.'

        elif decision == 'reformular':
            decision_enum = AccionPostOfertaEnum.REFORMULAR
            recurso_ids = request.form.getlist('recurso_id')
            cantidades = request.form.getlist('cantidad_necesaria')
            minimos = request.form.getlist('min_r')
            if not (len(recurso_ids) == len(cantidades) == len(minimos)):
                raise ValueError('Completa recurso, cantidad y mínimo requerido para cada fila.')
            detalles = [
                {
                    'recurso_id': recurso_id,
                    'cantidad_necesaria': cantidad,
                    'min_r': min_r,
                }
                for recurso_id, cantidad, min_r in zip(recurso_ids, cantidades, minimos)
            ]
            fecha_cierre = datetime.fromisoformat(request.form.get('fecha_cierre_ofertas', ''))
            fecha_cierre = _utc(fecha_cierre)
            lote = reformular_lote(lote_id, detalles, fecha_cierre)
            mensaje = f'Lote #{lote.id} reformulado y publicado nuevamente.'

        elif decision == 'continuar':
            decision_enum = AccionPostOfertaEnum.CONTINUAR
            aceptadas = continuar_con_ofertas_disponibles(lote_id)
            lote = obtener_lote(lote_id)
            mensaje = f'Se continúa con las ofertas disponibles; {aceptadas} oferta(s) pendiente(s) aceptada(s).'

        else:
            raise ValueError('Selecciona una alternativa válida para el lote.')

    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('ccr.lotes'))
    except SQLAlchemyError:
        flash('No se pudo aplicar la decisión del lote en la base de datos. Inténtalo nuevamente.', 'error')
        return redirect(url_for('ccr.lotes'))

    # Sincronización con Bonita BPM:
    # Se ejecuta luego de persistir la decisión en la BD local.
    # Sincronización con Bonita BPM:
    try:
        if not lote or not lote.emergencia:
            raise BonitaError("No se pudo recuperar la emergencia asociada al lote.")
        
        case_id = lote.emergencia.bonita_case_id
        if not case_id:
            raise BonitaError(f"La emergencia #{lote.emergencia_id} no posee un caso de Bonita asociado.")

        # Pasamos la fecha si fue reapertura o reformulación, o None si fue continuar
        nueva_fecha = fecha_cierre if decision_enum in (AccionPostOfertaEnum.REABRIR, AccionPostOfertaEnum.REFORMULAR) else None
        
        completar_decision_post_convocatoria(case_id, decision_enum, nueva_fecha)
        flash(f'{mensaje} Se avanzó la tarea en Bonita con la decisión {decision_enum.value}.', 'success')
    except BonitaError as err:
        flash(f'{mensaje} Sin embargo, no se pudo confirmar el avance en Bonita: {err}', 'error')

    return redirect(url_for('ccr.lotes'))


@ccr_bp.post('/lotes/<int:lote_id>/reintentar')
@login_required
@roles_required(RolEnum.CENTRO_COORDINADOR)
def reintentar(lote_id: int):
    try:
        fecha_cierre = datetime.fromisoformat(request.form.get('fecha_cierre_ofertas', ''))
        recurso_id_text = request.form.get('recurso_id', '').strip()
        cantidad_text = request.form.get('cantidad_necesaria', '').strip()
        min_r_text = request.form.get('min_r', '').strip()
        lote = reintentar_lote(
            lote_id=lote_id,
            fecha_cierre_ofertas=fecha_cierre,
            recurso_id=int(recurso_id_text) if recurso_id_text else None,
            cantidad_necesaria=int(cantidad_text) if cantidad_text else None,
            min_r=int(min_r_text) if min_r_text else None,
        )
    except ValueError as error:
        flash(str(error), 'error')
    except SQLAlchemyError:
        flash('No se pudo reabrir el lote. Inténtalo nuevamente.', 'error')
    else:
        flash(f'Lote #{lote.id} reintentado o reabierto correctamente.', 'success')
    return redirect(url_for('ccr.lotes'))