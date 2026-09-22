from os import environ
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv(dotenv_path='.env')

class Config(object):
    TESTING = False
    SECRET_KEY= environ.get('SECRET_KEY_PASS','my_precious') # "my_precious"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    # Asegurar que las cookies funcionen en desarrollo HTTP (sin SSL)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Setear en True solo en producción con HTTPS

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = environ.get("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 60,
        "pool_pre_ping": True,
    }

class DevelopmentConfig(Config):
    DB_USER = environ.get('DB_USER')
    DB_PASSWORD = environ.get('DB_PASSWORD')
    DB_HOST = environ.get('DB_HOST')
    DB_PORT = environ.get('DB_PORT')
    DB_NAME = environ.get('DB_NAME')
    SQLALCHEMY_DATABASE_URI = environ.get("DATABASE_URL")

class TestingConfig(Config):
    TESTING = True

config = {
    "development" : DevelopmentConfig,
    "production" : ProductionConfig,
    "testing" : TestingConfig
}