from datetime import datetime, timedelta, timezone
from src.core.models import Usuario, ONG, InventarioONG, RecursoCatalogo, Notificacion, ActividadONG, Emergencia, Municipio, Oferta, VersionOferta, DetalleVersionOferta
from src.core.enums import RolEnum, TipoRecursoEnum, TipoNotificacionEnum, EstadoActividadEnum, TipoDesastreEnum, EstadoOfertaEnum
from src.core.database import db


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
        seed_ofertas_data()
        print("🌱 Finalización de la carga de datos iniciales (Seeding)!")

def seed_users():
    print('🌱 Seedeando usuarios por cada rol...')

    ong = ONG.query.filter_by(nombre='Red de Apoyo Comunitario').first()
    if not ong:
        ong = ONG(nombre='Red de Apoyo Comunitario', descripcion='12345/2020')
        db.session.add(ong)

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
                created_at=datetime.now(timezone.utc) - timedelta(days=n_data['dias_atras']),
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
            'fecha_inicio': datetime.now(timezone.utc) - timedelta(hours=18),
            'fecha_finalizacion': None,
            'informe_cierre': None,
            'recursos_utilizados': '5 Paramédicos, 1 Ambulancia 4x4, 1 Carpa Sanitaria',
        },
        {
            'titulo': 'Distribución de Alimentos y Abrigo - Temporal La Plata',
            'descripcion': 'Reparto de raciones calóricas y frazadas en centros comunitarios.',
            'lote_referencia': 'LOTE-098-ALIM',
            'estado': EstadoActividadEnum.FINALIZADA,
            'fecha_inicio': datetime.now(timezone.utc) - timedelta(days=5),
            'fecha_finalizacion': datetime.now(timezone.utc) - timedelta(days=3),
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
    if not ong_usuario:
        print('  [!] Usuario ONG no encontrado. Saltando seeding de Ofertas.')
        return

    ong_id = (ong_usuario.datos_adicionales or {}).get('ong_id')
    ong_profile = db.session.get(ONG, int(ong_id)) if ong_id is not None else None
    if not ong_profile:
        print('  [!] Perfil de ONG no encontrado. Saltando seeding de Ofertas.')
        return

    recurso_paramedicos = RecursoCatalogo.query.filter_by(nombre='Paramédicos de Emergencia').first()
    recurso_alimento = RecursoCatalogo.query.filter_by(nombre='Raciones de Alimento Seco').first()
    if not recurso_paramedicos or not recurso_alimento:
        print('  [!] Recursos base no encontrados. Saltando seeding de Ofertas.')
        return

    emergencia_terremoto = Emergencia.query.filter_by(zona_afectada='Barrio Ribereño, Quilmes').first()
    emergencia_tormenta = Emergencia.query.filter_by(zona_afectada='Zona Forestal, La Plata').first()
    if not emergencia_terremoto or not emergencia_tormenta:
        print('  [!] Emergencias base no encontradas. Saltando seeding de Ofertas.')
        return

    ofertas_base = [
        {
            'emergencia': emergencia_terremoto,
            'estado': EstadoOfertaEnum.ACEPTADA,
            'es_conjunta': False,
            'recurso': recurso_paramedicos,
            'cantidad': 5,
            'observaciones': 'Disponemos de 5 paramédicos certificados listos para despliegue inmediato.',
        },
        {
            'emergencia': emergencia_terremoto,
            'estado': EstadoOfertaEnum.PENDIENTE,
            'es_conjunta': False,
            'recurso': recurso_alimento,
            'cantidad': 300,
            'observaciones': 'Oferta de raciones aún en revisión por el Sistema Nacional.',
        },
        {
            'emergencia': emergencia_tormenta,
            'estado': EstadoOfertaEnum.ACEPTADA,
            'es_conjunta': True,
            'recurso': recurso_alimento,
            'cantidad': 800,
            'observaciones': 'Oferta conjunta con otra ONG de la red para cubrir la zona afectada.',
        },
    ]

    for o_data in ofertas_base:
        existente = Oferta.query.filter_by(
            id_emergencia=o_data['emergencia'].id,
            estado=o_data['estado'].value,
        ).first()
        if existente:
            continue

        oferta = Oferta(
            id_emergencia=o_data['emergencia'].id,
            estado=o_data['estado'].value,
            version_actual=1,
            es_conjunta=o_data['es_conjunta'],
        )
        db.session.add(oferta)
        db.session.flush()  # para obtener oferta.id antes del commit

        version = VersionOferta(
            id_oferta=oferta.id,
            numero_version=1,
            usuario_modificacion=ong_usuario.id,
            observaciones=o_data['observaciones'],
            estado_versiones=o_data['estado'].value,
        )
        db.session.add(version)
        db.session.flush()  # para obtener version.id

        detalle = DetalleVersionOferta(
            id_version=version.id,
            id_ong=ong_profile.id,
            id_recurso=o_data['recurso'].id,
            cantidad=o_data['cantidad'],
            cantidad_adjudicada=0,
        )
        db.session.add(detalle)

        print(f"  [+] Oferta creada para {o_data['emergencia'].zona_afectada} - estado {o_data['estado'].value}")

    db.session.commit()