from datetime import datetime, timedelta, timezone
from src.core.models import (
    Usuario,
    ONG,
    InventarioONG,
    RecursoCatalogo,
    Notificacion,
    ActividadONG,
    Emergencia,
    Municipio,
    LoteNecesidades,
    LoteDetalle,
    Oferta,
    VersionOferta,
    DetalleVersionOferta,
    OfertaParticipante,
)
from src.core.enums import (
    RolEnum,
    TipoRecursoEnum,
    TipoNotificacionEnum,
    EstadoActividadEnum,
    TipoDesastreEnum,
    EstadoOfertaEnum,
    NivelGravedadEnum,
)
from src.core.database import db
from src.core.timezone import ahora_ar


def seed(app):
    """Función para inicializar la base de datos y cargar datos iniciales (seeding)."""
    with app.app_context():
        print("🌱 Iniciando carga de datos iniciales (Seeding)...")
        seed_users()
        seed_ongs()
        seed_municipios()
        seed_ong_data()
        seed_emergencies_data()
        print('🌱 Seedeando datos de Ofertas...')
        seed_ccr_data()
        seed_ofertas_data()
        seed_oferta_colaborativa_data()
        seed_reportes_historico()
        print("🌱 Finalización de la carga de datos iniciales (Seeding)!")

def seed_users():
    print('🌱 Seedeando usuarios por cada rol...')

    ong = ONG.query.filter_by(nombre='Red de Apoyo Comunitario').first()
    if not ong:
        ong = ONG(nombre='Red de Apoyo Comunitario', descripcion='12345/2020')
        db.session.add(ong)

    ong_colaboradora = ONG.query.filter_by(nombre='Brigada Humanitaria Federal').first()
    if not ong_colaboradora:
        ong_colaboradora = ONG(
            nombre='Brigada Humanitaria Federal',
            descripcion='ONG colaboradora de prueba',
        )
        db.session.add(ong_colaboradora)

    municipio = Municipio.query.filter_by(nombre='Sin asignar', provincia='Sin asignar').first()
    if not municipio:
        municipio = Municipio(nombre='Sin asignar', provincia='Sin asignar')
        db.session.add(municipio)
    db.session.flush()

    usuarios_base = [
        {
            'nombre': 'Operador Municipal',
            'email': 'operador@municipio.gob.ar',
            'password': 'Operador2026!',
            'rol': RolEnum.OPERADOR_MUNICIPAL,
            'datos_adicionales': {'municipio_id': municipio.id},
        },
        {
            'nombre': 'Centro Coordinador',
            'email': 'coordinador@emergencias.gob.ar',
            'password': 'Coordinador2026!',
            'rol': RolEnum.CENTRO_COORDINADOR,
            'datos_adicionales': {'centro_id': 1, 'sede': 'Central'},
        },
        {
            'nombre': 'Representante ONG',
            'email': 'ong@ayuda.org',
            'password': 'Ong2026!',
            'rol': RolEnum.ONG,
            'datos_adicionales': {'ong_id': ong.id},
        },
        {
            'nombre': 'Representante ONG Colaboradora',
            'email': 'colaboradora@ayuda.org',
            'password': 'Colaboradora2026!',
            'rol': RolEnum.ONG,
            'datos_adicionales': {'ong_id': ong_colaboradora.id},
        },
        {
            'nombre': 'Auditor General',
            'email': 'auditor@gmail.com',
            'password': 'Auditor2026!',
            'rol': RolEnum.AUDITOR,
            'datos_adicionales': {'departamento': 'Auditoría Interna'},
        },
    ]

    for datos in usuarios_base:
        usuario = Usuario.query.filter_by(email=datos['email']).first()

        if not usuario:
            usuario = Usuario(
                nombre=datos['nombre'],
                email=datos['email'],
                rol=datos['rol'],
                datos_adicionales=datos['datos_adicionales'],
            )
            usuario.set_password(datos['password'])

            db.session.add(usuario)
            print(f"  [+] Creado: {datos['email']} ({datos['rol'].value})")
        else:
            if datos['rol'] in (RolEnum.ONG, RolEnum.OPERADOR_MUNICIPAL):
                usuario.datos_adicionales = datos['datos_adicionales']
            print(f"  [-] El usuario ({datos['email']}) ya existe.")

    db.session.commit()

def seed_ongs():
    print('🌱 Seedeando perfiles de ONG...')
    usuarios = Usuario.query.filter_by(rol=RolEnum.ONG).all()

    for usuario in usuarios:
        ong_id = (usuario.datos_adicionales or {}).get('ong_id')
        if ong_id is None:
            continue

        ong_id = int(ong_id)
        if db.session.get(ONG, ong_id) is None:
            db.session.add(ONG(id=ong_id, nombre=usuario.nombre))
            print(f'  [+] ONG creada para el ID {ong_id}: {usuario.nombre}')

    db.session.commit()

def seed_municipios():
    print('🌱 Seedeando municipios...')
    usuarios = Usuario.query.filter_by(rol=RolEnum.OPERADOR_MUNICIPAL).all()

    for usuario in usuarios:
        municipio_id = (usuario.datos_adicionales or {}).get('municipio_id')
        if municipio_id is None:
            continue

        municipio_id = int(municipio_id)
        if db.session.get(Municipio, municipio_id) is None:
            db.session.add(Municipio(
                id=municipio_id,
                nombre='Sin asignar',
                provincia='Sin asignar',
            ))
            print(f'  [+] Municipio creado para el ID {municipio_id}')

    db.session.commit()

