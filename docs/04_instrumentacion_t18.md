# T18 — Instrumentación preliminar de SAD distribuido

## Alcance

Se instrumenta el **maestro** sin cambiar el algoritmo SAD, la partición con halos, la estructura de las solicitudes ZeroMQ ni el trabajador existente. Se mantienen las claves de estadísticas utilizadas en T15 para evitar romper sus pruebas.

## Métricas de una ejecución

| Clave | Interpretación |
|---|---|
| `partition_seconds` | División de franjas en el maestro |
| `serialize_seconds` | Preparación de los tres frames de la solicitud (metadatos + dos buffers) |
| `socket_setup_seconds` | Creación/configuración de contexto y socket REQ |
| `connect_call_seconds` | Duración de la llamada `connect()`; **no implica conexión TCP completada** |
| `send_call_seconds` | Duración de `send_multipart()`; **no mide transmisión hasta la laptop** |
| `local_compute_seconds` | Tiempo SAD sobre la franja local |
| `receive_wait_seconds` | Tiempo bloqueado en `recv_multipart()` después del cómputo local; incluye espera remota y transporte |
| `remote_compute_seconds` | Tiempo SAD comunicado por el trabajador; excluye su decodificación y serialización |
| `response_decode_seconds` | Decodificación y validación de resultado remoto en el maestro |
| `merge_seconds` | Ensamblado de ambas franjas y máscaras |
| `total_seconds` | Tiempo interno del maestro desde el inicio de `run_master` hasta terminar el ensamblado; **no incluye el cierre de socket/contexto** |
| `request_payload_bytes`, `response_payload_bytes` | Tamaño de frames a nivel de aplicación; **excluye overhead ZeroMQ/TCP/IP** |
| `wall_seconds` | Tiempo externo del benchmark; incluye llamada completa a `run_master` y liberación de recursos |

## Precauciones metodológicas

- Los cronómetros de PC y laptop no comparten un origen temporal: no restar marcas absolutas de relojes distintos para deducir latencia en un sentido.
- `receive_wait_seconds` se solapa con `remote_compute_seconds`. **No sumar todos los tiempos de la tabla.**
- No concluir que `wall_seconds - remote_compute_seconds` representa el tiempo de red.
- El cálculo distribuido usa una partición 50/50 y máquinas heterogéneas; la laptop puede ser el cuello de botella.
- El `ProcessPoolExecutor` local se crea en cada llamada: su costo está incluido en la medición paralela.
- Estas pruebas con matrices aleatorias son exploratorias; las conclusiones requieren un protocolo experimental posterior con escenas Middlebury, repeticiones y entorno controlado.

## Ejecución

Trabajador de laptop: `python -m src.distributed.worker --bind tcp://192.168.1.96:5555`.

Maestro PC: `python -m experiments.t18_prebenchmark --connect tcp://192.168.1.96:5555 --height 192 --width 320 --reps 5 --output results/t18_instrumentado_192x320.csv`.

Ejecutar `python -m pytest -q` antes de medir. El resultado de T18 se considera inicial hasta validar todos los tests en el entorno del proyecto y la ejecución interequipos.
