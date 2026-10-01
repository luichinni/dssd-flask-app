#!/bin/sh
set -e

on_exit() {
  STATUS=$?
  if [ $STATUS -ne 0 ]; then
    echo "❌ Ocurrió un error en la ejecución (código $STATUS)."
    echo "⚠️ El contenedor permanecerá encendido para depuración."
    echo "💡 Puedes acceder con: docker exec -it <nombre_del_contenedor> sh"
    tail -f /dev/null
  fi
}

trap 'on_exit' EXIT

echo "⏳ Esperando a que PostgreSQL esté disponible..."
while ! nc -z db 5432; do
  sleep 0.5
done
echo "✅ PostgreSQL conectado."

echo "🚀 Ejecutando migraciones..."
poetry run flask db upgrade

echo "🌱 Inicializando datos de prueba (solo agrega los faltantes)..."
poetry run flask seed-db

echo "🔥 Iniciando Flask..."
trap - EXIT
exec poetry run flask run --host=0.0.0.0 --port=5000 --reload --debug