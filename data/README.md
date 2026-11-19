# Dataset
Usar **Middlebury Stereo** con imagen izquierda, derecha, mapa de referencia y calibracion cuando corresponda.

- `raw/`: pares de imagenes rectificadas, separados por escena/resolucion.
- `ground_truth/`: disparidad de referencia, mascara y archivos de calibracion, si los hay.
- No incorporar datasets pesados al repositorio; documentar URL, licencia, fecha, escena, formato y escalado.
- Verificar que el `ground truth` de la resolucion corresponda a la escala de disparidad usada.

Fuente: https://vision.middlebury.edu/stereo/data/
