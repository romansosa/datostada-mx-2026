# Entrega 3 · Dashboard en Tableau · GAFEROSADA

Reto Yucatán Digital: ¿qué grupos de edad concentran el ciberacoso en Yucatán de manera constante
entre 2019 y 2025, y en qué plataformas digitales lo vive cada grupo?

## El entregable

- `dashboard_pitch.twbx`: libro empaquetado, con los seis CSV de `data/tableau/` incorporados.
  Pestañas «Historia» (vista principal) y «Contexto», con botones para ir y volver. Interacción: clic
  en una fila de la matriz 01 y la gráfica 02 muestra las plataformas de esa edad. Tamaño
  automático: para verlo a pantalla completa, modo presentación con F7 (pensado para 1920 × 1080).
- `dashboard_pitch.pdf`: PDF de respaldo de las dos pestañas (exportado a 1920 × 1080).

## Soporte para verificar (misma estructura de carpetas que el repositorio de trabajo)

| Carpeta | Qué hay |
| --- | --- |
| `data/raw/` | Los 7 ZIP originales de microdatos del MOCIBA 2019–2025 (INEGI, datos abiertos) |
| `data/limpieza/mociba_serie.py` | Filtra Yucatán, armoniza 2019–2025 (indicador comparable de 10 situaciones) y valida contra INEGI |
| `data/clean/` | Base de Yucatán 2019–2025 (8,530 personas) y prevalencia estatal por año |
| `analisis/` | Un script por pregunta, con sus tablas y gráficas (factores de expansión, IC 95 % por diseño) |
| `data/tableau/` | Los seis extractos que usa el libro (salen de los scripts de `analisis/`) |
| `tableau/construir_twbx_pitch.py` | Rehace el `.twbx` desde los CSV |
| `docs/` | Fuentes, diccionario de datos y tablas de la exploración |

Para reproducir (Python 3.11+): `pip install -r requirements.txt`, luego, desde esta carpeta,
`python data/limpieza/mociba_serie.py` y `python analisis/<carpeta>/analisis.py`.

| Pieza del dashboard | Script | Extracto |
| --- | --- | --- |
| 1 · Brecha y matriz edad × año | `analisis/A-edad-plataforma/analisis.py` | `A-edad_kpi.csv`, `A-edad_anio.csv` |
| 2 · Plataformas por edad | `analisis/B-plataforma/analisis.py` | `B-edad_plataforma.csv` |
| 3 · Qué hacen las víctimas | `analisis/B-acciones/analisis.py` | `B-edad_acciones.csv` |
| Contexto: ranking, sexo, escolaridad, zona | `analisis/A-contexto/analisis.py` | `A-yucatan_vs_nacional.csv`, `A-contexto_grupos.csv` |
| Verificaciones (cortes de edad, sexo, picos) | `analisis/A-verificacion/`, `analisis/B-picos/` | — |

Límites: es una encuesta (estimaciones con margen de error); relación, no causa; nivel estatal (la
base pública no trae municipio); plataformas y acciones solo 2021–2025.

Uso de IA: Claude (Anthropic) apoyó la armonización de los microdatos, los scripts de estimación y
el armado del libro; el equipo verificó las cifras contra las publicadas por INEGI.
