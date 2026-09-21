# Tutorial
```bash
docker compose up -d
```
Levanta los contenedores de postgreSQL y flask en modo headless

Para tener autocompletado y que ande bien el linter de python, con la extensión de VSCode de DevContainers (seguro ya viene por defecto) y una vez iniciado el contenedor de flask:
1. Apretan Ctrl+Shift+P y buscan la opción "Attach to running container..."
2. Seleccionan el contenedor de flask y esperan a que cargue
3. Luego de que abra seguro deben darle a "Open Folder" y buscan la carpeta /app, ese es el proyecto.