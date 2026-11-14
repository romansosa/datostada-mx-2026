# Diccionario de datos

Lo mantiene el carril Datos. Una sección por archivo de `data/clean/`. Si un análisis necesita
una columna que no está aquí, se pide con un issue (`pedido`), no se agrega por cuenta propia.

## MOCIBA 2024 (INEGI) · calentamiento, línea Digital

Script que los genera: `data/limpieza/mociba_2024.py` (lee el ZIP sin descomprimirlo).
Fuente original: `data/raw/conjunto_de_datos_mociba_2024_csv.zip` (ver `docs/fuentes.md`).

### `data/clean/mociba_2024_yucatan.csv`
- Una fila es: una persona entrevistada en Yucatán, usuaria de internet de 12 años o más
  (`p7_1` = 1 en todos los registros; edades de 12 a 91).
- Filas: 1,341 (de 43,434 a nivel nacional) · 285 columnas · Periodo: 2024.
- Población representada (suma de `factor`): 1,677,461 personas.
- Cambios respecto al original: filtro `cve_ent == "31"`; columnas en minúsculas; se agregó
  `id_persona`; `nom_ent` = "Yucatán" (venía "YUCATAN"); `factor` y `edad` como enteros.
  Todo lo demás queda como **texto con los códigos de INEGI** (con ceros a la izquierda). Las
  etiquetas de cada código están en `mociba_2024_catalogo.csv`.
- Celdas vacías = la pregunta no aplica (por ejemplo, de `p5` a `p11` solo se responden si en
  `p4_XX` la persona contestó 1 = Sí). Unas columnas (como `p5_10_2`) están vacías en todo Yucatán.
- **Es una encuesta.** Toda cifra se calcula con `factor`, y su error con `upm_dis` y
  `est_dis`. Yucatán tiene 273 UPM y 15 estratos de diseño que no comparten con otros estados,
  así que se puede estimar con este archivo sin la base nacional. Con 1,341 casos, los cruces
  finos (por ejemplo, tipo de acoso × sexo × edad) tendrán intervalos amplios: reportar siempre el
  intervalo o el coeficiente de variación.

Columnas clave (las 285 están descritas en `mociba_2024_variables.csv`):

| Columna | Tipo | Unidad | Descripción | Ejemplo |
| --- | --- | --- | --- | --- |
| id_persona | texto | — | `upm` + `viv_sel` + `hogar` + `n_ren`; único por fila (12 caracteres) | 310325501102 |
| cve_ent | texto | — | Entidad (siempre `31`). No hay clave de municipio en la base pública | 31 |
| factor | entero | personas | Factor de expansión | 710 |
| upm_dis / est_dis | texto | — | UPM y estrato de diseño (para varianzas) | 08481 / 0424 |
| dominio | texto | — | U = urbano, R = rural | U |
| tloc | texto | — | Tamaño de localidad (1 = 100 mil y más … 4 = menos de 2,500) | 4 |
| estrato | texto | — | Estrato socioeconómico (1 = bajo … 4 = alto) | 2 |
| sexo | texto | — | 1 = hombre, 2 = mujer | 2 |
| edad | entero | años | Años cumplidos | 28 |
| nivel / grado | texto | — | Escolaridad | 06 / 3 |
| p1 | texto | — | ¿Usa medidas de seguridad? 1 Sí, 2 No, 9 NS/NR | 1 |
| p2_1 … p2_8 | texto | — | Medidas de seguridad que usa (1 Sí, 2 No) | 1 |
| p4_01 … p4_13 | texto | — | ¿Vivió cada una de las 13 situaciones de ciberacoso en los últimos 12 meses? (1 Sí, 2 No, 9 NS/NR) | 2 |
| p5_XX_1..3 | texto | — | Identidad de la persona acosadora en la situación XX (hasta 3) | 08 = desconocida(o) |
| p6_XX | texto | — | Sexo de la persona acosadora | 1 |
| p7_XX_1..3 | texto | — | Edad de la persona acosadora | 4 |
| p8_XX_1..3 | texto | — | Motivación de la persona acosadora | 06 |
| p9_XX | texto | — | Frecuencia del acoso | 4 |
| p10_XX_1..3 | texto | — | Efectos en la víctima (enojo, miedo, etcétera) | 07 |
| p11_XX_1..3 | texto | — | Medio digital del acoso | 02 |
| p12_01 … p12_99 | texto | — | Qué hizo frente al ciberacoso (bloquear, denunciar…) | 1 |
| p12a_1 … p12a_5 | texto | — | Ciberdelitos vividos (hackeo de correo, etcétera; 3 = no aplica) | 2 |
| p13 | texto | — | Importancia de la protección de datos (1 muy … 4 nada) | 1 |
| p14 | texto | — | Percepción de qué tan protegidos están sus datos (1 mucho … 4 nada) | 1 |
| p7_1 | texto | — | Usa internet (siempre 1) | 1 |
| p7_4 | texto | horas | Horas de uso de internet al día (01 = una hora o menos) | 15 |
| p8_11usu | texto | — | Se conecta con celular inteligente (1 Sí, 2 No) | 1 |

