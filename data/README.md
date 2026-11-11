# Datos y licencias

Los assets de ejecución (`traductor/assets/`) se generan a partir de:

| Fuente | Uso | Licencia |
| --- | --- | --- |
| [FreeDict+WikDict eng-spa](https://freedict.org/) 2025.11.23 | Léxico EN→ES y ES→EN (≈60.000 entradas) | CC BY-SA 3.0 |
| [Tatoeba](https://tatoeba.org/) exports `spa_sentences`, `eng_sentences`, `spa-eng_links` | Memoria de frases ES↔EN | CC BY 2.0 FR |

## `curated.json`

Correcciones manuales que se aplican por encima del diccionario:

- `en_es`: palabra inglesa → lista de traducciones españolas (la primera se usa).
- `es_en`: palabra española → lista de traducciones inglesas.

Al construir, si falta una entrada `es_en` se reutiliza la primera traducción de
`en_es`, de modo que ambas direcciones mantengan coherencia.

## Reconstrucción

```bash
python3 scripts/fetch_data.py --dest /tmp/tdata
python3 scripts/build_assets.py \
  --freedict /tmp/tdata/eng-spa/eng-spa.tei \
  --tatoeba /tmp/tdata
```

Salida esperada (aproximada):

- `lexicon_en_es.json.gz` — 52.608 claves
- `lexicon_es_en.json.gz` — 76.506 claves
- `phrases_en_es.tsv.gz` / `phrases_es_en.tsv.gz` — 120.000 frases cada una
- `assets_meta.json` — recuentos, fuentes y licencias (se muestran en la app)

El texto de FreeDict se procesa descartando glosas entre paréntesis y
categorías no léxicas (sufijos, puntuación, símbolos). Las frases de Tatoeba se
normalizan, se limitan a 14 palabras y se ordenan por frecuencia de la palabra
clave para conservar las más útiles.
