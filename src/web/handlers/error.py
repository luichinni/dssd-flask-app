from dataclasses import dataclass
from flask import render_template

@dataclass
class Error:
    code: int
    message: str
    description: str


def bad_request_error(e):
    error = Error(
        code=400,
        message="Petición incorrecta",
        description="Los datos enviados en la solicitud no son válidos o están incompletos."
    )
    return render_template("error.html", error=error), 400


def unauthorized_error(e):
    error = Error(
        code=401,
        message="Alto ahí!",
        description="Debes iniciar sesión para acceder a este recurso."
    )
    return render_template("error.html", error=error), 401


def forbidden_error(e):
    error = Error(
        code=403,
        message="Acceso denegado",
        description="No tienes los permisos necesarios (rol requerido) para ver esta página."
    )
    return render_template("error.html", error=error), 403


def not_found_error(e):
    error = Error(
        code=404,
        message="Ups! No pudimos encontrar lo que estás buscando",
        description="La URL que estás buscando no se encuentra en nuestro servidor."
    )
    return render_template("error.html", error=error), 404


def internal_server_error(e):
    error = Error(
        code=500,
        message="Error interno del servidor",
        description="Ocurrió un problema inesperado en nuestro sistema. Ya estamos trabajando para solucionarlo."
    )
    return render_template("error.html", error=error), 500


def register_error_handlers(app):
    """Registra los manejadores de error en la aplicación de Flask."""
    app.register_error_handler(400, bad_request_error)
    app.register_error_handler(401, unauthorized_error)
    app.register_error_handler(403, forbidden_error)
    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_server_error)