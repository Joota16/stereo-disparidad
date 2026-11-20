# Dataset: Middlebury Stereo 2014

Conjunto de datos estéreo de referencia Middlebury Stereo 2014 para evaluación de algoritmos de correspondencia estéreo densa.

## Escenas seleccionadas
- **Adirondack (Piloto):** Planos estructurados y texturas diferenciadas.
  - Quarter (Q): $D_{\max} = 70$.
  - Half (H): $D_{\max} = 140$.
- **Jadeplant:** Follaje y oclusiones finas.
- **Motorcycle:** Zonas reflectantes y regiones lisas.

## Descarga de datos
Las imágenes y referencias deben ubicarse en:
- `data/raw/<escena>_<resolucion>/im0.png` (izquierda)
- `data/raw/<escena>_<resolucion>/im1.png` (derecha)
- `data/raw/<escena>_<resolucion>/calib.txt` (calibración)
- `data/ground_truth/<escena>_<resolucion>/disp0.pfm` (disparidad de referencia)

Ejemplo de descarga directa para Adirondack Quarter:
```bash
curl -O https://vision.middlebury.edu/stereo/data/scenes2014/zip/Adirondack-perfect.zip
unzip Adirondack-perfect.zip
```

Fuente oficial: https://vision.middlebury.edu/stereo/data/scenes2014/
