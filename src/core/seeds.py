from src.core.models import Usuario
from src.core.enums import RolEnum
from src.core.database import db

def seed(app):
    """Función para inicializar la base de datos y cargar datos iniciales (seeding)."""
    with app.app_context():
        print("🌱 Iniciando carga de datos iniciales (Seeding)...")
        seed_users()
        print("🌱 Finalización de la carga de datos iniciales (Seeding)!")

def seed_users():
    print('🌱 Seedeando usuarios por cada rol...')

    # Lista de usuarios iniciales de prueba por rol
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

    # Guardar cambios en PostgreSQL
    db.session.commit()