def seed_ong_data():
    print('🌱 Seedeando datos de ONG (inventario, notificaciones, actividades)...')
    ong = Usuario.query.filter_by(email='ong@ayuda.org').first()
    if not ong:
        print('  [!] Usuario ONG no encontrado. Saltando seeding de ONG.')
        return

    # 1. Inventario
    ong_id = (ong.datos_adicionales or {}).get('ong_id')
    ong_profile = db.session.get(ONG, int(ong_id)) if ong_id is not None else None
    if not ong_profile:
        print('  [!] Perfil de ONG no encontrado. Saltando seeding de ONG.')
        return

    recursos_base = [
        {
            'nombre': 'Paramédicos de Emergencia',
            'tipo_recurso': TipoRecursoEnum.PERSONAL,
            'unidad_medida': 'Personas',
            'cantidad_total': 15,
            'cantidad_disponible': 10,
            'descripcion': 'Personal certificado en primeros auxilios avanzados y triage en desastres.',
        },
        {
            'nombre': 'Raciones de Alimento Seco',
            'tipo_recurso': TipoRecursoEnum.INSUMO,
            'unidad_medida': 'Raciones',
            'cantidad_total': 2500,
            'cantidad_disponible': 2500,
            'descripcion': 'Raciones con valor calórico garantizado de 2200 kcal para 72 horas.',
        },
        {
            'nombre': 'Ambulancia de Traslado 4x4',
            'tipo_recurso': TipoRecursoEnum.VEHICULO,
            'unidad_medida': 'Vehículos',
            'cantidad_total': 3,
            'cantidad_disponible': 2,
            'descripcion': 'Equipadas con desfibrilador y tracción integral apta para terrenos anegados.',
        },
        {
            'nombre': 'Carpas Sanitarias de Campaña',
            'tipo_recurso': TipoRecursoEnum.EQUIPAMIENTO,
            'unidad_medida': 'Carpas',
            'cantidad_total': 6,
            'cantidad_disponible': 5,
            'descripcion': 'Carpas modulares impermeables con capacidad de 10 camillas cada una.',
        },
    ]

    for r_data in recursos_base:
        existente = InventarioONG.query.join(RecursoCatalogo).filter(
            InventarioONG.ong_id == ong_profile.id,
            RecursoCatalogo.nombre == r_data['nombre'],
        ).first()
        if not existente:
            catalogo = RecursoCatalogo(
                nombre=r_data['nombre'],
                tipo_recursos=r_data['tipo_recurso'],
                unidad_medida=r_data['unidad_medida'],
                descripcion=r_data['descripcion'],
            )
            recurso = InventarioONG(
                ong=ong_profile,
                recurso=catalogo,
                cantidad_total=r_data['cantidad_total'],
                cantidad_disponible=r_data['cantidad_disponible'],
            )
            db.session.add(recurso)
            print(f"  [+] Inventario creado: {r_data['nombre']}")

    # 2. Notificaciones
    notificaciones_base = [
        {
            'titulo': 'Adjudicación de Lote: 5 Paramédicos y 1 Ambulancia',
            'mensaje': 'El Municipio de Quilmes ha seleccionado su oferta para el Lote #104 (Respuesta a Inundación Ribereña). Se solicita el despliegue inmediato en el centro de coordinación local.',
            'tipo': TipoNotificacionEnum.ADJUDICACION_LOTE,
            'referencia_id': 104,
            'leida': False,
            'dias_atras': 0,
        },
        {
            'titulo': 'Aviso de Convocatoria Abierta: Temporal Zona Oeste',
            'mensaje': 'Se ha abierto una nueva convocatoria regional con 4 lotes disponibles para recepción de ofertas colaborativas durante las próximas 48 horas.',
            'tipo': TipoNotificacionEnum.CONVOCATORIA,
            'referencia_id': 101,
            'leida': True,
            'dias_atras': 2,
        },
    ]

    for n_data in notificaciones_base:
        existente = Notificacion.query.filter_by(usuario_id=ong.id, titulo=n_data['titulo']).first()
        if not existente:
            notif = Notificacion(
                usuario_id=ong.id,
                titulo=n_data['titulo'],
                mensaje=n_data['mensaje'],
                tipo=n_data['tipo'],
                referencia_id=n_data['referencia_id'],
                leida=n_data['leida'],
                created_at=ahora_ar() - timedelta(days=n_data['dias_atras']),
            )
            db.session.add(notif)
            print(f"  [+] Notificación creada: {n_data['titulo']}")

    # 3. Actividades
    actividades_base = [
        {
            'titulo': 'Operativo de Asistencia y Triage - Ribera Quilmes',
            'descripcion': 'Despliegue de equipo médico para atención de familias evacuadas por desborde del río.',
            'lote_referencia': 'LOTE-104-MED',
            'estado': EstadoActividadEnum.EN_EJECUCION,
            'fecha_inicio': ahora_ar() - timedelta(hours=18),
            'fecha_finalizacion': None,
            'informe_cierre': None,
            'recursos_utilizados': '5 Paramédicos, 1 Ambulancia 4x4, 1 Carpa Sanitaria',
        },
        {
            'titulo': 'Distribución de Alimentos y Abrigo - Temporal La Plata',
            'descripcion': 'Reparto de raciones calóricas y frazadas en centros comunitarios.',
            'lote_referencia': 'LOTE-098-ALIM',
            'estado': EstadoActividadEnum.FINALIZADA,
            'fecha_inicio': ahora_ar() - timedelta(days=5),
            'fecha_finalizacion': ahora_ar() - timedelta(days=3),
            'informe_cierre': 'Se distribuyeron 1200 raciones en 3 centros comunitarios designados. Cobertura al 100% de la población censada sin incidentes de gravedad.',
            'recursos_utilizados': '1200 Raciones de Alimento Seco, 4 Voluntarios',
        },
    ]

    for a_data in actividades_base:
        existente = ActividadONG.query.filter_by(ong_id=ong_profile.id, titulo=a_data['titulo']).first()
        if not existente:
            act = ActividadONG(
                ong_id=ong_profile.id,
                titulo=a_data['titulo'],
                descripcion=a_data['descripcion'],
                lote_referencia=None,
                estado=a_data['estado'],
                fecha_inicio=a_data['fecha_inicio'],
                fecha_finalizacion=a_data['fecha_finalizacion'],
                informe_cierre=a_data['informe_cierre'],
                recursos_utilizados={'descripcion': a_data['recursos_utilizados']},
            )
            db.session.add(act)
            print(f"  [+] Actividad creada: {a_data['titulo']} ({a_data['estado'].value})")

    db.session.commit()

