#!/bin/sh
set -e

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
exec poetry run flask run --host=0.0.0.0 --port=5000 --reload --debug