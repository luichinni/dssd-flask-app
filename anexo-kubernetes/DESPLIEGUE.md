# Anexo Kubernetes de RescueSync

El servicio asigna prioridad antes del alta de una emergencia. El puntaje base
para gravedad baja, media, alta y crítica es 1, 3, 5 y 8, respectivamente.
La tabla de prueba suma 1 para Los Hornos y Tolosa, 2 para Arroyo El Gato y
Barrio Ribereño, y 0 para otras zonas. La comparación ignora tildes, mayúsculas
y espacios repetidos. Se aplica la misma regla a todos los municipios.

## Publicación y despliegue

Desde la raíz de `dssd-flask-app`, con Docker y `kubectl` apuntando a un clúster
con la API de métricas disponible (`kubectl top nodes`), ejecutá en PowerShell
estos comandos. La imagen pública está en el repositorio Docker Hub
`emmanuelallende/rescuesync-prioridades`.

```powershell
$imagen = 'docker.io/emmanuelallende/rescuesync-prioridades:1.0.0'
docker login
docker build -t $imagen ./anexo-kubernetes/servicio
docker push $imagen

kubectl set image -f ./anexo-kubernetes/k8s/deployment.yaml "prioridades=$imagen" --local -o yaml | kubectl apply -f -
kubectl apply -f ./anexo-kubernetes/k8s/service.yaml -f ./anexo-kubernetes/k8s/hpa.yaml
kubectl rollout status deployment/prioridades
kubectl get hpa prioridades
```

## Prueba desde Flask

Para una demo local, dejá abierto este comando en una terminal. La dirección
permite que Flask, dentro de Docker Desktop, llegue al puerto reenviado del host.

```powershell
kubectl port-forward --address 0.0.0.0 service/prioridades 18000:8000
```

En el `.env` de Flask, configurá `PRIORIDADES_URL=http://host.docker.internal:18000`
y ejecutá `docker compose up -d --build web`. El arranque ejecuta la migración.
Si Flask corre en el clúster, usá `http://prioridades:8000` desde el mismo namespace.
Para probar solo con Compose, dejá vacía la variable.

Registrá una emergencia de gravedad alta en Los Hornos. Debería quedar con
**prioridad 6/10**. Si el servicio no responde, el formulario conserva los
datos y el alta queda pendiente de reintento.

## Prueba de escalado

En una terminal, observá `kubectl get hpa prioridades -w`. En otra, generá
peticiones concurrentes desde el clúster con un pod temporal:

```powershell
kubectl run carga-prioridades --image=curlimages/curl:8.13.0 --restart=Never --rm -it --command -- sh
```

```sh
for i in 1 2 3 4 5 6 7 8; do
  while true; do
    curl -s -o /dev/null -H 'Content-Type: application/json' \
      -d '{"nivel_gravedad":3,"zona_afectada":"Los Hornos"}' http://prioridades:8000/prioridades
  done &
done
wait
```

Comprobá que el HPA aumente las réplicas sin superar 5. Terminá la carga con
Ctrl+C y observá que, tras el período de estabilización, vuelva a 1.
