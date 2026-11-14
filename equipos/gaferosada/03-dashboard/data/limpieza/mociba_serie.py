"""Serie MOCIBA 2019–2025 (INEGI): prevalencia estatal y base armonizada de Yucatán.

Lee los ZIP originales de data/raw/ (conjunto_de_datos_mociba_<año>_csv.zip) y escribe:

- data/clean/mociba_prevalencia_estatal_2019_2025.csv
    Una fila por (año, entidad) más una fila "00 Nacional" por año.
- data/clean/mociba_2019_2025_yucatan.csv
    Una fila por persona entrevistada en Yucatán en 2019–2025, con columnas armonizadas.
- docs/exploracion_mociba.md
    Tablas de la exploración (las genera este script; no editar a mano).

CÓMO COMPARAR 2019–2025
El cuestionario cambió en 2021: 2019 y 2020 preguntaron 10 situaciones de ciberacoso y desde
2021 son 13 (las mismas 10 más 3 nuevas). Por eso hay dos indicadores:

- `ciberacoso` / `prevalencia`: la cifra oficial de cada año (todas las situaciones de ese año).
  Reproduce lo que publica INEGI (Yucatán 29.7 % en 2024 y 18.6 % en 2025), pero 2019–2020 no
  se pueden comparar con 2021–2025.
- `ciberacoso_comparable` / `prevalencia_comparable`: al menos una de las 10 situaciones que se
  preguntaron los siete años. **Es el indicador para cualquier comparación 2019–2025.**

Lo que no existe en 2019–2020 queda vacío en la base: los medios (se preguntan desde 2021), las
3 situaciones nuevas y algunas acciones. Detalle en `docs/diccionario.md`.

Errores estándar: linealización de Taylor para una razón, con UPM de diseño (`upm_dis`) dentro
de estratos de diseño (`est_dis`), con reemplazo. Para juntar años, el estrato es
`estrato_pool` (año + `est_dis`), porque cada año es una muestra distinta.

Uso (desde la raíz del repo):  python data/limpieza/mociba_serie.py
"""

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data/raw/conjunto_de_datos_mociba_{}_csv.zip"
CLEAN = RAIZ / "data/clean"
DOC = RAIZ / "docs/exploracion_mociba.md"
ANIOS = range(2019, 2026)
YUC = "31"
TODOS = "2019–2025"

# Situación: (columna en 2019–2020, columna en 2021–2025). None = no se preguntaba.
# El emparejamiento se hizo por el texto de la pregunta en el diccionario de cada año.
SITUACIONES = {
    "mensajes_ofensivos": ("p4_01", "p4_01"),
    "llamadas_ofensivas": ("p4_02", "p4_02"),
    "criticas_apariencia_clase": ("p4_04", "p4_03"),
    "usurpacion_identidad": ("p4_06", "p4_04"),
    "contacto_nombres_falsos": ("p4_07", "p4_05"),
    "vigilar_cuentas": ("p4_08", "p4_06"),
    "provocar_en_linea": ("p4_09", "p4_07"),
    "insinuaciones_sexuales": ("p4_05", "p4_08"),
    "envio_contenido_sexual": ("p4_10", "p4_09"),
    "difundir_contenido_intimo": (None, "p4_10"),
    "publicar_info_personal": ("p4_03", "p4_11"),
    "amenazar_con_publicar": (None, "p4_12"),
    "otra_situacion": (None, "p4_13"),
}
COMUNES = [nom for nom, (antes, _) in SITUACIONES.items() if antes]

# Medios (p11): solo 2021–2025; los códigos 01–13 son iguales en esos cinco años.
MEDIOS = {
    "01": "whatsapp", "02": "facebook", "03": "messenger", "04": "instagram", "05": "tiktok",
    "06": "telegram", "07": "x_twitter", "08": "youtube", "09": "sms", "10": "correo_institucional",
    "11": "correo_personal", "12": "llamada_celular", "13": "llamada_fijo",
}

# Medios agrupados en plataformas (pregunta principal de D-02). El código 14 ("otro" hasta
# 2024; "videojuegos" en 2025) y el 15 de 2025 no entran en ninguna.
PLATAFORMAS = {
    "redes_sociales": ["facebook", "instagram", "tiktok", "x_twitter", "youtube"],
    "mensajeria": ["whatsapp", "messenger", "telegram", "sms"],
    "llamadas": ["llamada_celular", "llamada_fijo"],
    "correo": ["correo_institucional", "correo_personal"],
}