def seed_emergencies_data():
    print('🌱 Seedeando datos de Emergencias...')
    #el operador municipal actua como el reportante de las emergencias
    operador = Usuario.query.filter_by(email='operador@municipio.gob.ar').first()

    if not operador:
        print('  [!] Usuario Operador Municipal no encontrado. Saltando seeding de Emergencias.')
        return
    municipio_id = (operador.datos_adicionales or {}).get('municipio_id')
    municipio = db.session.get(Municipio, int(municipio_id)) if municipio_id is not None else None
    if municipio is None:
        print('  [!] Municipio asociado al usuario no encontrado. Saltando seeding de Emergencias.')
        return

    emergencias_base = [
        {
            'tipo_desastre': TipoDesastreEnum.geologico,
            'nivel_gravedad': 4,
            'zona_afectada': 'Barrio Ribereño, Quilmes',
            'descripcion': 'Terremoto de magnitud 5.2 con daños estructurales leves en viviendas y cortes de energía eléctrica.',
            'reportante_id': operador.id
        },
        {
            'tipo_desastre': TipoDesastreEnum.meteorologico,
            'nivel_gravedad': 1,
            'zona_afectada': 'Zona Forestal, La Plata',
            'descripcion': 'Tormenta severa con ráfagas de viento de hasta 120 km/h, caída de árboles y voladura de techos en varias viviendas.',
            'reportante_id': operador.id
        },
        {
            'tipo_desastre': TipoDesastreEnum.hidrologico,
            'nivel_gravedad': 3,
            'zona_afectada': 'Centro Urbano, San Juan',
            'descripcion': 'Inundación por lluvias intensas que ha provocado el desbordamiento de ríos y la afectación de zonas residenciales.',
            'reportante_id': operador.id
        },
        {
            'tipo_desastre': TipoDesastreEnum.biologico,
            'nivel_gravedad': 4,
            'zona_afectada': 'Zona Rural, Rosario',
            'descripcion': 'Brote de enfermedad zoonótica que ha afectado a ganado y ha generado alerta sanitaria en la región.',
            'reportante_id': operador.id
        },
        {
            'tipo_desastre': TipoDesastreEnum.incendio_forestal,
            'nivel_gravedad': 2,
            'zona_afectada': 'Parque Nacional, Mendoza',
            'descripcion': 'Incendio forestal de gran magnitud con evacuación de campamentos y riesgo para fauna local.',
            'reportante_id': operador.id
        },
    ]

    for e_data in emergencias_base:
        existente = Emergencia.query.filter_by(zona_afectada=e_data['zona_afectada'], tipo_desastre=e_data['tipo_desastre']).first()
        if not existente:
            emergencia = Emergencia(
                tipo_desastre=e_data['tipo_desastre'],
                nivel_gravedad=e_data['nivel_gravedad'],
                zona_afectada=e_data['zona_afectada'],
                descripcion=e_data['descripcion'],
                reportante_id=e_data['reportante_id'],
                municipio_id=municipio.id,
            )
            db.session.add(emergencia)
            print(f"  [+] Emergencia creada: {e_data['zona_afectada']} ({e_data['tipo_desastre'].value})")

    db.session.commit()


