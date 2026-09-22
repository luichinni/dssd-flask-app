import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from src.core import database
from src.core.config import config
from src.core.bcrypt_and_session import bcrypt
from src.web.handlers.error import register_error_handlers
from src.web.controllers.auth import auth_bp
from src.core.seeds import seed
from src.web.auth_manager import auth_manager

load_dotenv()

migrate = Migrate()

def create_app(env="development", static_folder="./static"):
    app = Flask(__name__, static_folder=static_folder)

    app.config.from_object(config[env])

    database.init_app(app)
    migrate.init_app(app, database.db)

    bcrypt.init_app(app)

    auth_manager.init_app(app)

    register_error_handlers(app)

    app.register_blueprint(auth_bp)

    @app.cli.command(name="reset-db")
    def reset_db():
        database.reset()
        seed(app)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)