# Acción ante el ciberacoso: (columna en 2019–2020, número de p12 en 2021–2025).
# 2019–2020: p10_1..p10_9. 2021–2022: p12_1..p12_12 (sin cero). 2023–2025: p12_01..p12_13.
# "confrontar" en 2019–2020 decía "hablar con la persona".
ACCIONES = {
    "bloquear": ("p10_1", 1), "cambiar_numero_cuenta": ("p10_2", 2),
    "eliminar_publicacion": ("p10_3", 3), "confrontar": ("p10_4", 4),
    "reportar_plataforma": ("p10_6", 6), "contarle_a_alguien": ("p10_7", 7),
    "ignorar": ("p10_8", 8), "publicarlo_en_redes": (None, 9),
    "denunciar_escuela_trabajo": (None, 10),
}
# "denunciar_autoridad" = Ministerio Público/Fiscalía o policía (juntas hasta 2022, separadas
# desde 2023). "ninguna_accion" solo existe como opción desde 2021.
ACCIONES_LISTA = list(ACCIONES) + ["denunciar_autoridad", "ninguna_accion"]

ENTIDADES = {
    "00": "Nacional", "01": "Aguascalientes", "02": "Baja California", "03": "Baja California Sur",
    "04": "Campeche", "05": "Coahuila", "06": "Colima", "07": "Chiapas", "08": "Chihuahua",
    "09": "Ciudad de México", "10": "Durango", "11": "Guanajuato", "12": "Guerrero",
    "13": "Hidalgo", "14": "Jalisco", "15": "México", "16": "Michoacán", "17": "Morelos",
    "18": "Nayarit", "19": "Nuevo León", "20": "Oaxaca", "21": "Puebla", "22": "Querétaro",
    "23": "Quintana Roo", "24": "San Luis Potosí", "25": "Sinaloa", "26": "Sonora",
    "27": "Tabasco", "28": "Tamaulipas", "29": "Tlaxcala", "30": "Veracruz", "31": "Yucatán",
    "32": "Zacatecas",
}

ORDEN = {
    "sexo": ["Hombre", "Mujer"],
    "grupo_edad": ["12-17", "18-24", "25-34", "35-44", "45-59", "60+"],
    "escolaridad": ["Primaria o menos", "Secundaria", "Bachillerato o técnico", "Licenciatura o más"],
    "dominio": ["Urbano", "Rural"],
    "estrato": ["1 Bajo", "2 Medio bajo", "3 Medio alto", "4 Alto"],
}


def leer(anio: int) -> pd.DataFrame:
    """Microdatos de un año. Algunos años vienen en latin-1, con CR y con espacios pegados."""
    z = zipfile.ZipFile(str(RAW).format(anio))
    nombre = next(n for n in z.namelist() if "/conjunto_de_datos/" in "/" + n and n.endswith(".csv"))
    crudo = z.read(nombre)
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = crudo.decode("latin-1")
    df = pd.read_csv(io.StringIO(texto, newline=""), dtype=str, low_memory=False)
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.apply(lambda s: s.astype("string").str.strip()).fillna("")
    df["cve_ent"] = (df["cve_ent"] if "cve_ent" in df else df["ent"]).str.zfill(2)
    df["factor"] = df["factor"].astype(float)
    era = 0 if anio <= 2020 else 1
    sit = {}
    for nom, cols in SITUACIONES.items():
        sit[f"sit_{nom}"] = (df[cols[era]] == "1").astype(float) if cols[era] else np.nan
    p4 = [c for c in df.columns if re.fullmatch(r"p4_\d+", c)]
    sit["ciberacoso"] = (df[p4] == "1").any(axis=1).astype(int)
    df = pd.concat([df, pd.DataFrame(sit, index=df.index)], axis=1)
    df["ciberacoso_comparable"] = (df[[f"sit_{n}" for n in COMUNES]] == 1).any(axis=1).astype(int)
    df["anio"] = anio
    df.attrs["n_situaciones"] = len(p4)
    return df