def seed_ofertas_data():
    ong_usuario = Usuario.query.filter_by(email='ong@ayuda.org').first()
    emergencia = Emergencia.query.filter_by(zona_afectada='CCR - Convocatoria publicada').first()
    if ong_usuario is None or emergencia is None:
        print('  [!] Falta el usuario ONG o la emergencia seed. Se omite la oferta adjudicable.')
        return

    try:
        ong_id = int((ong_usuario.datos_adicionales or {}).get('ong_id'))
    except (TypeError, ValueError):
        print('  [!] El usuario ONG no tiene un perfil asociado.')
        return

    ong_profile = db.session.get(ONG, ong_id)
    municipio_id = (emergencia.responsable.datos_adicionales or {}).get('municipio_id')
    municipio = db.session.get(Municipio, int(municipio_id)) if municipio_id is not None else None
    recurso = RecursoCatalogo.query.filter_by(nombre='Paramédicos de Emergencia').first()
    ccr_usuario = Usuario.query.filter_by(rol=RolEnum.CENTRO_COORDINADOR).first()
    if not ong_profile or not municipio or not recurso or not ccr_usuario:
        print('  [!] Faltan ONG, municipio, recurso o usuario CCR para la oferta seed.')
        return

    lote = LoteNecesidades.query.filter_by(emergencia_id=emergencia.id).first()
    if lote is None:
        lote = LoteNecesidades(
            emergencia=emergencia,
            fecha_inicio_ofertas=ahora_ar() - timedelta(hours=1),
            fecha_cierre_ofertas=ahora_ar() + timedelta(days=2),
        )
        lote.detalles.append(LoteDetalle(
            recurso=recurso,
            cantidad_necesaria=40,
            cantidad_minima=15,
        ))
        db.session.add(lote)
        db.session.flush()

    inventario = InventarioONG.query.filter_by(
        ong_id=ong_id,
        id_recurso=recurso.id,
    ).first()
    if inventario is None:
        inventario = InventarioONG(
            ong_id=ong_id,
            recurso=recurso,
            cantidad_total=15,
            cantidad_disponible=15,
        )
        db.session.add(inventario)
        db.session.flush()

    cantidad_seed = min(10, inventario.cantidad_disponible)
    if cantidad_seed <= 0:
        print('  [!] Sin stock disponible. Se conserva la oferta adjudicable existente.')
        db.session.commit()
        return

    oferta = Oferta.query.filter_by(
        convocatoria_id=lote.id,
        creada_por_ong_id=ong_id,
    ).first()
    if oferta is None:
        oferta = Oferta(
            id_emergencia=emergencia.id,
            convocatoria_id=lote.id,
            creada_por_ong_id=ong_id,
            estado=EstadoOfertaEnum.ACEPTADA,
            version_actual=1,
            es_conjunta=False,
        )
        db.session.add(oferta)
        db.session.flush()

    oferta.id_emergencia = emergencia.id
    oferta.convocatoria_id = lote.id
    oferta.creada_por_ong_id = ong_id
    oferta.estado = EstadoOfertaEnum.ACEPTADA
    oferta.es_conjunta = False

    version = VersionOferta.query.filter_by(
        id_oferta=oferta.id,
        numero_version=oferta.version_actual,
    ).first()
    if version is None:
        version = VersionOferta(
            id_oferta=oferta.id,
            numero_version=oferta.version_actual,
            usuario_modificacion=ong_usuario.id,
            observaciones='Seed: oferta validada para adjudicación municipal',
        )
        db.session.add(version)
        db.session.flush()
    version.usuario_modificacion = ong_usuario.id
    version.estado_versiones = EstadoOfertaEnum.ACEPTADA.value
    version.observaciones = 'Seed: oferta validada para adjudicación municipal'

    detalle = next((
        item for item in version.detalles
        if item.id_ong == ong_id and item.id_recurso == recurso.id
    ), None)
    if detalle is None:
        version.detalles.append(DetalleVersionOferta(
            id_ong=ong_id,
            id_recurso=recurso.id,
            cantidad=cantidad_seed,
            cantidad_adjudicada=0,
        ))
    else:
        detalle.cantidad = cantidad_seed
        detalle.cantidad_adjudicada = 0

    for detalle_extra in list(version.detalles):
        if detalle_extra.id_ong != ong_id or detalle_extra.id_recurso != recurso.id:
            version.detalles.remove(detalle_extra)

    participante = OfertaParticipante.query.filter_by(
        oferta_id=oferta.id,
        ong_id=ong_id,
    ).first()
    if participante is None:
        db.session.add(OfertaParticipante(
            oferta_id=oferta.id,
            ong_id=ong_id,
            estado='Aceptada',
        ))
    else:
        participante.estado = 'Aceptada'

    db.session.commit()


