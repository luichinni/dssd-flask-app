FROM python:3.11-slim

# Evitar archivos .pyc y forzar logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# Instalar dependencias del sistema requeridas (PostgreSQL, utilidades de red y compilación)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copiar manifiesto de dependencias e instalarlas
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root

# Copiar el resto del código
COPY . .

# Exponer el puerto predeterminado de Flask
EXPOSE 5000

# Comando para ejecutar Flask con auto-reload activo
CMD ["poetry", "run", "flask", "run", "--host=0.0.0.0", "--port=5000", "--reload", "--debug"]