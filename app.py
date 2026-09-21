import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from src.core import database
from src.core.config import config
from src.core.bcrypt_and_session import bcrypt, session

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app(env="development", static_folder="./static"):
    app = Flask(__name__, static_folder=static_folder)

    app.config.from_object(config[env])

    database_url = os.getenv("DATABASE_URL")

    database.init_app(app)
    migrate.init_app(app, db)

    bcrypt.init_app(app)
    session.init_app(app)

    """
    Para despues
    app.register_error_handler(404, error.not_found_error)
    app.register_error_handler(401, error.unauthorized)
    """

    @app.cli.command(name="reset-db")
    def reset_db():
        database.reset()
        database.init()

    @app.route("/")
    def index():
        return jsonify({
            "status": "online",
            "mensaje": "APP Flask conectada usando .env"
        })

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)