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
# ESTILOS CSS PERSONALIZADOS (Programa 1 + 2)
# ==========================================
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    h1 { color: #1f77b4; text-align: center; font-size: 2.5rem; margin-bottom: 1rem; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 0.5rem; }
    .section-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    .footer {
        text-align: center; color: #7f8c8d; font-size: 0.9rem; margin-top: 2rem;
        padding-top: 1rem; border-top: 1px solid #ecf0f1;
    }
    .stButton > button { width: 100%; font-weight: bold; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Crear carpeta para guardar archivos si no existe
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ==========================================
# FUNCIONES AUXILIARES Y LÓGICA (Programa 2)
# ==========================================

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo en la carpeta local (del Programa 1)"""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None

def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):
    """
    - Mantiene tu interfaz y estructura.
    - Corrige el cálculo de coste usando TUS columnas reales.
    - Capacidad DIARIA.
    - Evita OutOfBoundsDatetime con dos guardarraíles:
        * Si el centro preferido tiene capacidad base diaria 0 -> marca sin capacidad y no avanza días.
        * Límite de avance de días (365) -> si lo alcanza, marca sin capacidad y sale.
    - NO hay precio/km por defecto (si falta en Excel, lanza error).
    """

    # --- Helper robusto para números con coma, sin fallback silencioso ---
    def to_float(v):
        if pd.isna(v):
            raise ValueError("⚠️ Campo numérico crítico vacío en el Excel.")
        if isinstance(v, str):
            v = v.strip().replace(",", ".")
        return float(v)

    # --- Mapeo fiable de DG/MCH según df_cap ---
    centros_detectados = [str(c).strip() for c in df_cap['Centro'].astype(str).unique()]
    DG_CODE = next((c for c in centros_detectados if c.endswith('833')), (centros_detectados[0] if centros_detectados else '833'))
    MCH_CODE = next((c for c in centros_detectados if c.endswith('184') and c != DG_CODE),
                    (centros_detectados[1] if len(centros_detectados) > 1 else DG_CODE))
    C1, C2 = DG_CODE, MCH_CODE  # Semántica original: C1=DG, C2=MCH

    # --- Fechas y semanas en demanda ---
    df_dem['Fecha_DT'] = pd.to_datetime(df_dem['Fecha de necesidad'])
    df_dem['Semana_Label'] = df_dem['Fecha_DT'].dt.strftime('%Y-W%U')

    # --- Merge con maestro de materiales y clientes ---
    df = df_dem.merge(df_mat, on=['Material', 'Unidad'], how='left')
    df = df.merge(df_cli, on='Cliente', how='left')

    # --- Columnas EXACTAS de tus ficheros ---
    # Clientes:
    COL_DIST_DG  = "Distáncia a DG"
    COL_DIST_MCH = "Distáncia a MCH"
    COL_COST_DG  = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    # Materiales:
    COL_CF_DG    = "Coste unitario DG"
    COL_CF_MCH   = "Coste unitario MCH"

    # --- Decidir centro por coste total ---
    def decidir_centro(r):
        # Exclusividades (según tu Excel)
        if str(r.get('Exclusico DG', '')).strip().upper() == 'X':
            return C1
        if str(r.get('Exclusivo MCH', '')).strip().upper() == 'X':
            return C2

        dist_dg  = to_float(r[COL_DIST_DG])
        dist_mch = to_float(r[COL_DIST_MCH])
        pkm_dg   = to_float(r[COL_COST_DG])
        pkm_mch  = to_float(r[COL_COST_MCH])
        cf_dg    = to_float(r[COL_CF_DG])
        cf_mch   = to_float(r[COL_CF_MCH])
        cantidad = to_float(r['Cantidad'])

        coste_dg  = dist_dg * pkm_dg   + cantidad * cf_dg
        coste_mch = dist_mch * pkm_mch + cantidad * cf_mch

        if coste_dg < coste_mch:
            return C1
        elif coste_mch < coste_dg:
            return C2
        else:
            rng = np.random.RandomState(r.name)
            umbral = ajustes_semanales.get(r['Semana_Label'], 50) / 100
            return C1 if rng.rand() < umbral else C2

    df['Centro_Final'] = df.apply(decidir_centro, axis=1)

    # --- Agrupación por día (capacidad diaria) ---
    df_agrupado = df.groupby(
        ['Material', 'Unidad', 'Centro_Final', 'Fecha de necesidad', 'Semana_Label']
    ).agg({
        'Cantidad': 'sum',
        'Tamaño lote mínimo': 'first',
        'Tamaño lote máximo': 'first',
        'Tiempo fabricación unidad DG': 'first',
        'Tiempo fabricación unidad MCH': 'first'
    }).reset_index()

    # ============
    # CAPACIDAD DIARIA + guardarraíles
    # ============
    horas_col = None
    for c in df_cap.columns:
        if ('hora' in str(c).lower()) or ('capacidad' in str(c).lower()):
            horas_col = c
            break

    if horas_col:
        base_cap_por_centro = df_cap.groupby('Centro')[horas_col].sum().to_dict()
    else:
        base_cap_por_centro = {C1: float('inf'), C2: float('inf')}

    # Asegurar claves con 0.0 (por si algún centro no aparece)
    for k in [C1, C2]:
        if k not in base_cap_por_centro:
            base_cap_por_centro[k] = 0.0

    # Capacidad restante por (centro, fecha) inicializada bajo demanda
    capacidad_restante = {}
    def get_cap(centro, fecha_norm):
        clave = (str(centro), fecha_norm)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = float(base_cap_por_centro.get(str(centro), 0.0))
        return capacidad_restante[clave]
    def consume_cap(centro, fecha_norm, horas):
        clave = (str(centro), fecha_norm)
        capacidad_restante[clave] = get_cap(centro, fecha_norm) - horas

    # ============================
    # Generación de órdenes/lotes (SIN CAMBIAR tu estructura de salida)
    # ============================
    resultado_lotes = []
    cont = 1

    # Guardarraíl 2: límite de días para mover (evita OutOfBoundsDatetime)
    MAX_DIAS_ADELANTE = 365  # 1 año

    for _, fila in df_agrupado.iterrows():
        fecha_actual = pd.to_datetime(fila['Fecha de necesidad']).normalize()
        semana = fila['Semana_Label']
        pref = str(fila['Centro_Final']).strip()

        cant_total = max(to_float(fila['Cantidad']), to_float(fila['Tamaño lote mínimo']))
        tam_lote_max = max(1.0, to_float(fila['Tamaño lote máximo']))

        tf_dg  = to_float(fila['Tiempo fabricación unidad DG'])
        tf_mch = to_float(fila['Tiempo fabricación unidad MCH'])

        def horas_lote(centro, cantidad):
            return cantidad * (tf_dg if str(centro) == str(C1) else tf_mch)

        def cantidad_posible(centro, cap_horas):
            tu = (tf_dg if str(centro) == str(C1) else tf_mch)
            if tu <= 0: return 0.0
            return cap_horas / tu

        # Trocear por tamaño lote máximo
        restante_global = cant_total
        lotes = []
        while restante_global > 0:
            q = round(min(restante_global, tam_lote_max), 2)
            lotes.append(q)
            restante_global = round(restante_global - q, 6)

        for cant_lote in lotes:
            restante = cant_lote
            dias_movidos = 0

            # Guardarraíl 1: si la capacidad DIARIA BASE del centro es 0, no avanzamos días
            if float(base_cap_por_centro.get(pref, 0.0)) <= 0.0:
                h_total = horas_lote(pref, restante)
                resultado_lotes.append({
                    'Nº de propuesta': cont,
                    'Material': fila['Material'],
                    'Centro': pref,
                    'Clase de orden': 'NORM',
                    'Cantidad a fabricar': round(restante, 2),
                    'Unidad': fila['Unidad'],
                    'Fecha de fabricación': fecha_actual.strftime('%Y%m%d'),
                    'Semana': semana,
                    'Horas': h_total,
                    'Sin capacidad (informativo)': True
                })
                cont += 1
                continue

            while restante > 0:
                cap_hoy = get_cap(pref, fecha_actual)
                h_neces = horas_lote(pref, restante)

                if cap_hoy >= h_neces:
                    # Cabe entero hoy
                    consume_cap(pref, fecha_actual, h_neces)
                    resultado_lotes.append({
                        'Nº de propuesta': cont,
                        'Material': fila['Material'],
                        'Centro': pref,
                        'Clase de orden': 'NORM',
                        'Cantidad a fabricar': round(restante, 2),
                        'Unidad': fila['Unidad'],
                        'Fecha de fabricación': fecha_actual.strftime('%Y%m%d'),
                        'Semana': semana,
                        'Horas': h_neces,
                        'Sin capacidad (informativo)': False
                    })
                    cont += 1
                    restante = 0.0
                    break

                # Produce lo que quepa hoy
                q_pos = round(cantidad_posible(pref, cap_hoy), 2) if cap_hoy > 0 else 0.0
                if q_pos > 0:
                    h_prod = horas_lote(pref, q_pos)
                    consume_cap(pref, fecha_actual, h_prod)
                    resultado_lotes.append({
                        'Nº de propuesta': cont,
                        'Material': fila['Material'],
                        'Centro': pref,
                        'Clase de orden': 'NORM',
                        'Cantidad a fabricar': q_pos,
                        'Unidad': fila['Unidad'],
                        'Fecha de fabricación': fecha_actual.strftime('%Y%m%d'),
                        'Semana': semana,
                        'Horas': h_prod,
                        'Sin capacidad (informativo)': False
                    })
                    cont += 1
                    restante = round(restante - q_pos, 6)

                if restante <= 0:
                    break

                # Guardarraíl 2: no avanzar más de N días
                if dias_movidos >= MAX_DIAS_ADELANTE:
                    h_pend = horas_lote(pref, restante)
                    resultado_lotes.append({
                        'Nº de propuesta': cont,
                        'Material': fila['Material'],
                        'Centro': pref,
                        'Clase de orden': 'NORM',
                        'Cantidad a fabricar': round(restante, 2),
                        'Unidad': fila['Unidad'],
                        'Fecha de fabricación': fecha_actual.strftime('%Y%m%d'),
                        'Semana': semana,
                        'Horas': h_pend,
                        'Sin capacidad (informativo)': True
                    })
                    cont += 1
                    restante = 0.0
                    break

                # Mover al día siguiente (normalizado para evitar desbordes por hora)
                fecha_actual = (fecha_actual + timedelta(days=1)).normalize()
                semana = fecha_actual.strftime('%Y-W%U')
                dias_movidos += 1

    return pd.DataFrame(resultado_lotes)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ajusta los parámetros de ejecución.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

# Variables de estado para los DataFrames
df_cap, df_mat, df_cli, df_dem = None, None, None, None

# --- TAB 1: CARGA DE ARCHIVOS (Diseño Programa 1) ---
with tab1:
    st.subheader("📁 Carga tus archivos Excel")
    
    col1, col2 = st.columns(2)
    
    # Bloque 1: Capacidad
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        file1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if file1:
            try:
                df_cap = pd.read_excel(file1)
                guardar_archivo(file1, "capacidad_planta")
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 2: Maestro Materiales
    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        file2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if file2:
            try:
                df_mat = pd.read_excel(file2)
                guardar_archivo(file2, "maestro_materiales")
                st.success("✅ Cargado")
                st.dataframe(df_mat, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    
    # Bloque 3: Maestro Clientes
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        file3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if file3:
            try:
                df_cli = pd.read_excel(file3)
                guardar_archivo(file3, "maestro_clientes")
                st.success("✅ Cargado")
                st.dataframe(df_cli, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 4: Demanda
    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        file4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if file4:
            try:
                df_dem = pd.read_excel(file4)
                guardar_archivo(file4, "demanda")
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: EJECUCIÓN (Lógica Programa 2) ---
with tab2:
    if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
    else:
        # Limpieza de columnas
        for d in [df_cap, df_mat, df_cli, df_dem]: d.columns = d.columns.str.strip()
        
        centros_detectados = [str(c) for c in df_cap['Centro'].astype(str).unique()]
        df_dem['Semana_Label'] = pd.to_datetime(df_dem['Fecha de necesidad']).dt.strftime('%Y-W%U')
        lista_semanas = sorted(df_dem['Semana_Label'].unique())

        st.subheader("⚙️ Configuración de Porcentajes por Semana")
        c1_name = centros_detectados[0]
        c2_name = centros_detectados[1] if len(centros_detectados) > 1 else "Centro 2"
        
        st.info(f"El sistema priorizará automáticamente el centro más barato. Usa los sliders para definir el reparto en caso de empate técnico entre **{c1_name}** y **{c2_name}**.")

        ajustes = {}
        cols_sliders = st.columns(4)
        for i, sem in enumerate(lista_semanas):
            with cols_sliders[i % 4]:
                ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50)

        st.markdown("---")
        if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
            with st.spinner("Calculando asignación óptima de costes..."):
                df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

                st.success("✅ Cálculo completado con éxito.")
                
                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Propuestas", len(df_res))
                for i, centro in enumerate(centros_detectados):
                    if i == 0:
                        m2.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")
                    elif i == 1:
                        m3.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")

                st.subheader("📊 Distribución de Carga Horaria")
                carga_plot = df_res.groupby(['Semana', 'Centro'])['Horas'].sum().unstack().fillna(0)
                st.bar_chart(carga_plot)

                st.subheader("📋 Detalle de la Propuesta")
                st.dataframe(df_res.drop(columns=['Horas']), use_container_width=True)

                # Exportación
                output_path = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
                df_res.drop(columns=['Semana', 'Horas']).to_excel(output_path, index=False)
                with open(output_path, "rb") as f:
                    st.download_button("📥 Descargar Propuesta en Excel", data=f, file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 3.2 (Interfaz Unificada)</p>
    <p>Desarrollado con Streamlit | 2026</p>
</div>
""", unsafe_allow_html=True)