### `data/clean/mociba_2024_variables.csv`
- Una fila es: una columna de la base (284, en el mismo orden que el archivo de Yucatán).
- Columnas: `columna`, `descripcion` (texto oficial de INEGI), `tipo_inegi`, `longitud`, `rango`.

### `data/clean/mociba_2024_catalogo.csv`
- Una fila es: un código de una columna (2,609 en total).
- Columnas: `columna`, `codigo`, `etiqueta`. Ejemplo: `p13`, `1`, `Muy importante`.
- Para poner etiquetas: unir por `columna` y `codigo` con el valor de la base (como texto).

### Cómo comparar 2019–2025 en el MOCIBA (leer antes de usar los dos archivos de abajo)
- El cuestionario cambió en 2021. 2019 y 2020 preguntaron 10 situaciones de ciberacoso; desde
  2021 son 13 (las mismas 10 más "difundir contenido íntimo", "amenazar con publicar" y "otra").
- **Para cualquier comparación entre años se usa el indicador comparable**
  (`ciberacoso_comparable`, `prevalencia_comparable`): al menos una de las 10 situaciones comunes.
- La cifra oficial (`ciberacoso`, `prevalencia`) es la que publica INEGI cada año. Sirve para
  citar un año suelto, no para comparar 2019–2020 con 2021–2025.
- Qué hay en cada año:

| Tema | 2019 | 2020 | 2021–2025 |
| --- | --- | --- | --- |
| Personas entrevistadas en Yucatán | 508 | 1,240 | 1,319 a 1,408 por año |
| Situaciones de ciberacoso | 10 | 10 | 13 |
| Medio por el que ocurrió | no se preguntó | no se preguntó | sí |
| Quién acosó | una persona por situación; sin "pareja actual" | hasta tres; sin "pareja actual" | hasta tres |
| Qué hizo la víctima | 8 opciones más "otro" | 8 opciones más "otro" | 10 u 11 opciones más "otro" y "ninguna" |

- 2019 tiene menos de la mitad de la muestra: sus intervalos son el doble de anchos. Al
  desglosar 2019 por grupo quedan menos de 100 casos por celda.
- En quién acosó y qué hizo la víctima, la lista de opciones cambió en 2021. Un salto entre 2020
  y 2021 en esas columnas puede venir del cuestionario y no de la realidad.
- `sit_publicar_info_personal` baja de golpe en 2021, justo cuando aparecen las dos situaciones
  nuevas parecidas. Es probable que parte de esos casos se haya movido a las nuevas, así que esa
  situación sola no se compara entre 2020 y 2021. El indicador comparable también puede quedar
  un poco abajo desde 2021 por lo mismo; el valor real está entre el comparable y el oficial.

### `data/clean/mociba_prevalencia_estatal_2019_2025.csv`
- Fuente original: `data/raw/conjunto_de_datos_mociba_<año>_csv.zip`, 2019 a 2025 (ver `docs/fuentes.md`)
- Script que lo genera: `data/limpieza/mociba_serie.py`
- Una fila es: una entidad en un año, más una fila `00` Nacional por año (231 filas).
- Periodo: 2019–2025.
- Las columnas oficiales reproducen las cifras de INEGI (Yucatán 29.7 % en 2024 y 18.6 % en 2025).

| Columna | Tipo | Unidad | Descripción | Ejemplo |
| --- | --- | --- | --- | --- |
| anio | entero | año | Edición del MOCIBA | 2025 |
| cve_ent | texto | — | Clave INEGI de entidad; `00` = nacional | 31 |
| nom_ent | texto | — | Nombre de la entidad | Yucatán |
| prevalencia_comparable | decimal | % | **Para comparar años.** Usuarios de internet de 12+ que vivieron al menos una de las 10 situaciones comunes | 17.3 |
| ee_comparable | decimal | puntos % | Error estándar del indicador comparable | 1.2 |
| ic95_inf_comparable, ic95_sup_comparable | decimal | % | Intervalo de confianza al 95 % del indicador comparable | 15.0 |
| lugar_comparable | entero | — | Lugar entre las 32 entidades con el indicador comparable (1 = mayor) | 25 |
| prevalencia | decimal | % | Cifra oficial del año (10 situaciones en 2019–2020, 13 desde 2021) | 18.6 |
| ee, ic95_inf, ic95_sup | decimal | % | Error estándar e intervalo de la cifra oficial | 16.2 |
| lugar | entero | — | Lugar entre las 32 entidades con la cifra oficial | 25 |
| n | entero | personas | Casos en la muestra | 1378 |
| n_situaciones | entero | — | Situaciones preguntadas ese año (10 o 13) | 13 |
| comparable_2021_2025 | booleano | — | `True` si la cifra oficial de ese año es comparable con 2021–2025 | True |

