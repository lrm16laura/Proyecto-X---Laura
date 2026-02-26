import streamlit as st
import pandas as pd
import numpy as np
import os
import math
from datetime import datetime, timedelta

# Configuración de página
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ESTILOS CSS PERSONALIZADOS
# ==========================================
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    h1 { color: #1f77b4; text-align: center; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: .3rem; }
    .section-container {
        background-color: #f8f9fa; padding: 1rem;
        border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 1rem;
    }
    .footer { text-align: center; color:#7f8c8d; font-size:13px; margin-top:2rem;
              padding-top:1rem; border-top:1px solid #ccc; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# UTILIDADES
# ==========================================
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def guardar_archivo(archivo, nombre):
    if archivo is None: return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre}_{ts}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta

# ==========================================
# REPARTO PROPORCIONAL (NUEVO 🔥)
# ==========================================
def repartir_porcentaje(df_semana, pct_dg, dg_code, mch_code):
    """
    Reparte proporcionalmente ENTRE HORAS:
    - pct_dg% de las horas totales irán a DG
    - el resto a MCH
    """
    if pct_dg == 0:
        df_semana["Centro"] = mch_code
        return df_semana

    if pct_dg == 100:
        df_semana["Centro"] = dg_code
        return df_semana

    # Ordenamos por horas descendente para asignar más grandes primero
    df_semana = df_semana.sort_values("Horas", ascending=False)

    total_h = df_semana["Horas"].sum()
    objetivo_dg = total_h * (pct_dg / 100)

    acumulado = 0
    centros = []

    for _, row in df_semana.iterrows():
        if acumulado < objetivo_dg:
            centros.append(dg_code)
            acumulado += row["Horas"]
        else:
            centros.append(mch_code)

    df_semana["Centro"] = centros
    return df_semana

# ==========================================
#   LÓGICA PRINCIPAL (MODO C)
# ==========================================
def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes):

    def to_float(v):
        if pd.isna(v):
            raise ValueError("Campo numérico vacío en Excel")
        if isinstance(v,str):
            v = v.replace(",",".").strip()
        return float(v)

    # Detectar centros
    centros = [str(c) for c in df_cap["Centro"].astype(str).unique()]
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184") and c!=DG),
               centros[-1] if len(centros)>1 else centros[0])
    C1, C2 = DG, MCH

    # Preparar demanda
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # Merge materiales + clientes
    df = df_dem.merge(df_mat,on=["Material","Unidad"],how="left")
    df = df.merge(df_cli,on="Cliente",how="left")

    # Columnas reales
    COL_DIST_DG  = "Distáncia a DG"
    COL_DIST_MCH = "Distáncia a MCH"
    COL_COST_DG  = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    COL_CU_DG    = "Coste unitario DG"
    COL_CU_MCH   = "Coste unitario MCH"

    # Decidir centro por coste
    def decidir_centro(r):
        if str(r.get("Exclusico DG","")).upper()=="X": return C1
        if str(r.get("Exclusivo MCH","")).upper()=="X": return C2

        d1 = to_float(r[COL_DIST_DG])
        d2 = to_float(r[COL_DIST_MCH])
        p1 = to_float(r[COL_COST_DG])
        p2 = to_float(r[COL_COST_MCH])
        cu1 = to_float(r[COL_CU_DG])
        cu2 = to_float(r[COL_CU_MCH])
        q   = to_float(r["Cantidad"])

        c1 = d1*p1 + q*cu1
        c2 = d2*p2 + q*cu2

        if c1 < c2: return C1
        if c2 < c1: return C2

        rng=np.random.RandomState(r.name)
        return C1 if rng.rand() < ajustes.get(r["Semana_Label"],50)/100 else C2

    df["Centro_Final"] = df.apply(decidir_centro,axis=1)

    # Agrupar por día
    df_g = df.groupby(
        ["Material","Unidad","Centro_Final","Fecha de necesidad","Semana_Label"]
    ).agg({
        "Cantidad":"sum",
        "Tamaño lote mínimo":"first",
        "Tamaño lote máximo":"first",
        "Tiempo fabricación unidad DG":"first",
        "Tiempo fabricación unidad MCH":"first"
    }).reset_index()

    # ============================
    # CAPACIDAD desde Excel
    # ============================
    horas_col = next((c for c in df_cap.columns if "hora" in c.lower() or "capacidad" in c.lower()),None)

    if horas_col:
        base = {}
        for centro in df_cap["Centro"].astype(str).unique():
            vals = pd.to_numeric(df_cap.loc[df_cap["Centro"].astype(str)==centro,horas_col],
                                 errors="coerce")
            cap = vals.max()
            if pd.isna(cap): cap=0
            base[str(centro)] = float(cap)
    else:
        base={C1:float("inf"),C2:float("inf")}

    capacidad_restante={}

    def get_cap(centro,fecha):
        clave=(str(centro),fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave]=base[str(centro)]
        return capacidad_restante[clave]

    def consume(centro,fecha,hrs):
        capacidad_restante[(str(centro),fecha)] = get_cap(centro,fecha)-hrs

    # ============================
    #   MODO C: producir lo que cabe
    # ============================
    resultado=[]
    cont=1
    MAX_DIAS=365

    for _,fila in df_g.iterrows():

        fecha = pd.to_datetime(fila["Fecha de necesidad"]).normalize()
        semana = fila["Semana_Label"]
        pref = fila["Centro_Final"]

        total = max(to_float(fila["Cantidad"]), to_float(fila["Tamaño lote mínimo"]))
        lotemax = max(1,to_float(fila["Tamaño lote máximo"]))

        t_dg = to_float(fila["Tiempo fabricación unidad DG"])
        t_mch= to_float(fila["Tiempo fabricación unidad MCH"])

        def horas(centro,q):
            return q*(t_dg if centro==C1 else t_mch)

        def qcap(centro,cap):
            tu = (t_dg if centro==C1 else t_mch)
            return cap/tu if tu>0 else 0

        # trocear
        resto=total
        lotes=[]
        while resto>0:
            q=min(resto,lotemax)
            lotes.append(round(q,2))
            resto=round(resto-q,6)

        # procesar lotes
        for lote in lotes:
            pendiente=lote
            dias=0

            if base.get(str(pref),0)==0:
                h=horas(pref,pendiente)
                resultado.append({
                    "Nº de propuesta":cont,"Material":fila["Material"],
                    "Centro":pref,"Clase de orden":"NORM",
                    "Cantidad a fabricar":round(pendiente,2),
                    "Unidad":fila["Unidad"],
                    "Fecha de fabricación":fecha.strftime("%d.%m.%Y"),
                    "Semana":semana,"Horas":h
                })
                cont+=1
                continue

            while pendiente>0:

                caph=get_cap(pref,fecha)
                hnec=horas(pref,pendiente)

                if caph>=hnec:
                    consume(pref,fecha,hnec)
                    resultado.append({
                        "Nº de propuesta":cont,"Material":fila["Material"],
                        "Centro":pref,"Clase de orden":"NORM",
                        "Cantidad a fabricar":round(pendiente,2),
                        "Unidad":fila["Unidad"],
                        "Fecha de fabricación":fecha.strftime("%d.%m.%Y"),
                        "Semana":semana,"Horas":hnec
                    })
                    cont+=1
                    pendiente=0
                    break

                # producir parte hoy
                qpos=qcap(pref,caph)
                if qpos>0:
                    hprod=horas(pref,qpos)
                    consume(pref,fecha,hprod)
                    resultado.append({
                        "Nº de propuesta":cont,"Material":fila["Material"],
                        "Centro":pref,"Clase de orden":"NORM",
                        "Cantidad a fabricar":round(qpos,2),
                        "Unidad":fila["Unidad"],
                        "Fecha de fabricación":fecha.strftime("%d.%m.%Y"),
                        "Semana":semana,"Horas":hprod
                    })
                    cont+=1
                    pendiente=round(pendiente-qpos,6)
                    if get_cap(pref,fecha)>0:
                        continue

                if pendiente<=0:
                    break

                if dias>=MAX_DIAS:
                    hpend=horas(pref,pendiente)
                    resultado.append({
                        "Nº de propuesta":cont,"Material":fila["Material"],
                        "Centro":pref,"Clase de orden":"NORM",
                        "Cantidad a fabricar":round(pendiente,2),
                        "Unidad":fila["Unidad"],
                        "Fecha de fabricación":fecha.strftime("%d.%m.%Y"),
                        "Semana":semana,"Horas":hpend
                    })
                    cont+=1
                    pendiente=0
                    break

                fecha=(fecha+timedelta(days=1)).normalize()
                semana=fecha.strftime("%Y-W%U")
                dias+=1

    return pd.DataFrame(resultado)

