# T18 — Control de intercambio ZeroMQ sin SAD

## Propósito

Estimar el tiempo extremo a extremo de un intercambio ZeroMQ con el mismo formato y el mismo orden de magnitud de bytes que una solicitud SAD distribuida, **pero sin ejecutar SAD en la laptop**. Es un control metodológico para interpretar los tiempos experimentales; no es un algoritmo de disparidad.

## Diseño

- Se usa `encode_request` con la franja remota y sus halos.
- El trabajador ejecuta `decode_request`, prepara un mapa `float32` lleno de NaN y una máscara `uint8` nula, y responde con `encode_response`.
- La respuesta tiene la misma forma y tamaño binario que SAD real.
- El maestro verifica la respuesta, la decodifica y cronometra el intercambio completo **incluyendo serialización y creación/cierre del socket**.
- Se descartan cinco calentamientos y se registran treinta repeticiones por defecto.

## Interpretación

`roundtrip_seconds` **NO** es latencia pura de red ni tiempo unidireccional. Contiene configuración de socket, buffers, serialización y deserialización, procesamiento ligero del trabajador, cola ZeroMQ y transporte bidireccional. El tiempo no se puede restar directamente del tiempo total distribuido para atribuir el resto exclusivamente a SAD: en la implementación real el cálculo local y remoto se solapan, y la ejecución en ambos programas es diferente.

## Ejecución

Cerrar `src.distributed.worker` que ocupa el puerto 5555 antes de iniciar el control.

Laptop:

```powershell
.\.venv\Scripts\python.exe -m experiments.t18_roundtrip --role worker --bind tcp://192.168.1.96:5555
```

PC:

```powershell
.\.venv\Scripts\python.exe -m experiments.t18_roundtrip --role master --connect tcp://192.168.1.96:5555 --height 192 --width 320 --warmups 5 --reps 30 --output results/t18_roundtrip_192x320.csv
```

Ambas máquinas necesitan el mismo código del control. Mantener el puerto accesible únicamente por la PC en una LAN de confianza. Tras terminar, detener el control de la laptop con Ctrl+C y volver a iniciar el trabajador SAD real.
