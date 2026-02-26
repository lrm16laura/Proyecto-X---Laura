# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — FLUJO EN 2 FASES
#   1) Cálculo inicial (Modo C)
#   2) Reajustar y Re‑planificar por semana
# Visual: Único gráfico 0184 vs 0833
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
)

UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def guardar_archivo(archivo, nombre_seccion):
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = os.path.join(UPLOAD_DIR, f"{nombre_seccion}_{timestamp}.xlsx")
        with open(ruta, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta

def to_float_safe(v, default=0.0):
    if pd.isna(v): 
        return float(default)
    if isinstance(v, str):
        v = v.replace(",", ".").strip()
        if v == "":
            return float(default)
    try:
        return float(v)
    except:
        return float(default)

def norm_code(code):
    s = str(code).strip()
    if s.endswith(".0"): 
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits

# ------------------------------------------------------------
# 🔎 DETECCIÓN AUTOMÁTICA DE COLUMNA DE CLIENTE  (CORRECCIÓN)
# ------------------------------------------------------------
def detectar_columna_cliente(df):
    posibles = [
        "cliente", "customer", "client", 
        "id cliente", "codigo cliente", "cod cliente",
        "cliente id", "sap cliente"
    ]

    cols = {c: c.strip().lower() for c in df.columns}

    for original, low in cols.items():
        for buscado in posibles:
            if buscado == low or buscado in low:
                return original

    st.error("❌ No se encontró ninguna columna de cliente en el Excel.")
    st.stop()

# ------------------------------------------------------------
# LECTURA DE CAPACIDADES
# ------------------------------------------------------------
def leer_capacidades(df_cap):
    if "Centro" not in df_cap.columns:
        st.error("❌ Falta la columna 'Centro' en el Excel de capacidades.")
        st.stop()

    col_lower = {c: c.strip().lower() for c in df_cap.columns}
    cap_col = None
    for c, low in col_lower.items():
        if low == "capacidad horas" or ("capacidad" in low and "hora" in low):
            cap_col = c
            break

    if cap_col is None:
        st.error("❌ No se encuentra la columna 'Capacidad horas' en el archivo.")
        st.stop()

    capacidades = {}
    for _, r in df_cap.iterrows():
        c = norm_code(r["Centro"])
        capacidades[c] = to_float_safe(r[cap_col], 0)

    return capacidades

def detectar_centros_desde_capacidades(capacidades):
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH, keys

# ------------------------------------------------------------
# REPARTO POR SEMANA
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
    if pct_dg <= 0:
        df_semana["Centro"] = mch
        return df_semana
    if pct_dg >= 100:
        df_semana["Centro"] = dg
        return df_semana

    df_semana = df_semana.sort_values("Horas", ascending=False)
    total = df_semana["Horas"].sum()
    objetivo = total * (pct_dg / 100)

    acum = 0
    nuevo_centro = []
    for _, row in df_semana.iterrows():
        if acum < objetivo:
            nuevo_centro.append(dg)
            acum += row["Horas"]
        else:
            nuevo_centro.append(mch)

    df_semana["Centro"] = nuevo_centro
    return df_semana

# ------------------------------------------------------------
# MODO C — PLANIFICACIÓN
# ------------------------------------------------------------
def modo_C(df_agr, df_mat, capacidades, DG, MCH):
    tiempos = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo","Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material","Unidad"], how="left")

    capacidad_restante = {}

    def get_cap(centro, fecha):
        key = (centro, fecha)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(centro, 0)
        return capacidad_restante[key]

    def consume(centro, fecha, horas):
        capacidad_restante[(centro, fecha)] = get_cap(centro, fecha) - horas

    def horas_necesarias(centro, qty, row):
        tu = row["Tiempo fabricación unidad DG"] if centro == DG else row["Tiempo fabricación unidad MCH"]
        return qty * to_float_safe(tu)

    def cant_por_capacidad(centro, cap_horas, row):
        tu = row["Tiempo fabricación unidad DG"] if centro == DG else row["Tiempo fabricación unidad MCH"]
        tu = to_float_safe(tu)
        if tu == 0:
            return 0
        return cap_horas / tu

    out = []
    contador = 1

    for _, r in df.iterrows():
        centro = r["Centro"]
        fecha = pd.to_datetime(r["Fecha"]).normalize()
        semana = r["Semana"]

        total = max(
            to_float_safe(r["Cantidad"], 0),
            to_float_safe(r["Tamaño lote mínimo"], 0)
        )
        lote_max = to_float_safe(r["Tamaño lote máximo"], 1)

        # === DIVIDO EN LOTES ===
        cantidades = []
        pendiente = total
        while pendiente > 0:
            q = min(pendiente, lote_max)
            cantidades.append(round(q, 2))
            pendiente -= q

        for q in cantidades:
            p = q
            while p > 0:
                cap = get_cap(centro, fecha)
                hnec = horas_necesarias(centro, p, r)

                if cap >= hnec:
                    consume(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(p,2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    contador += 1
                    p = 0

                else:
                    qpos = cant_por_capacidad(centro, cap, r)
                    if qpos <= 0:
                        fecha = fecha + timedelta(days=1)
                        semana = fecha.strftime("%Y-W%U")
                        continue

                    hprod = horas_necesarias(centro, qpos, r)
                    consume(centro, fecha, hprod)

                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(qpos,2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    contador += 1
                    p -= qpos

    return pd.DataFrame(out)

# ------------------------------------------------------------
# EJECUCIÓN INICIAL
# ------------------------------------------------------------
def ejecutar_modoC_base(df_cap, df_mat, df_cli, df_dem):
    capacidades = leer_capacidades(df_cap)
    DG, MCH, _ = detectar_centros_desde_capacidades(capacidades)

    # Detectar columnas de cliente (CORREGIDO)
    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)

    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    df = df_dem.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")
    df = df.merge(df_mat, on=["Material","Unidad"], how="left")

    # Decisión coste
    COL_DG_COST = next((c for c in df.columns if "dg" in c.lower() and "cost" in c.lower()), None)
    COL_MCH_COST = next((c for c in df.columns if "mch" in c.lower() and "cost" in c.lower()), None)

    def decidir(r):
        c1 = to_float_safe(r.get(COL_DG_COST,0))
        c2 = to_float_safe(r.get(COL_MCH_COST,0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(decidir, axis=1)

    g = df.groupby(
        ["Material","Unidad","Centro_Base","Fecha de necesidad","Semana_Label"]
    ).agg({"Cantidad":"sum","Tamaño lote mínimo":"first","Tamaño lote máximo":"first"}).reset_index()

    g = g.rename(columns={
        "Centro_Base":"Centro",
        "Fecha de necesidad":"Fecha",
        "Semana_Label":"Semana"
    })

    g["Centro"] = g["Centro"].apply(norm_code)

    df_c = modo_C(
        g.rename(columns={"Cantidad":"Cantidad"})[
            ["Material","Unidad","Centro","Cantidad","Fecha","Semana","Tamaño lote mínimo","Tamaño lote máximo"]
        ],
        df_mat, capacidades, DG, MCH
    )

    # Calcular horas
    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]]
    df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")

    df_c["Horas"] = np.where(
        df_c["Centro"] == DG,
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
    )

    return df_c, capacidades, DG, MCH

# ------------------------------------------------------------
# REPLANIFICACIÓN
# ------------------------------------------------------------
def replanificar(df_base, df_mat, capacidades, DG, MCH, ajustes):
    df_rep = []
    for semana in df_base["Semana"].unique():
        df_sem = df_base[df_base["Semana"] == semana].copy()
        pct = ajustes.get(semana, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG, MCH)
        df_rep.append(df_sem)

    df_adj = pd.concat(df_rep, ignore_index=True)

    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana"]
    ]

    df_final = modo_C(df_adj_pre, df_mat, capacidades, DG, MCH)

    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]]
    df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")

    df_final["Horas"] = np.where(
        df_final["Centro"] == DG,
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
    )

    return df_final