# ==========================================
#         INTERFAZ
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel y ejecuta el cálculo en Modo C.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos","⚙️ Ejecución"])

df_cap=df_mat=df_cli=df_dem=None

# ------------------------------------------
# TAB 1: Carga
# ------------------------------------------
with tab1:

    st.subheader("Carga de Datos")

    col1,col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-container">',unsafe_allow_html=True)
        st.markdown("### Capacidad")
        f1 = st.file_uploader("Subir Capacidad",type=["xlsx"],key="cap")
        if f1:
            df_cap=pd.read_excel(f1)
            guardar_archivo(f1,"capacidad")
            st.success("✔ Cargado")
            st.dataframe(df_cap)
        st.markdown("</div>",unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">',unsafe_allow_html=True)
        st.markdown("### Materiales")
        f2 = st.file_uploader("Subir Materiales",type=["xlsx"],key="mat")
        if f2:
            df_mat=pd.read_excel(f2)
            guardar_archivo(f2,"materiales")
            st.success("✔ Cargado")
            st.dataframe(df_mat)
        st.markdown("</div>",unsafe_allow_html=True)

    col3,col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-container">',unsafe_allow_html=True)
        st.markdown("### Clientes")
        f3 = st.file_uploader("Subir Clientes",type=["xlsx"],key="cli")
        if f3:
            df_cli=pd.read_excel(f3)
            guardar_archivo(f3,"clientes")
            st.success("✔ Cargado")
            st.dataframe(df_cli)
        st.markdown("</div>",unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">',unsafe_allow_html=True)
        st.markdown("### Demanda")
        f4 = st.file_uploader("Subir Demanda",type=["xlsx"],key="dem")
        if f4:
            df_dem=pd.read_excel(f4)
            guardar_archivo(f4,"demanda")
            st.success("✔ Cargado")
            st.dataframe(df_dem)
        st.markdown("</div>",unsafe_allow_html=True)

# ------------------------------------------
# TAB 2: Ejecución
# ------------------------------------------
with tab2:

    if any(x is None for x in [df_cap,df_mat,df_cli,df_dem]):
        st.warning("⚠️ Carga los 4 archivos")
        st.stop()

    for d in [df_cap,df_mat,df_cli,df_dem]:
        d.columns=d.columns.str.strip()

    centros=list(df_cap["Centro"].astype(str).unique())
    df_dem["Semana_Label"]=pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
    semanas=sorted(df_dem["Semana_Label"].unique())

    st.subheader("⚙️ Asignación por semana (0% = MCH / 100% = DG / resto = repartido proporcional)")
    ajustes={s: st.slider(s,0,100,50) for s in semanas}

    if st.button("🚀 Ejecutar cálculo",use_container_width=True):

        with st.spinner("Procesando..."):
            df_res = procesar_logica_estable(df_dem,df_mat,df_cli,df_cap,ajustes)

        # -----------------------------------------------
        # 🔧 REASIGNACIÓN PROPORCIONAL DE CENTRO POR SEMANA
        # -----------------------------------------------
        DG = next((c for c in centros if c.endswith("833")), centros[0])
        MCH = next((c for c in centros if c.endswith("184") and c!=DG),
                   centros[1] if len(centros)>1 else centros[0])

        # Recuperar tiempos para recalcular horas
        tiempos=df_mat[["Material","Unidad",
                        "Tiempo fabricación unidad DG",
                        "Tiempo fabricación unidad MCH"]]
        df_tmp=df_res.merge(tiempos,on=["Material","Unidad"],how="left")

        # Horas iniciales antes de repartir
        df_res["Horas"]=np.where(
            df_res["Centro"].astype(str)==str(DG),
            df_res["Cantidad a fabricar"]*df_tmp["Tiempo fabricación unidad DG"],
            df_res["Cantidad a fabricar"]*df_tmp["Tiempo fabricación unidad MCH"]
        )

        df_final=[]

        for sem,pct in ajustes.items():
            df_sem=df_res[df_res["Semana"]==sem].copy()
            df_sem=repartir_porcentaje(df_sem,pct,DG,MCH)
            df_final.append(df_sem)

        df_res=pd.concat(df_final,ignore_index=True)

        # Recalcular horas después del reparto
        df_tmp=df_res.merge(tiempos,on=["Material","Unidad"],how="left")
        df_res["Horas"]=np.where(
            df_res["Centro"].astype(str)==str(DG),
            df_res["Cantidad a fabricar"]*df_tmp["Tiempo fabricación unidad DG"],
            df_res["Cantidad a fabricar"]*df_tmp["Tiempo fabricación unidad MCH"]
        )

        st.success("✔ Cálculo completado")

        # Mostrar tabla
        st.dataframe(df_res.drop(columns=["Horas"],errors="ignore"),use_container_width=True)

        # Gráficos arreglados (ahora Horas existe)
        st.subheader("📊 Distribución de carga horaria")
        carga_plot=df_res.groupby(["Semana","Centro"])["Horas"].sum().unstack().fillna(0)
        st.bar_chart(carga_plot)

        # Exportación
        out=os.path.join(UPLOAD_DIR,"Propuesta_Final.xlsx")
        df_res.drop(columns=["Semana","Horas"],errors="ignore").to_excel(out,index=False)

        with open(out,"rb") as f:
            st.download_button("📥 Descargar Excel",f,
                file_name=f"Propuesta_Fabricacion_"+datetime.now().strftime("%Y%m%d")+".xlsx")

# Footer
st.markdown("""
<div class="footer">
✨ Sistema de Cálculo de Fabricación — Modo C + Reparto proporcional  
</div>
""", unsafe_allow_html=True)
