"""Gráfica 2 (D-03, issue #19) · Plataforma por la que se vive el ciberacoso, según grupo de edad.

Pregunta (D-03): ¿qué grupos de edad concentran el ciberacoso en Yucatán de manera constante
entre 2019 y 2025, y en qué plataformas digitales lo vive cada grupo? Este script responde la
segunda mitad.

Lee: data/clean/mociba_2019_2025_yucatan.csv (carril Datos)
Deja en esta carpeta:
  - tabla.csv            % de víctimas por plataforma y grupo de edad, 2021–2025 juntos
  - diferencias.csv      contrastes entre grupos de edad, con IC 95 % de la diferencia
  - tabla_por_anio.csv   constancia: el mismo cruce por año, con 3 grupos de edad amplios
  - grafica.png
Deja en data/tableau/: B-edad_plataforma.csv

Población: víctimas de ciberacoso (ciberacoso == 1, definición oficial de 13 situaciones),
usuarias de internet de 12 años o más en Yucatán. Solo 2021–2025, porque el medio no se
preguntó en 2019–2020. Se juntan los cinco años: un año solo tiene entre 260 y 400 víctimas.

Plataformas (columnas plataforma_* del carril Datos):
  mensajería = WhatsApp, Messenger, Telegram, SMS
  redes sociales = Facebook, Instagram, TikTok, X, YouTube
  llamadas = celular o fijo
  correo = institucional o personal (casi nulo; va en la tabla, no en la gráfica)
Una víctima puede vivirlo por varias plataformas: los porcentajes NO suman 100.

Estimación: proporción ponderada con `factor`; error estándar por linealización (UPM `upm_dis`
dentro de estratos `estrato_pool` = año + est_dis, con reemplazo), estimando cada grupo como
dominio sobre la muestra completa 2021–2025. Es la misma función `proporcion` que usa el carril
Datos (data/limpieza/mociba_serie.py), así que las cifras cuadran con docs/exploracion_mociba.md
sección 7c. IC al 95 % (± 1.96 EE), igual que el resto del equipo.

Esto muestra asociación entre edad y plataforma, no que el agresor elija el canal según la edad.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "data" / "limpieza"))
from mociba_serie import proporcion  # noqa: E402  (función del carril Datos; no se modifica)

Z95 = 1.96
EDADES = ["12-17", "18-24", "25-34", "35-44", "45-59", "60+"]
PLATAFORMAS = {
    "mensajeria": "Mensajería",
    "redes_sociales": "Redes sociales",
    "llamadas": "Llamadas",
    "correo": "Correo",
}
POCAS = 100  # menos de 100 víctimas en la muestra = marcar

# ---------------------------------------------------------------- datos
df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", encoding="utf-8-sig",
                 dtype={"upm_dis": str, "est_dis": str, "estrato_pool": str})
d = df[df["anio"] >= 2021].reset_index(drop=True)
victima = (d["ciberacoso"] == 1).to_numpy()
assert d.loc[victima, [f"plataforma_{p}" for p in PLATAFORMAS]].notna().all().all(), \
    "hay víctimas 2021–2025 sin dato de plataforma"


def diferencia(df, var, dom_a, dom_b):
    """Diferencia de proporciones (a − b) entre dos dominios, con EE por linealización.

    Mismo estimador que `proporcion`, pero linealizando la diferencia para tomar en cuenta que
    los dos grupos comparten UPM y estratos.
    """
    z = df[var].astype(float).fillna(0).to_numpy()
    w = df["factor"].to_numpy(dtype=float)
    u = np.zeros(len(df))
    ps = []
    for signo, m in [(1, dom_a), (-1, dom_b)]:
        m = np.asarray(m, bool)
        W = (w * m).sum()
        p = (w * m * z).sum() / W
        ps.append(p)
        u += signo * w * m * (z - p) / W
    t = pd.DataFrame({"h": df["estrato_pool"].to_numpy(), "c": df["upm_dis"].to_numpy(), "u": u})
    tot = t.groupby(["h", "c"], sort=False)["u"].sum()
    g = tot.groupby(level="h", sort=False)
    k = g.transform("size").to_numpy(dtype=float)
    dif = (tot - g.transform("mean")).to_numpy()
    v = (np.where(k > 1, k / np.maximum(k - 1, 1), 0.0) * dif ** 2).sum()
    return ps[0] - ps[1], float(np.sqrt(v))


# ---------------------------------------------------------------- 1. tabla principal
filas = []
for edad in EDADES:
    m = victima & (d["grupo_edad"] == edad).to_numpy()
    n = int(m.sum())
    victimas_pob = d.loc[m, "factor"].sum() / 5  # promedio anual de víctimas expandidas
    for clave, nombre in PLATAFORMAS.items():
        p, ee, _ = proporcion(d, f"plataforma_{clave}", m)
        filas.append({
            "grupo_edad": edad, "plataforma": nombre,
            "porcentaje": round(100 * p, 1),
            "ic95_inf": round(100 * (p - Z95 * ee), 1),
            "ic95_sup": round(100 * (p + Z95 * ee), 1),
            "ee": round(100 * ee, 2),
            "cv": round(100 * ee / p, 1) if p > 0 else np.nan,
            "victimas_muestra": n,
            "victimas_promedio_anual": int(round(victimas_pob, -3)),
            "poca_muestra": n < POCAS,
        })
tabla = pd.DataFrame(filas)
tabla.to_csv(AQUI / "tabla.csv", index=False, encoding="utf-8")

# Plataforma principal de cada grupo (y si su ventaja sobre la segunda es clara)
princ = []
for edad in EDADES:
    t = tabla[(tabla["grupo_edad"] == edad) & (tabla["plataforma"] != "Correo")]
    t = t.sort_values("porcentaje", ascending=False)
    a, b = t.iloc[0], t.iloc[1]
    m = victima & (d["grupo_edad"] == edad).to_numpy()
    inv = {v: k for k, v in PLATAFORMAS.items()}
    # diferencia entre dos plataformas en el mismo grupo: variable = a − b, en el dominio m
    d["_dif"] = d[f"plataforma_{inv[a['plataforma']]}"] - d[f"plataforma_{inv[b['plataforma']]}"]
    p, ee, _ = proporcion(d, "_dif", m)
    princ.append({"grupo_edad": edad, "principal": a["plataforma"], "segunda": b["plataforma"],
                  "ventaja_pp": round(100 * p, 1),
                  "ic95_inf": round(100 * (p - Z95 * ee), 1),
                  "ic95_sup": round(100 * (p + Z95 * ee), 1),
                  "ventaja_clara": (p - Z95 * ee) > 0})
d = d.drop(columns="_dif")
princ = pd.DataFrame(princ)

# ---------------------------------------------------------------- 2. contrastes entre edades
# Se compara 12-17 (el grupo más joven) y 18-24 contra 45-59 (el mayor con muestra suficiente;
# 60+ tiene < 100 víctimas y no se usa como extremo).
contrastes = [
    ("llamadas", "45-59", "12-17"),
    ("redes_sociales", "18-24", "45-59"),
    ("redes_sociales", "25-34", "45-59"),
    ("mensajeria", "12-17", "25-34"),
    ("mensajeria", "12-17", "45-59"),
]
filas = []
for clave, a, b in contrastes:
    ma = victima & (d["grupo_edad"] == a).to_numpy()
    mb = victima & (d["grupo_edad"] == b).to_numpy()
    dif, ee = diferencia(d, f"plataforma_{clave}", ma, mb)
    filas.append({"plataforma": PLATAFORMAS[clave], "grupo_a": a, "grupo_b": b,
                  "diferencia_pp": round(100 * dif, 1),
                  "ic95_inf": round(100 * (dif - Z95 * ee), 1),
                  "ic95_sup": round(100 * (dif + Z95 * ee), 1),
                  "significativa_95": abs(dif) > Z95 * ee})
difs = pd.DataFrame(filas)
difs.to_csv(AQUI / "diferencias.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- 3. constancia por año
# Con 6 grupos un año solo no alcanza; con 3 grupos amplios cada celda tiene ~70–180 víctimas.
amplio = {"12-17": "12-24", "18-24": "12-24", "25-34": "25-44", "35-44": "25-44",
          "45-59": "45+", "60+": "45+"}
d["edad_amplia"] = d["grupo_edad"].map(amplio)
filas = []
for anio in range(2021, 2026):
    da = d[d["anio"] == anio].reset_index(drop=True)
    va = (da["ciberacoso"] == 1).to_numpy()
    for g in ["12-24", "25-44", "45+"]:
        m = va & (da["edad_amplia"] == g).to_numpy()
        for clave in ["mensajeria", "redes_sociales", "llamadas"]:
            p, ee, n = proporcion(da, f"plataforma_{clave}", m)
            filas.append({"anio": anio, "edad_amplia": g, "plataforma": PLATAFORMAS[clave],
                          "porcentaje": round(100 * p, 1),
                          "ic95_inf": round(100 * (p - Z95 * ee), 1),
                          "ic95_sup": round(100 * (p + Z95 * ee), 1),
                          "victimas_muestra": n, "poca_muestra": n < POCAS})
por_anio = pd.DataFrame(filas)
por_anio.to_csv(AQUI / "tabla_por_anio.csv", index=False, encoding="utf-8")

# En cuántos años las llamadas pesan más en 45+ que en 12-24 (y redes al revés)
piv = por_anio.pivot_table(index=["anio", "plataforma"], columns="edad_amplia",
                           values="porcentaje").reset_index()
constancia = {
    "llamadas: 45+ > 12-24": int((piv.loc[piv.plataforma == "Llamadas", "45+"]
                                  > piv.loc[piv.plataforma == "Llamadas", "12-24"]).sum()),
    "redes: 12-24 > 45+": int((piv.loc[piv.plataforma == "Redes sociales", "12-24"]
                               > piv.loc[piv.plataforma == "Redes sociales", "45+"]).sum()),
    "mensajería: 12-24 > 45+": int((piv.loc[piv.plataforma == "Mensajería", "12-24"]
                                    > piv.loc[piv.plataforma == "Mensajería", "45+"]).sum()),
}

# ---------------------------------------------------------------- 4. extracto para Tableau
tb = tabla.rename(columns={"grupo_edad": "grupo_de_edad", "porcentaje": "porcentaje_de_victimas",
                           "ic95_inf": "ic95_inferior", "ic95_sup": "ic95_superior",
                           "victimas_muestra": "victimas_en_la_muestra",
                           "poca_muestra": "menos_de_100_victimas"})
tb.insert(0, "periodo", "2021-2025")
tb["orden_edad"] = tb["grupo_de_edad"].map({e: i + 1 for i, e in enumerate(EDADES)})
tb["nota"] = ("% de las víctimas del grupo que lo vivió por esa plataforma; una víctima puede "
              "vivirlo por varias, no suman 100. Fuente: INEGI, MOCIBA 2021-2025.")
tb = tb[["periodo", "grupo_de_edad", "orden_edad", "plataforma", "porcentaje_de_victimas",
         "ic95_inferior", "ic95_superior", "cv", "victimas_en_la_muestra",
         "victimas_promedio_anual", "menos_de_100_victimas", "nota"]]
(RAIZ / "data/tableau").mkdir(exist_ok=True)
tb.to_csv(RAIZ / "data/tableau/B-edad_plataforma.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- 5. gráfica
# Líneas sobre el eje ordinal de edad: muestran cómo cambia el peso de cada plataforma con la
# edad. Paleta categórica de referencia (3 primeros espacios, validados en todos los pares).
COLOR = {"Mensajería": "#2a78d6", "Redes sociales": "#eb6834", "Llamadas": "#1baf7a"}
MARCA = {"Mensajería": "o", "Redes sociales": "s", "Llamadas": "^"}
DESPL = {"Mensajería": -0.12, "Redes sociales": 0.0, "Llamadas": 0.12}
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"

fig, ax = plt.subplots(figsize=(9, 5.6), dpi=150)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")
x = np.arange(len(EDADES))
for nombre in ["Mensajería", "Redes sociales", "Llamadas"]:
    t = tabla[tabla["plataforma"] == nombre].set_index("grupo_edad").loc[EDADES]
    xs = x + DESPL[nombre]
    ax.plot(xs[:-1], t["porcentaje"][:-1], color=COLOR[nombre], lw=2, zorder=3)
    ax.plot(xs[-2:], t["porcentaje"][-2:], color=COLOR[nombre], lw=2, ls=(0, (2, 2)), zorder=3)
    ax.vlines(xs, t["ic95_inf"], t["ic95_sup"], color=COLOR[nombre], lw=1.2, alpha=0.45, zorder=2)
    ax.scatter(xs, t["porcentaje"], s=46, marker=MARCA[nombre], color=COLOR[nombre],
               edgecolor="#fcfcfb", linewidth=1.5, zorder=4, label=nombre)
    ultimo = t["porcentaje"].iloc[-1]
    ax.annotate(nombre, (xs[-1], ultimo), xytext=(10, 0), textcoords="offset points",
                va="center", fontsize=10, color=TINTA)

for nombre, edad in [("Mensajería", "12-17"), ("Redes sociales", "18-24"), ("Llamadas", "45-59")]:
    v = tabla[(tabla.plataforma == nombre) & (tabla.grupo_edad == edad)]["porcentaje"].iloc[0]
    xi = EDADES.index(edad) + DESPL[nombre]
    ax.annotate(f"{v:.1f} %", (xi, v), xytext=(0, 9), textcoords="offset points",
                ha="center", fontsize=9, color=TINTA2)

etq = [f"{e}\n(n={tabla[tabla.grupo_edad == e].victimas_muestra.iloc[0]})" for e in EDADES]
etq[-1] = etq[-1].replace(")", ") *")
ax.set_xticks(x, etq, fontsize=9, color=TINTA2)
ax.set_xlim(-0.4, len(EDADES) - 0.4 + 0.9)
ax.set_ylim(0, 85)
ax.set_yticks(range(0, 81, 20), [f"{v} %" for v in range(0, 81, 20)], fontsize=9, color=TINTA2)
ax.yaxis.grid(True, color=REJILLA, lw=0.8)
ax.set_axisbelow(True)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(REJILLA)
ax.tick_params(length=0)
ax.set_xlabel("Grupo de edad (víctimas en la muestra)", fontsize=9, color=TINTA2)
ax.legend(loc="upper left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=9,
          labelcolor=TINTA2, handletextpad=0.3)

fig.suptitle("Con la edad, las redes sociales pierden peso y las llamadas lo ganan",
             x=0.06, ha="left", fontsize=13, fontweight="bold", color=TINTA, y=0.975)
ax.set_title("% de víctimas de cada grupo de edad que lo vivió por cada plataforma · Yucatán, "
             "2021–2025 juntos", loc="left", fontsize=9.5, color=TINTA2, pad=26)
fig.text(0.06, 0.015,
         "Fuente: INEGI, MOCIBA 2021–2025, usuarios de internet de 12 años o más que vivieron "
         "ciberacoso. Barras verticales: IC 95 %.\nUna víctima puede vivirlo por varias "
         "plataformas (no suman 100). * 60+: menos de 100 víctimas en la muestra (línea punteada), "
         "leer con cautela.\nMensajería = WhatsApp, Messenger, Telegram, SMS · Redes = Facebook, "
         "Instagram, TikTok, X, YouTube. Asociación, no causa.",
         fontsize=7.5, color=TINTA2, va="bottom")
fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.22)
fig.savefig(AQUI / "grafica.png", facecolor=fig.get_facecolor())

# ---------------------------------------------------------------- resumen en consola
pd.set_option("display.width", 140)
print("Víctimas 2021–2025 en la muestra:", int(victima.sum()))
print(tabla.pivot(index="grupo_edad", columns="plataforma", values="porcentaje").loc[EDADES])
print("\nPlataforma principal por grupo:\n", princ.to_string(index=False))
print("\nContrastes:\n", difs.to_string(index=False))
print("\nConstancia (años de 5):", constancia)