### `data/clean/mociba_2019_2025_yucatan.csv`
- Fuente original: los ZIP de MOCIBA 2019 a 2025 en `data/raw/`
- Script que lo genera: `data/limpieza/mociba_serie.py`
- Una fila es: una persona entrevistada en Yucatán en un año (8,530 filas).
- Reemplaza a `mociba_2021_2025_yucatan.csv`: mismas columnas y mismos valores para 2021–2025,
  más los años 2019 y 2020 y la columna `ciberacoso_comparable`.
- Cambios respecto al original: columnas armonizadas entre años y convertidas a 0/1. **Una celda
  vacía significa que eso no se preguntó ese año** (ver la tabla de arriba).
- Para estimar: ponderar con `factor`. Para errores estándar, UPM = `upm_dis` y estrato =
  `estrato_pool` (año + `est_dis`; cada año es una muestra distinta).

| Columna | Tipo | Unidad | Descripción | Ejemplo |
| --- | --- | --- | --- | --- |
| anio | entero | año | Edición del MOCIBA | 2024 |
| id_persona | texto | — | upm + viv_sel + hogar + n_ren; único dentro de cada año | 310325501102 |
| factor | entero | personas | Factor de expansión | 710 |
| upm_dis, est_dis, estrato_pool | texto | — | Diseño muestral | 2024-0424 |
| dominio | texto | — | Urbano / Rural | Urbano |
| sexo | texto | — | Hombre / Mujer | Mujer |
| estrato | texto | — | Estrato sociodemográfico de INEGI: 1 Bajo, 2 Medio bajo, 3 Medio alto, 4 Alto | 2 Medio bajo |
| edad, grupo_edad | entero / texto | años | Edad y grupo (12-17, 18-24, 25-34, 35-44, 45-59, 60+) | 18-24 |
| escolaridad | texto | — | Primaria o menos, Secundaria, Bachillerato o técnico, Licenciatura o más (vacío si no sabe) | Secundaria |
| ciberacoso_comparable | 0/1 | — | **Para comparar años.** Vivió al menos una de las 10 situaciones comunes en los últimos 12 meses | 1 |
| ciberacoso | 0/1 | — | Definición oficial del año (todas las situaciones de ese año) | 1 |
| sit_* | 0/1 | — | Vivió esa situación (13 columnas; 3 vacías en 2019–2020) | 0 |
| medio_* | 0/1 | — | Fue acosada por ese medio en alguna situación (13 medios; vacías en 2019–2020) | 1 |
| plataforma_redes_sociales, plataforma_mensajeria, plataforma_llamadas, plataforma_correo | 0/1 | — | Fue acosada por alguno de los medios de esa plataforma. Redes: Facebook, Instagram, TikTok, X, YouTube. Mensajería: WhatsApp, Messenger, Telegram, SMS. Llamadas: celular, fijo. Correo: institucional, personal. Vacías en 2019–2020 | 1 |
| agresor_desconocido, agresor_pareja_o_ex, agresor_familia_amigo_companero | 0/1 | — | Quién la acosó en alguna situación. En 2019–2020 `pareja_o_ex` solo incluye expareja | 1 |
| accion_* | 0/1 | — | Qué hizo ante el ciberacoso. `denunciar_autoridad` = Ministerio Público/Fiscalía o policía. Vacías en 2019–2020: `publicarlo_en_redes`, `denunciar_escuela_trabajo`, `ninguna_accion` | 1 |

## Plantilla (cópiala para cada archivo)

### `data/clean/<archivo>.csv`
- Fuente original: `data/raw/<archivo original>` (ver `docs/fuentes.md`)
- Script que lo genera: `data/limpieza/<script>.py`
- Una fila es: (por ejemplo: un municipio en un año)
- Filas: · Periodo:
- Cambios respecto al original: (filtros, columnas renombradas, valores corregidos)

| Columna | Tipo | Unidad | Descripción | Ejemplo |
| --- | --- | --- | --- | --- |
| cve_mun | texto | — | Clave INEGI de 5 dígitos (entidad + municipio) | 31050 |
| anio | entero | año | Año de referencia | 2025 |
