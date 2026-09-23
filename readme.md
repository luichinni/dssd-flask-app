# Tutorial
```bash
docker compose up -d
```
Levanta los contenedores de postgreSQL y flask en modo headless

Para tener autocompletado y que ande bien el linter de python, con la extensión de VSCode de DevContainers (seguro ya viene por defecto) y una vez iniciado el contenedor de flask:
1. Apretan Ctrl+Shift+P y buscan la opción "Attach to running container..."
2. Seleccionan el contenedor de flask y esperan a que cargue
3. Luego de que abra seguro deben darle a "Open Folder" y buscan la carpeta /app, ese es el proyecto.

## Estructura del proyecto

- `app.py`: crea y configura la aplicación Flask, registra extensiones, blueprints y comandos CLI.
- `src/core/`: lógica central independiente de las rutas web.
	- `config.py`: configuración por entorno.
	- `database.py`: instancia y ciclo de vida de SQLAlchemy.
	- `models/`: modelos persistidos en la base de datos.
	- `services/`: operaciones de negocio y acceso a datos reutilizables por los controllers.
	- `seeds.py`: datos iniciales idempotentes para desarrollo.
	- `enums/`: valores enumerados compartidos por modelos y lógica de negocio.
- `src/web/`: capa HTTP de la aplicación.
	- `controllers/`: blueprints y funciones que reciben requests y devuelven responses.
	- `decorators/`: decoradores para autenticación y autorización.
	- `handlers/`: manejadores de errores HTTP. 
	- `auth_manager.py`: configuración de Flask-Login.
- `templates/`: vistas HTML renderizadas por Flask/Jinja.
- `static/`: archivos estáticos como CSS, JavaScript e imágenes.
- `migrations/`: versiones de esquema generadas por Flask-Migrate/Alembic.
        - Tiene su propio archivo donde se especifica como usarlo: `Alembic.md`
- `entrypoint.sh`: espera a PostgreSQL, aplica migraciones, carga seeds faltantes y arranca Flask.

## Comandos de base de datos

- `flask db upgrade`: aplica migraciones pendientes sin borrar datos.
- `flask seed-db`: crea los usuarios iniciales que todavía no existen.
- `flask reset-db`: elimina y recrea todas las tablas; usar sólo cuando se quiera reiniciar la base de datos de forma explícita.