def seed_ccr_data():
    print('🌱 Seedeando escenarios CCR...')
    operador = Usuario.query.filter_by(email='operador@municipio.gob.ar').first()
    ong_usuario = Usuario.query.filter_by(email='ong@ayuda.org').first()
    if not operador or not ong_usuario:
        print('  [!] Faltan usuarios CCR/ONG. Saltando escenarios CCR.')
        return

    municipio_id = (operador.datos_adicionales or {}).get('municipio_id')
    ong_id = (ong_usuario.datos_adicionales or {}).get('ong_id')
    municipio = db.session.get(Municipio, int(municipio_id)) if municipio_id is not None else None
    ong = db.session.get(ONG, int(ong_id)) if ong_id is not None else None
    recurso_publicado = RecursoCatalogo.query.filter_by(nombre='Paramédicos de Emergencia').first()
    recurso_decision = RecursoCatalogo.query.filter_by(nombre='Raciones de Alimento Seco').first()
    if not municipio or not ong or not recurso_publicado or not recurso_decision:
        print('  [!] Faltan municipio, perfil ONG o recursos de catálogo. Saltando escenarios CCR.')
        return

    emergencias = {}
    datos_emergencias = (
        ('CCR - Convocatoria publicada', 'Escenario seed CCR con convocatoria vigente.'),
        ('CCR - Mínimos pendientes', 'Escenario seed CCR vencido con ofertas por debajo de min_r.'),
    )
    for zona, descripcion in datos_emergencias:
        emergencia = Emergencia.query.filter_by(zona_afectada=zona).first()
        if emergencia is None:
            emergencia = Emergencia(
                tipo_desastre=TipoDesastreEnum.hidrologico,
                nivel_gravedad=2,
                zona_afectada=zona,
                descripcion=descripcion,
                responsable_id=operador.id,
                municipio_id=municipio.id,
            )
            db.session.add(emergencia)
        emergencias[zona] = emergencia
    db.session.flush()

    ahora = ahora_ar()
    escenarios_lotes = (
        (emergencias['CCR - Convocatoria publicada'], recurso_publicado, 40, 15,
         ahora - timedelta(hours=1), ahora + timedelta(days=7)),
        (emergencias['CCR - Mínimos pendientes'], recurso_decision, 100, 20,
         ahora - timedelta(days=2), ahora - timedelta(hours=1)),
    )
    lotes = []
    for emergencia, recurso, cantidad, min_r, inicio, cierre in escenarios_lotes:
        lote = LoteNecesidades.query.filter_by(emergencia_id=emergencia.id).first()
        if lote is None:
            lote = LoteNecesidades(emergencia=emergencia)
            db.session.add(lote)
        lote.fecha_inicio_ofertas = inicio
        lote.fecha_cierre_ofertas = cierre
        lote.detalles.clear()
        lote.detalles.append(LoteDetalle(
            recurso=recurso,
            cantidad_necesaria=cantidad,
            cantidad_minima=min_r,
        ))
        lotes.append((lote, emergencia, recurso, min_r))
    db.session.flush()

    lote_decision, emergencia_decision, recurso_decision, _ = lotes[1]
    oferta = Oferta.query.filter_by(id_emergencia=emergencia_decision.id).first()
    if oferta is None:
        oferta = Oferta(emergencia=emergencia_decision)
        db.session.add(oferta)
        db.session.flush()
    oferta.estado = EstadoOfertaEnum.PENDIENTE
    oferta.version_actual = 1
    oferta.es_conjunta = False
    oferta.convocatoria_id = lote_decision.id
    oferta.creada_por_ong_id = ong.id

    version = VersionOferta.query.filter_by(id_oferta=oferta.id_oferta, numero_version=1).first()
    if version is None:
        version = VersionOferta(
            oferta=oferta,
            numero_version=1,
            usuario_modificacion=ong_usuario.id,
        )
        db.session.add(version)
    version.usuario_modificacion = ong_usuario.id
    version.estado_versiones = 'pendiente'
    version.observaciones = 'Seed CCR: convocatoria vencida bajo min_r'
    detalle_seed = next((
        detalle for detalle in version.detalles
        if detalle.id_ong == ong.id and detalle.id_recurso == recurso_decision.id
    ), None)
    if detalle_seed is None:
        version.detalles.append(DetalleVersionOferta(
            ong=ong,
            recurso=recurso_decision,
            cantidad=5,
            cantidad_adjudicada=0,
        ))
    else:
        detalle_seed.cantidad = 5
        detalle_seed.cantidad_adjudicada = 0
    participante = OfertaParticipante.query.filter_by(
        oferta_id=oferta.id,
        ong_id=ong.id,
    ).first()
    if participante is None:
        participante = OfertaParticipante(
            oferta_id=oferta.id,
            ong_id=ong.id,
            estado='Aceptada',
        )
        db.session.add(participante)
    else:
        participante.estado = 'Aceptada'

    lote_publicado, emergencia_publicada, recurso_publicado, min_publicado = lotes[0]
    titulo = f'Convocatoria CCR publicada #{lote_publicado.id}'
    notificacion = Notificacion.query.filter_by(usuario_id=ong_usuario.id, titulo=titulo).first()
    mensaje = (
        f'Convocatoria para la emergencia {emergencia_publicada.zona_afectada}: '
        f'{recurso_publicado.nombre}, mínimo requerido {min_publicado}.'
    )
    if notificacion is None:
        notificacion = Notificacion(
            usuario_id=ong_usuario.id,
            titulo=titulo,
            mensaje=mensaje,
            tipo=TipoNotificacionEnum.CONVOCATORIA,
            referencia_id=lote_publicado.id,
            leida=False,
        )
        db.session.add(notificacion)
    else:
        notificacion.mensaje = mensaje
        notificacion.tipo = TipoNotificacionEnum.CONVOCATORIA
        notificacion.referencia_id = lote_publicado.id
        notificacion.leida = False

    db.session.commit()


