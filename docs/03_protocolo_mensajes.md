# Contrato de mensajes ZeroMQ - completar en T14

Topologia: un maestro en PC local y un trabajador en otra PC dentro de una LAN confiable. El maestro trabaja una franja local y solicita una franja remota.

Solicitud propuesta:
- `job_id`, `scene_id`, `block_id`, `start_row`, `end_row` (filas utiles), `halo_top`, `halo_bottom`.
- `image_height`, `image_width`, `window_size`, `d_min`, `d_max`, `dtype`, `shape`.
- Binarios de franjas izquierda y derecha con metadatos; **no** serializar arreglos como listas JSON.

Respuesta propuesta:
- `job_id`, `block_id`, `status`, `dtype`, `shape`, `disparity_bytes`, `valid_mask_bytes`, `compute_seconds` y error si falla.

Mediciones: bytes reales transmitidos por aplicacion, serializacion, envio, retorno, espera, calculo remoto, ensamblado y tiempo total extremo a extremo.

Seguridad: no exponer endpoints sin autenticacion a Internet; usar LAN confiable; habilitar solo puertos necesarios; documentar IPs locales fuera del repositorio.
