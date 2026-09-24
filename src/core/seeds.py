from datetime import datetime, timedelta
from src.core.models import Usuario, InventarioONG, Notificacion, ActividadONG
from src.core.enums import RolEnum, TipoRecursoEnum, TipoNotificacionEnum, EstadoActividadEnum
from src.core.database import db

def seed(app):
    """Función para inicializar la base de datos y cargar datos iniciales (seeding)."""
    with app.app_context():
        print("🌱 Iniciando carga de datos iniciales (Seeding)...")
        seed_users()
        seed_ong_data()
        print("🌱 Finalización de la carga de datos iniciales (Seeding)!")

def seed_users():
    print('🌱 Seedeando usuarios por cada rol...')

    usuarios_base = [
        {
            'nombre': 'Operador Municipal',
            'email': 'operador@municipio.gob.ar',
            'password': 'Operador2026!',
            'rol': RolEnum.OPERADOR_MUNICIPAL,
            'datos_adicionales': {'jurisdiccion': 'Zona Norte', 'turno': 'Mañana'},
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
            'datos_adicionales': {'organizacion': 'Red de Apoyo Comunitario', 'personeria': '12345/2020'},
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
            print(f"  [-] El usuario ({datos['email']}) ya existe.")

    db.session.commit()

def seed_ong_data():
    print('🌱 Seedeando datos de ONG (inventario, notificaciones, actividades)...')
    ong = Usuario.query.filter_by(email='ong@ayuda.org').first()
    if not ong:
        print('  [!] Usuario ONG no encontrado. Saltando seeding de ONG.')
        return

    # 1. Inventario
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
        existente = InventarioONG.query.filter_by(ong_id=ong.id, nombre=r_data['nombre']).first()
        if not existente:
            recurso = InventarioONG(
                ong_id=ong.id,
                nombre=r_data['nombre'],
                tipo_recurso=r_data['tipo_recurso'],
                unidad_medida=r_data['unidad_medida'],
                cantidad_total=r_data['cantidad_total'],
                cantidad_disponible=r_data['cantidad_disponible'],
                descripcion=r_data['descripcion'],
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
                created_at=datetime.utcnow() - timedelta(days=n_data['dias_atras']),
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
            'fecha_inicio': datetime.utcnow() - timedelta(hours=18),
            'fecha_finalizacion': None,
            'informe_cierre': None,
            'recursos_utilizados': '5 Paramédicos, 1 Ambulancia 4x4, 1 Carpa Sanitaria',
        },
        {
            'titulo': 'Distribución de Alimentos y Abrigo - Temporal La Plata',
            'descripcion': 'Reparto de raciones calóricas y frazadas en centros comunitarios.',
            'lote_referencia': 'LOTE-098-ALIM',
            'estado': EstadoActividadEnum.FINALIZADA,
            'fecha_inicio': datetime.utcnow() - timedelta(days=5),
            'fecha_finalizacion': datetime.utcnow() - timedelta(days=3),
            'informe_cierre': 'Se distribuyeron 1200 raciones en 3 centros comunitarios designados. Cobertura al 100% de la población censada sin incidentes de gravedad.',
            'recursos_utilizados': '1200 Raciones de Alimento Seco, 4 Voluntarios',
        },
    ]

    for a_data in actividades_base:
        existente = ActividadONG.query.filter_by(ong_id=ong.id, titulo=a_data['titulo']).first()
        if not existente:
            act = ActividadONG(
                ong_id=ong.id,
                titulo=a_data['titulo'],
                descripcion=a_data['descripcion'],
                lote_referencia=a_data['lote_referencia'],
                estado=a_data['estado'],
                fecha_inicio=a_data['fecha_inicio'],
                fecha_finalizacion=a_data['fecha_finalizacion'],
                informe_cierre=a_data['informe_cierre'],
                recursos_utilizados=a_data['recursos_utilizados'],
            )
            db.session.add(act)
            print(f"  [+] Actividad creada: {a_data['titulo']} ({a_data['estado'].value})")

    db.session.commit()