def proporcion(df: pd.DataFrame, var: str, dominio=None) -> tuple[float, float, int]:
    """Proporción ponderada con EE por linealización (UPM dentro de estratos, con reemplazo).

    Devuelve (p, ee, n). Si la variable no se preguntó en ese dominio (vacía), p y ee son NaN.
    """
    z = df[var].astype(float).to_numpy()
    w = df["factor"].to_numpy(dtype=float)
    m = np.ones(len(df), bool) if dominio is None else np.asarray(dominio, bool)
    n = int(m.sum())
    W = (w * m).sum()
    if n == 0 or W == 0 or np.isnan(z[m]).any():
        return np.nan, np.nan, n
    z = np.where(m, z, 0.0)
    p = (w * m * z).sum() / W
    estrato = df["estrato_pool"] if "estrato_pool" in df else df["est_dis"]
    u = pd.DataFrame({"h": estrato.to_numpy(), "c": df["upm_dis"].to_numpy(),
                      "u": w * m * (z - p) / W})
    tot = u.groupby(["h", "c"], sort=False)["u"].sum()
    g = tot.groupby(level="h", sort=False)
    k = g.transform("size").to_numpy(dtype=float)
    dif = (tot - g.transform("mean")).to_numpy()
    v = (np.where(k > 1, k / np.maximum(k - 1, 1), 0.0) * dif ** 2).sum()
    return float(p), float(np.sqrt(v)), n


def prevalencia_estatal(datos: dict[int, pd.DataFrame]) -> pd.DataFrame:
    filas = []
    for anio, df in datos.items():
        res = []
        for ent in ["00"] + sorted(df["cve_ent"].unique()):
            dom = None if ent == "00" else (df["cve_ent"] == ent)
            p, ee, n = proporcion(df, "ciberacoso", dom)
            pc, eec, _ = proporcion(df, "ciberacoso_comparable", dom)
            res.append({"anio": anio, "cve_ent": ent, "nom_ent": ENTIDADES[ent], "n": n,
                        "prevalencia": p, "ee": ee,
                        "prevalencia_comparable": pc, "ee_comparable": eec})
        t = pd.DataFrame(res)
        est = t["cve_ent"] != "00"
        for suf in ["", "_comparable"]:
            t.loc[est, f"lugar{suf}"] = t.loc[est, f"prevalencia{suf}"].rank(
                ascending=False, method="min")
        t["n_situaciones"] = df.attrs["n_situaciones"]
        filas.append(t)
    out = pd.concat(filas, ignore_index=True)
    for suf in ["", "_comparable"]:
        out[f"ic95_inf{suf}"] = out[f"prevalencia{suf}"] - 1.96 * out[f"ee{suf}"]
        out[f"ic95_sup{suf}"] = out[f"prevalencia{suf}"] + 1.96 * out[f"ee{suf}"]
        for c in [f"prevalencia{suf}", f"ee{suf}", f"ic95_inf{suf}", f"ic95_sup{suf}"]:
            out[c] = (out[c] * 100).round(3)
        out[f"lugar{suf}"] = out[f"lugar{suf}"].astype("Int64")
    out["comparable_2021_2025"] = out["anio"] >= 2021
    return out[["anio", "cve_ent", "nom_ent", "prevalencia", "ee", "ic95_inf", "ic95_sup", "n",
                "lugar", "n_situaciones", "comparable_2021_2025", "prevalencia_comparable",
                "ee_comparable", "ic95_inf_comparable", "ic95_sup_comparable",
                "lugar_comparable"]]


def col_p12(d: pd.DataFrame, k: int) -> pd.Series:
    nombre = f"p12_{k:02d}" if f"p12_{k:02d}" in d else f"p12_{k}"
    return d[nombre] == "1"


