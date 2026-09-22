from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    """Inicializar la base de datos."""
    db.init_app(app)
    return app

def reset():
    """Resetea la base de datos."""
    print("Eliminando la base de datos...")
    db.drop_all()
    print("Creando la base de datos...")
    db.create_all()
    print("¡Finalización del reset de la base de datos!")