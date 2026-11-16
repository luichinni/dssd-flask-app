# Tutorial
```bash
docker compose up -d
```
Levanta los contenedores de postgreSQL y flask en modo headless

Para tener autocompletado y que ande bien el linter de python, con la extensión de VSCode de `DevContainers` (seguro ya viene por defecto) y una vez iniciado el contenedor de flask:
1. Apretan `Ctrl+Shift+P` y buscan la opción `Attach to running container...`
2. Seleccionan el contenedor de `flask` y esperan a que cargue
3. Luego de que abra seguro deben darle a `Open Folder` y buscan la carpeta `/app`, ese es el proyecto.

⚠️ Leer el archivo [Alembic.md](migrations/Alembic.md) para saber como usar las migraciones y el apartado [Comandos de base de datos](#comandos-de-base-de-datos) para saber como acceder a la consola del contenedor.

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
        - Tiene su propio archivo donde se especifica como usarlo: [Alembic.md](migrations/Alembic.md).
- `entrypoint.sh`: espera a PostgreSQL, aplica migraciones, carga seeds faltantes y arranca Flask.

## Comandos de base de datos

- `flask db upgrade`: aplica migraciones pendientes sin borrar datos.
- `flask seed-db`: crea los usuarios iniciales que todavía no existen.
- `flask reset-db`: elimina y recrea todas las tablas; usar sólo cuando se quiera reiniciar la base de datos de forma explícita.

Todos estos comandos pueden ser lanzados desde dentro del contendor desde la opción Exec en Docker Desktop que abre una consola, sino, por medio de la consola con el comando:
```bash
docker exec -it <nombre_o_id_del_contenedor> /bin/sh
```
## Inicio de procesos en Bonita

El alta de emergencias consulta el servicio del [anexo Kubernetes](anexo-kubernetes/DESPLIEGUE.md)
antes de iniciar Bonita. Docker Compose levanta una instancia local para desarrollo.

Copiar la configuración de Bonita de `.env.example` a `.env`. El ejemplo usa
`123` para las cuentas de prueba del runtime local. Si cambiás una contraseña
en Bonita, actualizá la variable correspondiente en tu `.env`.

| Actor | Variables de entorno |
| --- | --- |
| Municipio (inicia el proceso) | `BONITA_USERNAME`, `BONITA_PASSWORD` |
| Centro Coordinador | `BONITA_CCR_USERNAME`, `BONITA_CCR_PASSWORD` |
| ONG | `BONITA_ONG_USERNAME`, `BONITA_ONG_PASSWORD` |
| Sistema Nacional | `BONITA_SISTEMA_NACIONAL_USERNAME`, `BONITA_SISTEMA_NACIONAL_PASSWORD` |

La app busca por API la definición habilitada
BestRescueSyncEver versión 1.0 al iniciar e inicia el caso usando su ID actual.
BONITA_URL debe incluir /bonita y el puerto real. Si Flask se ejecuta directamente en Windows,
usar localhost; desde el contenedor usar host.docker.internal.

El servicio se usa dentro de un contexto Flask (por ejemplo, un controlador):

```python
from src.core.services.bonita import BonitaError, iniciar_proceso

# Ejemplo solamente: reemplazar las entradas por el contrato real del BPMN.
case_id = iniciar_proceso({"emergenciaId": emergencia.id})
# Sin contrato: iniciar_proceso()
# Otro proceso: iniciar_proceso(datos_contrato, proceso_id=123)
```

El método inicia una sesión, conserva cookies, envía el token CSRF y devuelve
el caseId como entero. Las entradas deben coincidir con el contrato de
instanciación; el BPMN debe usarlas para inicializar sus variables.
Los fallos generan BonitaError sin mostrar credenciales ni cuerpos de respuesta.
Ante un HTTP 404 por una definición obsoleta, la app busca la definición
habilitada actual y reintenta una sola vez si el ID cambió. No reintenta ante
timeout, errores 5xx ni respuestas sin caseId: verificar los casos en Bonita
antes de repetir para evitar duplicados.

El alta de emergencias inicia automáticamente el proceso con el contrato
id_emergencia_init y guarda bonita_case_id. El BPMN avanza según sus transiciones
hasta la tarea humana Registrar emergencia; la app no completa esa tarea.
Si no se confirma el caso, conserva la emergencia con estado no_confirmado y
muestra un aviso. Solo se repite el inicio cuando Bonita rechaza definitivamente
con HTTP 404 una definición obsoleta; respuestas ambiguas no se repiten.
Las emergencias preexistentes no generan casos retroactivamente.
Aplicar flask db upgrade antes de usar este flujo.

### Publicación de lotes y tareas BPM

Al publicar un lote, la app completa en el caso asociado:
Registrar emergencia (si sigue pendiente), Crear lotes de necesidades y
Publicar convocatoria. Envía id_emergencia_input a la primera; las otras dos
usan contratos vacíos. Las tareas se asignan al usuario configurado de Bonita;
si están asignadas a otra persona, se informa el fallo sin reasignarlas.
Se consultan tareas por caseId y se espera de forma acotada a que la próxima
esté lista. Las tareas ya completadas se omiten y no se repiten POST ante fallos.
El lote conserva bonita_estado=sincronizado o no_confirmado para investigar
fallos parciales. La creación de lotes adicionales no repite tareas ya cerradas.
Esto no configura el temporizador ni implementa la recepción de ofertas.