def yucatan_armonizado(datos: dict[int, pd.DataFrame]) -> pd.DataFrame:
    partes = []
    for anio, d in datos.items():
        d = d[d["cve_ent"] == YUC]
        antes = anio <= 2020
        out = pd.DataFrame({
            "anio": anio,
            "id_persona": (d["upm"].str.zfill(7) + d["viv_sel"].str.zfill(2) + d["hogar"]
                           + d["n_ren"].str.zfill(2)),
            "factor": d["factor"].astype(int),
            "upm_dis": d["upm_dis"],
            "est_dis": d["est_dis"],
            "estrato_pool": str(anio) + "-" + d["est_dis"],
            "dominio": d["dominio"].map({"U": "Urbano", "R": "Rural"}),
            "sexo": d["sexo"].map({"1": "Hombre", "2": "Mujer"}),
            "estrato": d["estrato"].map(dict(zip("1234", ORDEN["estrato"]))),
            "edad": pd.to_numeric(d["edad"], errors="coerce").astype("Int64"),
        })
        out["grupo_edad"] = pd.cut(out["edad"].astype(float), [11, 17, 24, 34, 44, 59, 200],
                                   labels=ORDEN["grupo_edad"])
        nivel = pd.to_numeric(d["nivel"], errors="coerce")
        out["escolaridad"] = pd.cut(nivel, [-1, 2, 3, 7, 11], labels=ORDEN["escolaridad"])
        out["ciberacoso"] = d["ciberacoso"].to_numpy()
        out["ciberacoso_comparable"] = d["ciberacoso_comparable"].to_numpy()
        for nom in SITUACIONES:
            out[f"sit_{nom}"] = d[f"sit_{nom}"].to_numpy()

        p11 = [c for c in d.columns if re.fullmatch(r"p11_\d\d_\d", c)]
        for cod, nom in MEDIOS.items():
            out[f"medio_{nom}"] = (np.nan if antes
                                   else (d[p11] == cod).any(axis=1).astype(float).to_numpy())

        for plat, medios in PLATAFORMAS.items():
            out[f"plataforma_{plat}"] = (np.nan if antes else
                                         out[[f"medio_{m}" for m in medios]].max(axis=1).to_numpy())

        # Quién acosó (p5). 2019: una persona por situación; 2020 en adelante: hasta tres.
        # 2019–2020 no tenían la opción "pareja actual" (solo expareja).
        p5 = [c for c in d.columns if re.fullmatch(r"p5_\d\d(_\d)?", c)]
        desc, pareja, cerca = ((["7"], ["1"], ["2", "3", "4"]) if antes
                               else (["08"], ["01", "02"], ["03", "04", "05"]))
        out["agresor_desconocido"] = d[p5].isin(desc).any(axis=1).astype(float).to_numpy()
        out["agresor_pareja_o_ex"] = d[p5].isin(pareja).any(axis=1).astype(float).to_numpy()
        out["agresor_familia_amigo_companero"] = (
            d[p5].isin(cerca).any(axis=1).astype(float).to_numpy())

        for nom, (col_antes, k) in ACCIONES.items():
            if antes:
                out[f"accion_{nom}"] = ((d[col_antes] == "1").astype(float).to_numpy()
                                        if col_antes else np.nan)
            else:
                out[f"accion_{nom}"] = col_p12(d, k).astype(float).to_numpy()
        if antes:
            autoridad, ninguna = (d["p10_5"] == "1"), None
        elif "p12_13" in d:  # 2023–2025
            autoridad, ninguna = col_p12(d, 5) | col_p12(d, 11), col_p12(d, 13)
        else:  # 2021–2022
            autoridad, ninguna = col_p12(d, 5), col_p12(d, 12)
        out["accion_denunciar_autoridad"] = autoridad.astype(float).to_numpy()
        out["accion_ninguna_accion"] = np.nan if ninguna is None else ninguna.astype(float).to_numpy()
        partes.append(out)
    yuc = pd.concat(partes, ignore_index=True)
    binarias = [c for c in yuc.columns
                if c.startswith(("sit_", "medio_", "plataforma_", "agresor_", "accion_"))]
    yuc[binarias] = yuc[binarias].astype("Int64")
    assert not yuc.duplicated(["anio", "id_persona"]).any(), "id_persona repetido"
    return yuc


def celda(p: float, ee: float, n: int) -> str:
    if np.isnan(p):
        return "—"
    return f"{p * 100:.1f} ± {1.96 * ee * 100:.1f}" + (" *" if n < 100 else "")


