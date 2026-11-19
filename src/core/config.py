from os import environ
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv(dotenv_path='.env')


def _resolver_bonita_url(raw_url: str, raw_port: str) -> str:
    """Resuelve BONITA_URL aplicando el puerto configurado en BONITA_PORT."""
    url = str(raw_url or "").strip()
    port = str(raw_port or "").strip()
    if not url:
        return ""
    if port:
        url = url.replace("${BONITA_PORT}", port).replace("$BONITA_PORT", port)
        parsed = urlsplit(url)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
            auth = ""
            if parsed.username:
                auth = parsed.username
                if parsed.password:
                    auth += f":{parsed.password}"
                auth += "@"
            return urlunsplit((parsed.scheme, f"{auth}{host}:{port}", parsed.path, parsed.query, parsed.fragment))
    return url


class Config(object):
    BONITA_PORT = environ.get("BONITA_PORT", "18080").strip() or "18080"
    BONITA_URL = _resolver_bonita_url(environ.get("BONITA_URL", ""), environ.get("BONITA_PORT", ""))
    BONITA_USERNAME = environ.get("BONITA_USERNAME", "")
    BONITA_PASSWORD = environ.get("BONITA_PASSWORD", "")
    BONITA_CCR_USERNAME = environ.get("BONITA_CCR_USERNAME", "ccr.coordinador")
    BONITA_CCR_PASSWORD = environ.get("BONITA_CCR_PASSWORD", "")
    BONITA_ONG_USERNAME = environ.get("BONITA_ONG_USERNAME", "ong.representante")
    BONITA_ONG_PASSWORD = environ.get("BONITA_ONG_PASSWORD", "")
    BONITA_SISTEMA_NACIONAL_USERNAME = environ.get("BONITA_SISTEMA_NACIONAL_USERNAME", "sistema.nacional")
    BONITA_SISTEMA_NACIONAL_PASSWORD = environ.get("BONITA_SISTEMA_NACIONAL_PASSWORD", "")
    BONITA_TIMEOUT = environ.get("BONITA_TIMEOUT", "15")
    BONITA_CALLBACK_API_KEY = environ.get("BONITA_CALLBACK_API_KEY", "")
    BONITA_ADMIN_USERNAME = environ.get("BONITA_ADMIN_USERNAME", "walter.bates")
    BONITA_ADMIN_PASSWORD = environ.get("BONITA_ADMIN_PASSWORD", "Grupo11!")
    BONITA_RETRY_ENABLED = environ.get("BONITA_RETRY_ENABLED", "true").lower() in ("1", "true", "yes")
    BONITA_RETRY_INTERVAL = int(environ.get("BONITA_RETRY_INTERVAL", "30"))
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