def seed_oferta_colaborativa_data():
    """Crea datos repetibles para probar una oferta compartida entre dos ONGs."""
    ong_usuario = Usuario.query.filter_by(email='ong@ayuda.org').first()
    colaboradora_usuario = Usuario.query.filter_by(email='colaboradora@ayuda.org').first()
    emergencia = Emergencia.query.filter_by(zona_afectada='CCR - Convocatoria publicada').first()
    if not ong_usuario or not colaboradora_usuario or not emergencia:
        print('  [!] Faltan usuarios ONG o emergencia publicada. Se omite la oferta colaborativa.')
        return

    ong_id = int((ong_usuario.datos_adicionales or {}).get('ong_id', 0))
    colaboradora_id = int((colaboradora_usuario.datos_adicionales or {}).get('ong_id', 0))
    ong = db.session.get(ONG, ong_id)
    ong_colaboradora = db.session.get(ONG, colaboradora_id)
    if not ong or not ong_colaboradora:
        print('  [!] Faltan perfiles de ONG. Se omite la oferta colaborativa.')
        return

    recurso_catalogo_ong = RecursoCatalogo.query.filter_by(
        nombre='Paramédicos de Emergencia'
    ).first()
    if recurso_catalogo_ong is None:
        recurso_catalogo_ong = RecursoCatalogo(
            nombre='Paramédicos de Emergencia',
            tipo_recursos=TipoRecursoEnum.PERSONAL,
            unidad_medida='Personas',
            descripcion='Personal médico de respuesta para escenarios colaborativos.',
        )
        db.session.add(recurso_catalogo_ong)

    recurso_catalogo_colaboradora = RecursoCatalogo.query.filter_by(
        nombre='Kits de Higiene Comunitarios'
    ).first()
    if recurso_catalogo_colaboradora is None:
        recurso_catalogo_colaboradora = RecursoCatalogo(
            nombre='Kits de Higiene Comunitarios',
            tipo_recursos=TipoRecursoEnum.INSUMO,
            unidad_medida='Kits',
            descripcion='Kits de higiene para familias afectadas.',
        )
        db.session.add(recurso_catalogo_colaboradora)
    db.session.flush()

    inventario_ong = InventarioONG.query.filter_by(
        ong_id=ong.id,
        id_recurso=recurso_catalogo_ong.id,
    ).first()
    if inventario_ong is None:
        inventario_ong = InventarioONG(
            ong_id=ong.id,
            recurso=recurso_catalogo_ong,
            cantidad_total=15,
            cantidad_disponible=15,
        )
        db.session.add(inventario_ong)

    inventario_colaboradora = InventarioONG.query.filter_by(
        ong_id=ong_colaboradora.id,
        id_recurso=recurso_catalogo_colaboradora.id,
    ).first()
    if inventario_colaboradora is None:
        inventario_colaboradora = InventarioONG(
            ong_id=ong_colaboradora.id,
            recurso=recurso_catalogo_colaboradora,
            cantidad_total=100,
            cantidad_disponible=100,
        )
        db.session.add(inventario_colaboradora)
    db.session.flush()

    observacion_seed = 'Seed: oferta colaborativa entre ONGs'
    lote_publicado = LoteNecesidades.query.filter_by(emergencia_id=emergencia.id).first()
    if lote_publicado is None:
        print('  [!] Falta la convocatoria publicada. Se omite la oferta colaborativa.')
        return

    version = VersionOferta.query.filter_by(observaciones=observacion_seed).first()
    if version is None:
        oferta = Oferta(
            id_emergencia=emergencia.id,
            convocatoria_id=lote_publicado.id,
            creada_por_ong_id=ong.id,
            estado=EstadoOfertaEnum.PENDIENTE,
            version_actual=1,
            es_conjunta=True,
        )
        db.session.add(oferta)
        db.session.flush()
        version = VersionOferta(
            id_oferta=oferta.id,
            numero_version=1,
            usuario_modificacion=ong_usuario.id,
            estado_version=EstadoOfertaEnum.PENDIENTE.value,
            observaciones=observacion_seed,
        )
        db.session.add(version)
        db.session.flush()
    else:
        oferta = version.oferta
        oferta.id_emergencia = emergencia.id
        oferta.convocatoria_id = lote_publicado.id
        oferta.creada_por_ong_id = ong.id
        oferta.estado = EstadoOfertaEnum.PENDIENTE
        oferta.es_conjunta = True
        oferta.version_actual = version.numero_version

    asignaciones_seed = (
        (ong.id, inventario_ong.id_recurso, 5),
        (ong_colaboradora.id, inventario_colaboradora.id_recurso, 20),
    )
    asignaciones_ids = {(participante_id, recurso_id) for participante_id, recurso_id, _ in asignaciones_seed}
    for participante_id, recurso_id, cantidad in asignaciones_seed:
        detalle = next((
            item for item in version.detalles
            if item.id_ong == participante_id and item.id_recurso == recurso_id
        ), None)
        if detalle is None:
            version.detalles.append(DetalleVersionOferta(
                id_ong=participante_id,
                id_recurso=recurso_id,
                cantidad=cantidad,
                cantidad_adjudicada=0,
            ))
        else:
            detalle.cantidad = cantidad
            detalle.cantidad_adjudicada = 0
    for detalle in list(version.detalles):
        if (detalle.id_ong, detalle.id_recurso) not in asignaciones_ids:
            version.detalles.remove(detalle)

    for participante_id in (ong.id, ong_colaboradora.id):
        participante = OfertaParticipante.query.filter_by(
            oferta_id=oferta.id,
            ong_id=participante_id,
        ).first()
        estado_participante = 'Aceptada' if participante_id == ong.id else 'Pendiente'
        if participante is None:
            db.session.add(OfertaParticipante(
                oferta_id=oferta.id,
                ong_id=participante_id,
                estado=estado_participante,
            ))
        else:
            participante.estado = estado_participante

    titulo = f'Participación en oferta #{oferta.id}'
    notificacion = Notificacion.query.filter_by(
        usuario_id=colaboradora_usuario.id,
        titulo=titulo,
    ).first()
    mensaje = f'Tu ONG fue incluida como participante en la oferta colaborativa #{oferta.id}.'
    if notificacion is None:
        notificacion = Notificacion(
            usuario_id=colaboradora_usuario.id,
            titulo=titulo,
            mensaje=mensaje,
            tipo=TipoNotificacionEnum.SISTEMA,
            referencia_id=oferta.id,
            leida=False,
        )
        db.session.add(notificacion)
    else:
        notificacion.mensaje = mensaje
        notificacion.referencia_id = oferta.id
        notificacion.leida = False

    db.session.commit()