def tabla(df, var, por=None, dominio=None, pool=False, etiqueta=None) -> pd.DataFrame:
    """Proporción (%) ± IC 95 % por año. `por` desglosa; `pool` agrega la columna 2019–2025."""
    filas = {}
    for nv in (ORDEN[por] if por else [etiqueta or var]):
        fila = {}
        for anio in list(ANIOS) + ([TODOS] if pool else []):
            d = df if anio == TODOS else df[df["anio"] == anio]
            m = np.ones(len(d), bool) if dominio is None else dominio(d)
            if por:
                m = m & (d[por] == nv).to_numpy(dtype=bool)
            fila[str(anio)] = celda(*proporcion(d, var, m))
        filas[nv] = fila
    return pd.DataFrame.from_dict(filas, orient="index")


def main() -> None:
    datos = {a: leer(a) for a in ANIOS}
    prev = prevalencia_estatal(datos)
    prev.to_csv(CLEAN / "mociba_prevalencia_estatal_2019_2025.csv", index=False, encoding="utf-8")
    yuc = yucatan_armonizado(datos)
    yuc.to_csv(CLEAN / "mociba_2019_2025_yucatan.csv", index=False, encoding="utf-8")

    # --- Documento de exploración --------------------------------------------------------
    def texto(r, suf):
        t = f"{r[f'prevalencia{suf}']:.1f} [{r[f'ic95_inf{suf}']:.1f}, {r[f'ic95_sup{suf}']:.1f}]"
        return t + (f" · lugar {r[f'lugar{suf}']}" if r.cve_ent == YUC else "")

    serie = prev[prev["cve_ent"].isin(["00", YUC])].copy()
    partes = []
    for suf, nom in [("_comparable", "comparable (10 situaciones)"), ("", "oficial")]:
        serie["t"] = serie.apply(lambda r: texto(r, suf), axis=1)
        s = serie.pivot(index="anio", columns="cve_ent", values="t")
        s.columns = [f"Nacional, {nom}", f"Yucatán, {nom}"]
        partes.append(s)
    s = pd.concat(partes, axis=1)
    s.insert(0, "n Yucatán", yuc.groupby("anio").size())

    # Los siete años juntos, por entidad (indicador comparable)
    mini = pd.concat([d[["anio", "cve_ent", "factor", "upm_dis", "est_dis",
                         "ciberacoso_comparable"]] for d in datos.values()], ignore_index=True)
    mini["estrato_pool"] = mini["anio"].astype(str) + "-" + mini["est_dis"]
    pn = proporcion(mini, "ciberacoso_comparable")
    py = proporcion(mini, "ciberacoso_comparable", mini["cve_ent"] == YUC)
    junto = pd.Series({e: proporcion(mini, "ciberacoso_comparable", mini["cve_ent"] == e)[0]
                       for e in sorted(mini["cve_ent"].unique())}).sort_values(ascending=False)
    lugar_yuc = list(junto.index).index(YUC) + 1
    primeros = ", ".join(f"{ENTIDADES[e]} ({v * 100:.1f})" for e, v in junto.head(5).items())

    vict = lambda d: (d["ciberacoso_comparable"] == 1).to_numpy()
    vict_of = lambda d: (d["ciberacoso"] == 1).to_numpy()
    md = ["# Exploración inicial del MOCIBA 2019–2025 (generado por `data/limpieza/mociba_serie.py`)",
          "",
          "Cifras en % con IC 95 % (± 1.96 EE, diseño muestral). `*` = menos de 100 casos en la",
          "muestra. `—` = no se preguntó ese año. Población: usuarios de internet de 12 años o más.",
          "No editar a mano.", "",
          "**Para comparar 2019–2025 se usa el indicador comparable**: al menos una de las 10",
          "situaciones que se preguntaron los siete años. La cifra oficial incluye 3 situaciones",
          "más desde 2021, así que no se puede comparar con 2019–2020. Salvo las secciones 7 y 9,",
          "todas las tablas usan el indicador comparable.", "",
          "## 1. Prevalencia de ciberacoso, Yucatán vs nacional", "",
          s.to_markdown(), "",
          "2019 tiene menos de la mitad de la muestra de los demás años: su intervalo es el doble de ancho.",
          "",
          f"Los siete años juntos (indicador comparable): Yucatán {celda(*py)}, nacional "
          f"{celda(*pn)}. En ese promedio Yucatán es el lugar {lugar_yuc} de 32; los primeros "
          f"cinco son {primeros}.",
          ""]
    for titulo, por in [("2. Prevalencia en Yucatán por sexo", "sexo"),
                        ("3. Prevalencia en Yucatán por grupo de edad", "grupo_edad"),
                        ("4. Prevalencia en Yucatán por escolaridad", "escolaridad"),
                        ("5. Prevalencia en Yucatán por tipo de localidad", "dominio"),
                        ("5b. Prevalencia en Yucatán por estrato sociodemográfico", "estrato")]:
        md += [f"## {titulo}", "",
               tabla(yuc, "ciberacoso_comparable", por, pool=True).to_markdown(), ""]
    md += ["La columna 2019–2025 junta los siete años (cada año pesa según su población).", ""]

    md += ["## 6. % de usuarios de internet en Yucatán que vivió cada situación", ""]
    md += [pd.concat([tabla(yuc, f"sit_{n}", etiqueta=n) for n in SITUACIONES]).to_markdown(), ""]
    md += ["## 7. Entre las víctimas en Yucatán: % que fue acosada por cada medio (solo 2021–2025)",
           "", "El medio se pregunta desde 2021. Víctimas según la definición oficial (13 situaciones).",
           ""]
    t = pd.concat([tabla(yuc, f"medio_{n}", dominio=vict_of, etiqueta=n) for n in MEDIOS.values()])
    md += [t.drop(columns=["2019", "2020"]).to_markdown(), ""]
    md += ["## 7b. Entre las víctimas en Yucatán: % por plataforma, por año (solo 2021–2025)", ""]
    t = pd.concat([tabla(yuc, f"plataforma_{n}", dominio=vict_of, etiqueta=n) for n in PLATAFORMAS])
    md += [t.drop(columns=["2019", "2020"]).to_markdown(), ""]

    # Plataforma por grupo: 2021–2025 juntos (un año solo tiene muy pocas víctimas por grupo)
    v21 = yuc[(yuc["anio"] >= 2021)].reset_index(drop=True)
    md += ["## 7c. Entre las víctimas en Yucatán: % por plataforma según grupo, 2021–2025 juntos", "",
           "Un año solo tiene entre 260 y 400 víctimas en la muestra; por eso se juntan los cinco "
           "años. `*` = menos de 100 víctimas en el grupo.", ""]
    for por in ["grupo_edad", "sexo", "escolaridad", "dominio"]:
        filas = {}
        for nv in ORDEN[por]:
            m = (v21["ciberacoso"] == 1) & (v21[por] == nv)
            filas[nv] = {pl: celda(*proporcion(v21, f"plataforma_{pl}", m)) for pl in PLATAFORMAS}
            filas[nv]["víctimas en la muestra"] = int(m.sum())
        md += [pd.DataFrame.from_dict(filas, orient="index").to_markdown(), ""]

    md += ["## 8. Entre las víctimas en Yucatán: quién acosó y qué hicieron", "",
           "En 2019 solo se registraba una persona acosadora por situación (desde 2020, hasta tres),",
           "y 2019–2020 no tenían la opción \"pareja actual\".", ""]
    cols = ["agresor_desconocido", "agresor_pareja_o_ex", "agresor_familia_amigo_companero"] + \
        [f"accion_{n}" for n in ACCIONES_LISTA]
    md += [pd.concat([tabla(yuc, c, dominio=vict) for c in cols]).to_markdown(), ""]

    # Medios: Yucatán vs nacional 2025
    d25 = datos[2025]
    p11 = [c for c in d25.columns if re.fullmatch(r"p11_\d\d_\d", c)]
    filas = []
    for cod, nom in MEDIOS.items():
        d25["_m"] = (d25[p11] == cod).any(axis=1).astype(int)
        pn, en, nn = proporcion(d25, "_m", d25["ciberacoso"] == 1)
        py, ey, ny = proporcion(d25, "_m", (d25["ciberacoso"] == 1) & (d25["cve_ent"] == YUC))
        filas.append({"medio": nom, "Nacional 2025": celda(pn, en, nn),
                      "Yucatán 2025": celda(py, ey, ny)})
    md += ["## 9. Medios entre víctimas: Yucatán vs nacional, 2025", "",
           pd.DataFrame(filas).set_index("medio").to_markdown(), ""]
    DOC.write_text("\n".join(md), encoding="utf-8")

    print(s.to_string())
    print(f"Yucatán armonizado: {len(yuc)} personas en {yuc['anio'].nunique()} años")


if __name__ == "__main__":
    main()
