# Lúmina · Estudio de imagen con IA local

Retratos, personajes, edición y restauración de fotografías con modelos ejecutados en tu equipo. Interfaz HTML/CSS/JavaScript, API FastAPI, PyTorch/Diffusers y almacenamiento MongoDB/GridFS.

**[Ver presentación y catálogo](https://helynecheverry.github.io/lumina-ia/)** · [Código](https://github.com/helynecheverry/lumina-ia)

## Qué incluye

- 32 estilos y 12 perfiles visuales, con controles de vestuario, escena e iluminación.
- Generación con referencia facial: Realistic Vision/DreamShaper + IP-Adapter, RealVisXL, FLUX.2 klein y Qwen Image Edit según recursos e instalación.
- Descubrimiento de semejanza visual con Pokémon, Digimon y guardianes zodiacales mediante un análisis local. Es una actividad recreativa.
- Recreación de una versión joven, entre 8 y 17 años, mediante edición guiada. Identidad y edad aproximadas; no recupera fotos del pasado.
- Restauración y ampliación con Real-ESRGAN, editor, cola persistente, cancelación e historial.

Las imágenes del catálogo son ilustraciones conceptuales sintéticas; **no son resultados de los motores locales ni pruebas de fidelidad**. La fotografía de ejemplo incluida también es sintética. No se incluyen fotografías personales.

## GitHub Pages

La página pública permite explorar estilos y conocer los motores. Es una presentación estática: no carga pesos, no recibe fotografías y no ejecuta inferencia. Para generar imágenes, instala y abre la aplicación local.

La publicación se sirve desde `docs/` en la rama `main`. Los enlaces y recursos son relativos para funcionar bajo la ruta del repositorio.

## Instalación local

Entorno de referencia: Python 3.10, PyTorch 2.6.0 + CUDA 12.4 y torchvision 0.21.0. Instala una distribución de PyTorch adecuada para tu GPU. La inferencia generativa requiere CUDA; memoria y tiempos dependen de cada motor.

```bash
git clone https://github.com/helynecheverry/lumina-ia.git
cd lumina-ia
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/prepare_environment.py
cp .env.example .env
bash scripts/setup_mongo.sh
python scripts/download_influencer.py
python scripts/download_portrait_upgrade.py
python scripts/download_creative_models.py
bash scripts/start.sh
```

`setup_mongo.sh` está dirigido a Ubuntu 24.04 x86_64 y descarga MongoDB 8.0.16. En otros sistemas instala MongoDB por separado y configura `MONGO_URI`. El arranque usa `python` del entorno activo; admite `PYTHON_BIN=/ruta/al/python bash scripts/start.sh`.

- Interfaz: <http://127.0.0.1:8501>
- Estudio: <http://127.0.0.1:8501/studio>
- API: <http://127.0.0.1:8000/docs>
- Detener: `bash scripts/stop.sh`.

Es una aplicación local: los servicios escuchan en loopback. El historial se guarda en MongoDB y las fotos no se envían a APIs de generación. La primera instalación descarga modelos externos.

## Pesos: descarga independiente

**Este repositorio no distribuye pesos.** Los scripts descargan los modelos a `weights/`, excluido de Git.

Para restauración, descarga `RealESRGAN_x4plus.pth` desde los [releases oficiales de Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN/releases) y guárdalo en `weights/RealESRGAN_x4plus.pth`.

Motores opcionales:

```bash
python scripts/install_studio_model.py portrait_sdxl
bash scripts/setup_modern_runtime.sh
python scripts/install_studio_model.py flux_klein
# Alternativa de edición con mayores necesidades de memoria:
python scripts/install_studio_model.py qwen_edit
```

Consulta `app/model_registry.py` para las revisiones fijadas, las resoluciones y los requisitos de cada motor. FLUX declara 13 GB de VRAM como perfil estándar y Qwen 24 GB. El perfil experimental de FLUX con poca memoria exige una validación local generada por `scripts/probe_flux_low_memory.py`; los informes de otro equipo no se distribuyen. No se garantiza el funcionamiento de todos los motores en una GPU de 4 GB.

Para el análisis de criaturas:

```bash
python scripts/install_discovery_model.py
python scripts/prepare_discovery_index.py
```

Ejecuta instalaciones y preparación sin generaciones en curso. Algunos modelos pueden requerir aceptar condiciones de acceso de su proveedor.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `app/` | API, inferencia, catálogo, cola y servidor del frontend |
| `web/` | Aplicación local y recursos visuales |
| `scripts/` | Instalación, validación y herramientas de desarrollo |
| `tests/` | Pruebas de contratos y regresión |
| `experiments/` | Casos reproducibles sin imágenes personales |
| `docs/` | Presentación estática de GitHub Pages |

## Verificación

Desde el entorno con dependencias instaladas:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Las pruebas de frontend requieren servicios locales y Playwright/Chrome. Algunas pruebas de inferencia requieren pesos, GPU o archivos producidos por experimentos locales; no se incluyen esos resultados. Para revisar únicamente contratos sin navegador, puedes ejecutar archivos concretos:

```bash
python -m unittest discover -s tests -p 'test_youth.py'
python -m unittest discover -s tests -p 'test_discovery.py'
```

## Publicación y recursos

Se publica código, configuración de ejemplo, pruebas y recursos necesarios. Quedan fuera credenciales, `.env`, pesos, bases de datos, imágenes subidas, resultados, cuadernos con salidas, conversaciones con IA y documentación de sesiones. El repositorio tiene un historial nuevo e independiente del desarrollo local.

Los textos de instrucciones en el código forman parte del funcionamiento del generador. No son transcripciones de conversaciones.

Consulta [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) para las fuentes y licencias de recursos y modelos. Los modelos y personajes de terceros conservan sus condiciones originales. La superresolución puede inventar texturas y las transformaciones pueden modificar la identidad visual.
