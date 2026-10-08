import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from src.core import database
from src.core.config import config
from src.core.bcrypt_and_session import bcrypt
from src.web.handlers.error import register_error_handlers
from src.core import models
from src.core.seeds import seed
from src.web.auth_manager import auth_manager
from src.web.controllers.auth import auth_bp
from src.web.controllers.users import users_bp
from src.web.controllers.ong import ong_bp
from src.web.controllers.emergencies import emergencies_bp
from src.web.controllers.ccr import ccr_bp
from flask_login import current_user

load_dotenv()

migrate = Migrate()

def create_app(env="development", static_folder="./static"):
    app = Flask(__name__, static_folder=static_folder)

    app.config.from_object(config[env])

    # Bonita puede arrancar después de Flask; la integración vuelve a resolver
    # el ID al crear el primer caso si esta consulta inicial no está disponible.
    try:
        from src.core.services.bonita import BonitaError, resolver_process_definition_id
        with app.app_context():
            process_id = resolver_process_definition_id()
        app.logger.info("Definición Bonita habilitada detectada (ID %s).", process_id)
    except BonitaError as error:
        app.config.pop("BONITA_PROCESS_ID", None)
        app.logger.warning("No se pudo resolver la definición Bonita al iniciar; se intentará al crear un caso: %s", error)

    database.init_app(app)
    migrate.init_app(app, database.db)

    bcrypt.init_app(app)

    auth_manager.init_app(app)

    register_error_handlers(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(ong_bp)
    app.register_blueprint(emergencies_bp)
    app.register_blueprint(ccr_bp)
    @app.context_processor
    def inject_global_data():
        if current_user.is_authenticated and hasattr(current_user, 'rol'):
            from src.core.enums import RolEnum
            from src.core.services.notificaciones import contar_no_leidas
            rol_val = current_user.rol.value if hasattr(current_user.rol, 'value') else current_user.rol
            if rol_val == RolEnum.ONG.value:
                return {'notificaciones_pendientes_count': contar_no_leidas(current_user.id)}
        return {'notificaciones_pendientes_count': 0}

    @app.cli.command(name="reset-db")
    def reset_db():
        database.reset()
        seed(app)

    @app.cli.command(name="seed-db")
    def seed_db():
        """Carga los datos iniciales sin eliminar los existentes."""
        seed(app)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)