# ------------------------------------------------------------
# INTERFAZ
# ------------------------------------------------------------
st.title("📊 Sistema de Cálculo de Fabricación — Versión Corregida")

tab1, tab2 = st.tabs(["📥 Carga", "⚙️ Cálculo y Reajuste"])

with tab1:
    st.header("Sube los archivos Excel")

    f1 = st.file_uploader("Capacidad", type=["xlsx"])
    f2 = st.file_uploader("Materiales", type=["xlsx"])
    f3 = st.file_uploader("Clientes", type=["xlsx"])
    f4 = st.file_uploader("Demanda", type=["xlsx"])

    if f1 and f2 and f3 and f4:
        st.session_state.df_cap = pd.read_excel(f1)
        st.session_state.df_mat = pd.read_excel(f2)
        st.session_state.df_cli = pd.read_excel(f3)
        st.session_state.df_dem = pd.read_excel(f4)

        st.success("Archivos cargados correctamente ✔")

with tab2:

    if not all(k in st.session_state for k in ["df_cap","df_mat","df_cli","df_dem"]):
        st.warning("Sube todos los archivos en la pestaña anterior.")
        st.stop()

    if st.button("🚀 Ejecutar cálculo inicial"):
        df_base, capacidades, DG, MCH = ejecutar_modoC_base(
            st.session_state.df_cap,
            st.session_state.df_mat,
            st.session_state.df_cli,
            st.session_state.df_dem
        )

        st.session_state.df_base = df_base
        st.session_state.capacidades = capacidades
        st.session_state.DG = DG
        st.session_state.MCH = MCH

        st.success("Cálculo inicial completado ✔")

    if "df_base" in st.session_state:
        df_base = st.session_state.df_base
        DG = st.session_state.DG
        MCH = st.session_state.MCH

        st.subheader("📊 Producción inicial por centro (Horas)")

        horas = df_base.groupby("Centro")["Horas"].sum()

        resumen = pd.DataFrame({
            "Horas": [
                horas.get(MCH, 0),
                horas.get(DG, 0)
            ]
        }, index=[MCH, DG])

        st.bar_chart(resumen)

        st.subheader("🔁 ¿Reajustar por semana?")

        semanas = sorted(df_base["Semana"].unique())
        ajustes = {}

        cols = st.columns(4)
        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(sem, 0, 100, 50)

        if st.button("Aplicar y Re‑planificar"):
            df_final = replanificar(
                df_base,
                st.session_state.df_mat,
                st.session_state.capacidades,
                DG,
                MCH,
                ajustes
            )
            st.session_state.df_final = df_final
            st.success("Re‑planificación completada ✔")

    if "df_final" in st.session_state:
        df_final = st.session_state.df_final

        st.subheader("📊 Producción FINAL por centro (Horas)")
        horas2 = df_final.groupby("Centro")["Horas"].sum()

        resumen2 = pd.DataFrame({
            "Horas": [
                horas2.get(st.session_state.MCH, 0),
                horas2.get(st.session_state.DG, 0)
            ]
        }, index=[st.session_state.MCH, st.session_state.DG])

        st.bar_chart(resumen2)

        st.subheader("📋 Tabla final")
        st.dataframe(df_final)

# Footer
st.markdown("---")
st.markdown("✔ App corregida | ✔ Detección cliente | ✔ Gráfico único | ✔ Flujo 2 fases")
