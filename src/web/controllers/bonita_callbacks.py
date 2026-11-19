from flask import Blueprint, jsonify, request, abort, current_app
from src.core.services.lotes import todos_los_lotes_cubiertos
from src.core.services.ofertas import registrar_ofertas_validadas

bonita_callbacks_bp = Blueprint('bonita_callbacks', __name__, url_prefix='/api')


@bonita_callbacks_bp.route('/emergencias/<int:id_emergencia>/evaluar-cobertura', methods=['GET'])
def evaluar_cobertura(id_emergencia):
    if request.headers.get('secret-key-api') != current_app.config.get('BONITA_CALLBACK_API_KEY'):
        abort(401)
    try:
        cubierto = todos_los_lotes_cubiertos(id_emergencia)
    except ValueError:
        abort(404)
    return jsonify({"todosLotesCubiertos": cubierto})


@bonita_callbacks_bp.route('/emergencias/<int:id_emergencia>/ofertas-validadas', methods=['POST'])
def recibir_ofertas_validadas(id_emergencia):
    if request.headers.get('secret-key-api') != current_app.config.get('BONITA_CALLBACK_API_KEY'):
        abort(401)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    try:
        registrar_ofertas_validadas(id_emergencia, payload)
    except ValueError:
        abort(404)
    return jsonify({"ok": True})