def seed_reportes_historico():
    """Carga datos históricos idempotentes de emergencias, ofertas, consorcios y actividades para reportes."""
    print('🌱 Seedeando histórico para reportes de Auditoría/Dirección...')

    operador = Usuario.query.filter_by(email='operador@municipio.gob.ar').first()
    ong_principal = ONG.query.filter_by(nombre='Red de Apoyo Comunitario').first()
    ong_colab = ONG.query.filter_by(nombre='Brigada Humanitaria Federal').first()
    if not (operador and ong_principal and ong_colab):
        print('  [!] Faltan usuarios/ONGs base para seed_reportes_historico.')
        return

    ong_extra = ONG.query.filter_by(nombre='Cruz Verde Solidaria').first()
    if not ong_extra:
        ong_extra = ONG(nombre='Cruz Verde Solidaria', descripcion='ONG de respuesta rápida y logística')
        db.session.add(ong_extra)
        db.session.flush()

    municipios_seed = [
        ('La Plata', 'Buenos Aires'),
        ('Bahía Blanca', 'Buenos Aires'),
        ('Córdoba Capital', 'Córdoba'),
        ('Rosario', 'Santa Fe'),
    ]
    municipios_map = {}
    for nombre, provincia in municipios_seed:
        muni = Municipio.query.filter_by(nombre=nombre, provincia=provincia).first()
        if not muni:
            muni = Municipio(nombre=nombre, provincia=provincia)
            db.session.add(muni)
            db.session.flush()
        municipios_map[nombre] = muni

    recursos = {
        r.nombre: r
        for r in RecursoCatalogo.query.all()
    }
    if not recursos:
        print('  [!] No hay recursos en catálogo. Saltando seed_reportes_historico.')
        return

    ahora = ahora_ar()
    escenarios = [
        {
            'zona': '[HIST] Cuenca Arroyo El Gato - La Plata',
            'tipo': TipoDesastreEnum.hidrologico,
            'gravedad': NivelGravedadEnum.ALTO.value,
            'municipio': 'La Plata',
            'dias_atras': 120,
            'bonita_estado': 'finalizada',
            'es_conjunta': True,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Raciones de Alimento Seco', 1200, 800, 1200),
                ('Carpas Sanitarias de Campaña', 4, 2, 4),
            ],
            'actividades': [
                (ong_principal.id, '[HIST] Despliegue sanitario El Gato', EstadoActividadEnum.FINALIZADA, 118, 110, 'Cobertura total de evacuados sin novedades.'),
                (ong_colab.id, '[HIST] Distribución raciones El Gato', EstadoActividadEnum.FINALIZADA, 117, 111, 'Entregadas 1200 raciones en 3 centros.'),
            ],
        },
        {
            'zona': '[HIST] Temporal Costero - Bahía Blanca',
            'tipo': TipoDesastreEnum.meteorologico,
            'gravedad': NivelGravedadEnum.CRITICO.value,
            'municipio': 'Bahía Blanca',
            'dias_atras': 92,
            'bonita_estado': 'finalizada',
            'es_conjunta': True,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Paramédicos de Emergencia', 12, 8, 10),
                ('Ambulancia de Traslado 4x4', 3, 2, 3),
            ],
            'actividades': [
                (ong_principal.id, '[HIST] Atención prehospitalaria Bahía', EstadoActividadEnum.FINALIZADA, 90, 81, 'Se asistieron 140 vecinos en zona sur.'),
                (ong_extra.id, '[HIST] Traslados de urgencia Bahía', EstadoActividadEnum.FINALIZADA, 90, 83, 'Operativo cerrado con 3 unidades.'),
            ],
        },
        {
            'zona': '[HIST] Incendio Sierras Chicas - Córdoba',
            'tipo': TipoDesastreEnum.incendio_forestal,
            'gravedad': NivelGravedadEnum.CRITICO.value,
            'municipio': 'Córdoba Capital',
            'dias_atras': 64,
            'bonita_estado': 'finalizada',
            'es_conjunta': False,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Paramédicos de Emergencia', 10, 6, 8),
                ('Raciones de Alimento Seco', 900, 500, 900),
            ],
            'actividades': [
                (ong_colab.id, '[HIST] Soporte brigadistas Sierras Chicas', EstadoActividadEnum.FINALIZADA, 62, 53, 'Apoyo médico e hidratación completados.'),
            ],
        },
        {
            'zona': '[HIST] Brote Sanitario Ribera - Rosario',
            'tipo': TipoDesastreEnum.biologico,
            'gravedad': NivelGravedadEnum.MEDIO.value,
            'municipio': 'Rosario',
            'dias_atras': 35,
            'bonita_estado': 'finalizada',
            'es_conjunta': True,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Carpas Sanitarias de Campaña', 5, 3, 5),
                ('Paramédicos de Emergencia', 8, 5, 8),
            ],
            'actividades': [
                (ong_principal.id, '[HIST] Posta sanitaria Rosario', EstadoActividadEnum.FINALIZADA, 33, 25, 'Postas desmontadas tras control epidemiológico.'),
            ],
        },
        {
            'zona': '[HIST] Sismo Leve Precordillera - Córdoba',
            'tipo': TipoDesastreEnum.geologico,
            'gravedad': NivelGravedadEnum.BAJO.value,
            'municipio': 'Córdoba Capital',
            'dias_atras': 16,
            'bonita_estado': 'vinculada',
            'es_conjunta': False,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Raciones de Alimento Seco', 600, 300, 600),
                ('Ambulancia de Traslado 4x4', 2, 1, 2),
            ],
            'actividades': [
                (ong_extra.id, '[HIST] Relevamiento preventivo precordillera', EstadoActividadEnum.EN_EJECUCION, 14, None, None),
            ],
        },
        {
            'zona': '[HIST] Sudestada Canal Sur - La Plata',
            'tipo': TipoDesastreEnum.hidrologico,
            'gravedad': NivelGravedadEnum.ALTO.value,
            'municipio': 'La Plata',
            'dias_atras': 6,
            'bonita_estado': 'vinculada',
            'es_conjunta': True,
            'estado_oferta': EstadoOfertaEnum.ADJUDICADA,
            'detalles_lote': [
                ('Raciones de Alimento Seco', 1500, 1000, 1350),
                ('Carpas Sanitarias de Campaña', 4, 2, 3),
            ],
            'actividades': [
                (ong_principal.id, '[HIST] Asistencia evacuados Canal Sur', EstadoActividadEnum.EN_EJECUCION, 4, None, None),
                (ong_colab.id, '[HIST] Logística alimentaria Canal Sur', EstadoActividadEnum.FINALIZADA, 5, 2, 'Primera tanda entregada al 100%.'),
            ],
        },
    ]

    for esc in escenarios:
        if Emergencia.query.filter_by(zona_afectada=esc['zona']).first():
            continue

        fecha_reg = ahora - timedelta(days=esc['dias_atras'])
        emergencia = Emergencia(
            tipo_desastre=esc['tipo'],
            nivel_gravedad=esc['gravedad'],
            zona_afectada=esc['zona'],
            descripcion=f"Emergencia histórica de prueba ({esc['tipo'].value}).",
            responsable_id=operador.id,
            municipio_id=municipios_map[esc['municipio']].id,
            fecha_registro=fecha_reg,
            updated_at=fecha_reg,
            bonita_estado=esc['bonita_estado'],
        )
        db.session.add(emergencia)
        db.session.flush()

        lote = LoteNecesidades(
            emergencia_id=emergencia.id,
            fecha_inicio_ofertas=fecha_reg + timedelta(hours=4),
            fecha_cierre_ofertas=fecha_reg + timedelta(days=2),
            bonita_estado='sincronizado',
        )
        db.session.add(lote)
        db.session.flush()

        detalles_adjudicados = []
        for nombre_rec, cant_nec, cant_min, cant_adj in esc['detalles_lote']:
            rec = recursos.get(nombre_rec)
            if not rec:
                continue
            db.session.add(LoteDetalle(
                lote_id=lote.id,
                id_recurso=rec.id,
                cantidad_necesaria=cant_nec,
                cantidad_minima=cant_min,
            ))
            detalles_adjudicados.append((rec, cant_nec, cant_adj))

        fecha_oferta = fecha_reg + timedelta(days=1)
        oferta = Oferta(
            id_emergencia=emergencia.id,
            convocatoria_id=lote.id,
            creada_por_ong_id=ong_principal.id if esc['es_conjunta'] else ong_colab.id,
            fecha_creacion=fecha_oferta,
            estado=esc['estado_oferta'],
            version_actual=1,
            es_conjunta=esc['es_conjunta'],
            fecha_ultima_modificacion=fecha_oferta + timedelta(hours=12),
        )
        db.session.add(oferta)
        db.session.flush()

        version = VersionOferta(
            id_oferta=oferta.id,
            numero_version=1,
            fecha_version=fecha_oferta + timedelta(hours=12),
            usuario_modificacion=operador.id,
            observaciones='Adjudicación histórica seed',
            estado_versiones='Adjudicada',
        )
        db.session.add(version)
        db.session.flush()

        participantes = [ong_principal.id, ong_colab.id] if esc['es_conjunta'] else [ong_colab.id]
        for idx, (rec, cant_nec, cant_adj) in enumerate(detalles_adjudicados):
            ong_det = participantes[idx % len(participantes)]
            db.session.add(DetalleVersionOferta(
                id_version=version.id,
                id_ong=ong_det,
                id_recurso=rec.id,
                cantidad=cant_nec,
                cantidad_adjudicada=cant_adj,
            ))

        if esc['es_conjunta']:
            for pid in participantes:
                db.session.add(OfertaParticipante(
                    oferta_id=oferta.id,
                    ong_id=pid,
                    estado='Aceptada',
                ))

        for ong_act_id, titulo, estado_act, d_ini, d_fin, informe in esc['actividades']:
            db.session.add(ActividadONG(
                ong_id=ong_act_id,
                titulo=titulo,
                descripcion=f'Actividad operativa vinculada a {esc["zona"]}',
                lote_referencia=lote.id,
                estado=estado_act,
                fecha_inicio=ahora - timedelta(days=d_ini),
                fecha_finalizacion=(ahora - timedelta(days=d_fin)) if d_fin is not None else None,
                informe_cierre=informe,
                created_at=ahora - timedelta(days=d_ini),
            ))

    db.session.commit()
    print('  [+] Histórico para reportes cargado correctamente.')
