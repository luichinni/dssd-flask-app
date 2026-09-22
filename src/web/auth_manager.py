from flask import Flask, redirect, url_for, flash, request
from flask_login import LoginManager
from src.core.models import Usuario
from src.core.database import db

class AuthManager:
    """Clase encargada de encapsular la configuración e inicialización de Flask-Login."""

    def __init__(self, app: Flask = None):
        self.login_manager = LoginManager()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        self.login_manager.init_app(app)

        # Endpoint al que redirige si el usuario no está autenticado
        self.login_manager.login_view = 'auth.login'
        self.login_manager.login_message = 'Por favor, iniciá sesión para acceder a esta página.'
        self.login_manager.login_message_category = 'info'

        self._register_callbacks()

    def _register_callbacks(self) -> None:
        @self.login_manager.user_loader
        def load_user(user_id: str):
            # Usar db.session.get para mayor compatibilidad con SQLAlchemy 2.0
            return db.session.get(Usuario, int(user_id))

        @self.login_manager.unauthorized_handler
        def handle_unauthorized():
            flash(self.login_manager.login_message, self.login_manager.login_message_category)
            return redirect(url_for(self.login_manager.login_view, next=request.endpoint))


auth_manager = AuthManager()