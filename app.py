import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    database_url = os.getenv("DATABASE_URL")
    
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    db.init_app(app)
    migrate.init_app(app, db)

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