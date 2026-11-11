# Traductor offline ES ⇄ EN

Traductor español-inglés que funciona **sin internet**, pensado para PC
(Linux/Windows) y Android. Está hecho con **Flet** (Python + Flutter) y un motor
léxico propio: no descarga modelos ni usa servicios en la nube, y los datos
viajan dentro de la app (~6,1 MB comprimidos).

## Características

- Traducción ES → EN y EN → ES con detección automática de la dirección cuando
  el texto es claramente del otro idioma.
- Memoria de frases (Tatoeba) + diccionario (FreeDict+WikDict) + morfología
  (plurales, géneros, tiempos verbales, gerundios, contracciones).
- Alternativas por palabra, palabras sin traducir señaladas y nivel de
  confianza.
- Historial local persistente, copiar/pegar, tema claro/oscuro, atajo `Enter`.
- Interfaz adaptable a móvil y escritorio; todo el estado vive en el
  dispositivo.

## Inicio rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

flet run                 # ventana de escritorio
flet run --web           # vista previa en el navegador
```

Los assets ya están versionados en `traductor/assets/`, así que no hace falta
descargar nada para ejecutar la app.

## Estructura

```
main.py                     punto de entrada para flet run/build
traductor/
  app/controller.py         estado, dirección, historial (sin UI, testeable)
  app/ui.py                 interfaz Flet
  engine/text.py            normalización, tokenización, detección de idioma
  engine/morphology.py      lematización ES/EN
  engine/inflect.py         plurales, tiempos, gerundios, adjetivos
  engine/translator.py      motor: frases, léxico, morfología, post-proceso
  engine/models.py          TranslationResult
  assets/                   datos comprimidos de ejecución
scripts/
  fetch_data.py             descarga FreeDict + Tatoeba
  build_assets.py           genera los assets desde las fuentes
  build_linux.sh            bundle de escritorio
  build_apk.sh              APK por arquitectura
tests/                      pruebas unitarias y de integración
data/curated.json           correcciones manuales incorporadas al build
data/README.md              fuentes y licencias
seesion_brief.md            bitácora de sesiones (contexto para futuras sesiones)
```

## Reconstruir los datos

```bash
python3 scripts/fetch_data.py --dest /tmp/tdata
python3 scripts/build_assets.py \
  --freedict /tmp/tdata/eng-spa/eng-spa.tei \
  --tatoeba /tmp/tdata
```

`build_assets.py` tarda un par de minutos y reescribe `traductor/assets/`.
Las correcciones manuales se editan en `data/curated.json` y se hornean en los
léxicos.

## Compilar

Requisitos: Flutter 3.x, Java 17+ y Flet CLI (`pip install flet==1.1.2`).

```bash
# Linux (necesita CMake, ninja, clang y GTK 3)
scripts/build_linux.sh

# Android (requiere Android SDK con licencias aceptadas)
scripts/build_apk.sh arm64-v8a
```

Los APK se generan por ABI (`--split-per-abi`) para que cada teléfono descargue
solo lo suyo. El resultado de la última compilación es
`build/apk/traductor_offline-arm64-v8a.apk` (~59 MB). La app no pide permisos
peligrosos ni accede a cámara, contactos o ubicación; la plantilla de Flutter
declara `INTERNET`/`ACCESS_NETWORK_STATE` (permisos normales) para los sockets
locales del runtime Python, pero todo el contenido es offline y no hay tráfico
de red.

## Pruebas

```bash
pip install pytest
python -m pytest -q
```

Cobertura actual: ver `seesion_brief.md` para resultados y fecha de la última
ejecución. Las pruebas de integración usan los assets reales empaquetados.

## Limitaciones conocidas

- El motor es léxico, no neuronal: el orden de palabras y la concordancia de
  adjetivos pueden sonar poco naturales en frases largas.
- No conjuga verbos españoles a partir del tiempo/persona ingleses (usa la forma
  de diccionario o el gerundio cuando corresponde).
- Algunas formas ambiguas (`fue`, `hablas`) eligen una interpretación por
  frecuencia.
- La memoria de frases puede devolver una traducción del corpus distinta del
  matiz buscado.

## Licencias de datos

- FreeDict+WikDict eng-spa — CC BY-SA 3.0 (https://freedict.org/)
- Tatoeba spa-eng — CC BY 2.0 FR (https://tatoeba.org/)

El código de la app no se distribuye con una licencia explícita todavía; añadir
una antes de publicar.
