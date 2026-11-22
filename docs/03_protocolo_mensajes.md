# Protocolo ZeroMQ de franjas SAD (T14–T15)

## Arquitectura
Maestro en PC y trabajador remoto en laptop, bajo LAN de confianza. Utilizar socket ZeroMQ `REQ` en maestro y `REP` en trabajador. El maestro procesa localmente la primera franja mientras el trabajador calcula la segunda.

## Mensaje de solicitud (3 frames)
1. JSON UTF-8 con `version=1`, `operation="sad"`, `job_id`, `image_height`, `shape=[alto_franka, ancho]`, `dtype="uint8"`, `window_size`, `d_min`, `d_max` y `part` (`worker_id`, `row_start`, `row_end`, `halo_start`, `halo_end`).
2. Bytes contiguos de imagen izquierda (`uint8`, orden C, tamaño `alto_franka*ancho`).
3. Bytes contiguos de imagen derecha (`uint8`, mismo formato).

Los intervalos son `[inicio, fin)`. Los halos son filas que solo proporcionan contexto; no deben duplicarse en el resultado final. Se conserva el ancho completo.

## Respuesta normal (3 frames)
1. JSON UTF-8 con `version=1`, `status="ok"`, `job_id`, `worker_id`, `shape`, `disparity_dtype="<f4"`, `mask_dtype="uint8"`, `compute_seconds`.
2. Bytes del mapa local de disparidad `float32` little-endian, orden C, NaN en inválidos.
3. Bytes de la máscara local `uint8` (0 y 1) orden C.

## Respuesta de error (3 frames)
1. JSON UTF-8 con `version=1`, `status="error"`, `message`.
2. Bytes vacíos.
3. Bytes vacíos.

## Límites y validación
Se validan versiones, tipos, dimensiones, límites de franja, tamaños de buffers y consistencia del `job_id` y `worker_id`. La prueba restringe la franja a un máximo de 4 194 304 píxeles. El protocolo no proporciona autenticación ni cifrado: solo ejecutar en una LAN de confianza con puerto TCP 5555 restringido a las IPs previstas. No exponerlo en Internet.

## Mediciones preliminares
`total_seconds`: tiempo extremo a extremo del maestro (incluye preparación, transporte, cómputo local, espera, ensamblado).
`local_compute_seconds`: cálculo SAD de franja local.
`remote_compute_seconds`: cálculo SAD informado por el trabajador.
`receive_wait_seconds`: tiempo que el maestro bloquea esperando la respuesta; **no equivale al tiempo puro de red**.
`request_payload_bytes` / `response_payload_bytes`: bytes de aplicación enviados/recibidos, sin overhead de TCP/ZeroMQ.

La descomposición rigurosa de costos de comunicación y las repeticiones con hardware estable corresponden a T18–T19.
