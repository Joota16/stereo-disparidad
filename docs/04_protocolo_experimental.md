# Protocolo experimental - acuerdo del equipo

1. Dataset: Middlebury; documentar escenas, resoluciones, ground truth y escala de disparidad.
2. Variables iniciales: resoluciones Quarter y Half; ventanas 7x7 y 15x15; d_max 32 y 64; revisar compatibilidad con cada escena.
3. Versiones: secuencial (1 proceso), multiprocessing (2, 4; 8 segun hardware), dos nodos (1 franja local + 1 remota).
4. Repeticiones iniciales: 10 por combinacion, con calentamiento previo. Mismas imagenes, parametros y codigo SAD.
5. Registrar: modelo CPU/RAM/OS, versiones software, red/latencia aproximada, roles y condiciones de energia.
6. Medir tiempo total con reloj monotono, sin doble conteo de etapas concurrentes. Separar particion, serializacion, envio, compute, retorno, sincronizacion y ensamblado.
7. Registrar bytes transmitidos/recibidos, FPS, speedup, eficiencia CPU homogenea, mediana y dispersion de tiempos.
8. Validar exactitud: mascara valida, MAE/EPE o RMSE de disparidad, bad-pixel ratio, pixeles invalidos; RMSE profundidad solo si hay referencia valida.
9. Resultado principal: cruce de T_distribuido y T_secuencial medido, o no-cruce en las condiciones exploradas.
10. Guardar configuracion, commit de Git, CSV y figuras por corrida; documentar decisiones y fallas.
