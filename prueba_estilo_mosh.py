def pagina_ordenes_fabricacion():
    """
    Pantalla: 🏭 Planificación de Órdenes de Fabricación
    - Validaciones robustas (evita evaluar DataFrames en booleano).
    - Preparación de demanda con semana ISO y unión con materiales y clientes.
    - Selección de centro base (DG/MCH) por coste si está disponible.
    """

    st.markdown("### 🏭 Planificación de Órdenes de Fabricación")

    # ─────────────────────────────────────────────────────────────────────
    # Validar cargas (NO evaluar DataFrames en booleano → ValueError)
    # ─────────────────────────────────────────────────────────────────────
    required = ("df_cap", "df_mat", "df_cli", "df_dem")
    missing = []
    for k in required:
        df = st.session_state.get(k)
        if df is None or (hasattr(df, "empty") and df.empty):
            missing.append(k)

    if missing:
        st.warning("⚠️ Debes cargar todos los maestros en Tablas maestras.")
        st.info("Faltan: " + ", ".join(missing))
        return

    # Referencias locales
    df_cap = st.session_state.df_cap
    df_mat = st.session_state.df_mat
    df_cli = st.session_state.df_cli
    df_dem = st.session_state.df_dem

    # ─────────────────────────────────────────────────────────────────────
    # Validaciones mínimas de columnas en Demanda
    # ─────────────────────────────────────────────────────────────────────
    required_cols_dem = {"Material", "Unidad", "Fecha de necesidad", "Cantidad"}
    faltan_dem = required_cols_dem - set(df_dem.columns)
    if faltan_dem:
        st.error("Faltan columnas en Demanda: " + ", ".join(sorted(faltan_dem)))
        return

    # Semana ISO en Demanda
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"], errors="coerce")
    if df_dem["Fecha_DT"].isna().any():
        st.error("Existen fechas no válidas en 'Fecha de necesidad'. Revísalas.")
        return

    iso = df_dem["Fecha_DT"].dt.isocalendar()
    df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    # Detectar columna de cliente en Demanda y Clientes
    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)
    if not col_cli_dem or not col_cli_cli:
        st.error("No se pudo identificar la columna de cliente en Demanda/Clientes.")
        return

    # ─────────────────────────────────────────────────────────────────────
    # Preparación: unir Demanda ↔ Materiales ↔ Clientes
    # ─────────────────────────────────────────────────────────────────────
    # Crea columnas de lote si no vienen en Materiales/merge (para agrupar sin KeyError)
    for col_agg in ("Tamaño lote mínimo", "Tamaño lote máximo"):
        if col_agg not in df_dem.columns:
            df_dem[col_agg] = np.nan

    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    # Capacidad y detección de centros DG/MCH
    capacidades = leer_capacidades(df_cap)
    DG, MCH = detectar_centros(capacidades)
    if not DG or not MCH:
        st.error("No se pudieron identificar los centros DG/MCH a partir de Capacidades.")
        return

    # Selección del centro base por coste (si existen columnas de coste)
    col_cost_dg = next((c for c in df.columns if "cost" in c.lower() and "dg" in c.lower()), None)
    col_cost_mch = next((c for c in df.columns if "cost" in c.lower() and "mch" in c.lower()), None)

    def elegir_centro(r):
        # Si no hay columnas de coste, por defecto DG (o cambia a tu preferencia)
        if col_cost_dg is None or col_cost_mch is None:
            return DG
        c1 = to_float_safe(r.get(col_cost_dg, 0))
        c2 = to_float_safe(r.get(col_cost_mch, 0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(elegir_centro, axis=1)

    # Agregación por Material, Unidad, Centro base y Fecha
    g = df.groupby(
        ["Material", "Unidad", "Centro_Base", "Fecha de necesidad", "Semana_Label"]
    ).agg({
        "Cantidad": "sum",
        "Tamaño lote mínimo": "first",
        "Tamaño lote máximo": "first"
    }).reset_index()

    g = g.rename(columns={
        "Centro_Base": "Centro",
        "Fecha de necesidad": "Fecha",
        "Semana_Label": "Semana"
    })
    # ─────────────────────────────────────────────────────────────────────
    # Acción: Ejecutar cálculo inicial
    # ─────────────────────────────────────────────────────────────────────
    st.markdown("#### 🚀 Ejecutar planificación")
    if st.button("⚙️ Ejecutar cálculo inicial", use_container_width=True):
        with st.spinner("Calculando..."):
            g["Centro"] = g["Centro"].apply(norm_code)
            df_base = modo_C(
                df_agr=g[["Material", "Unidad", "Centro", "Cantidad", "Fecha", "Semana"]],
                df_mat=df_mat,
                capacidades=capacidades,
                DG_code=DG,
                MCH_code=MCH
            )
            st.session_state.df_base = df_base
            st.session_state.capacidades_calc = capacidades
            st.session_state.DG_calc = DG
            st.session_state.MCH_calc = MCH

        guardar_historial("Inicial", st.session_state.usuario, df_base, DG, MCH)
        st.success("✔ Cálculo inicial completado.")

    # ─────────────────────────────────────────────────────────────────────
    # Resultados iniciales
    # ─────────────────────────────────────────────────────────────────────
    if "df_base" in st.session_state and st.session_state.df_base is not None:
        df_base = st.session_state.df_base
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📊 Resultados iniciales")

        c = st.columns(3)
        c[0].metric("Total propuestas", f"{len(df_base):,}")
        c[1].metric(f"Horas {DG}", f"{df_base[df_base['Centro'] == DG]['Horas'].sum():,.1f}h")
        c[2].metric(f"Horas {MCH}", f"{df_base[df_base['Centro'] == MCH]['Horas'].sum():,.1f}h")

        dfp = df_base.copy()
        dfp["Semana"] = dfp["Semana"].astype(str)
        dfp["Centro"] = dfp["Centro"].astype(str)

        carga = dfp.groupby(["Semana", "Centro"])["Horas"].sum().unstack().fillna(0)
        st.bar_chart(carga)
        st.dataframe(carga.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle")
        st.dataframe(df_base)

        # Exportación XLSX de propuesta inicial
        path_ini = os.path.join(UPLOAD_DIR, f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_base.to_excel(path_ini, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_ini, "rb") as f:
                st.download_button("Descargar Propuesta Inicial", f, file_name="Propuesta_Inicial.xlsx")
                # ─────────────────────────────────────────────────────────────────
        # Replanificación por semana (slider 0% → 100%)
        # ─────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🎛️ Ajuste por semana (0% MCH → 100% DG)")

        semanas = sorted(df_base["Semana"].astype(str).unique())
        ajustes = {}
        cols = st.columns(4)
        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(f"Semana {sem}", 0, 100, 50)

        if st.button("🔁 Replanificar", use_container_width=True):
            with st.spinner("Replanificando..."):
                df_final = replanificar(
                    df_base=df_base,
                    df_mat=df_mat,
                    capacidades=capacidades,
                    DG_code=DG,
                    MCH_code=MCH,
                    ajustes=ajustes
                )
                st.session_state.df_replan = df_final

            guardar_historial("Reajustado", st.session_state.usuario, df_final, DG, MCH)
            st.success("✔ Replanificación completada.")

    # ─────────────────────────────────────────────────────────────────────
    # Resultados finales tras replanificación
    # ─────────────────────────────────────────────────────────────────────
    if "df_replan" in st.session_state and st.session_state.df_replan is not None:
        df_final = st.session_state.df_replan
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📈 Resultados tras replanificación")

        c2 = st.columns(3)
        c2[0].metric("Total propuestas", f"{len(df_final):,}")
        c2[1].metric(f"Horas {DG}", f"{df_final[df_final['Centro'] == DG]['Horas'].sum():,.1f}h")
        c2[2].metric(f"Horas {MCH}", f"{df_final[df_final['Centro'] == MCH]['Horas'].sum():,.1f}h")

        dfp2 = df_final.copy()
        dfp2["Semana"] = dfp2["Semana"].astype(str)
        dfp2["Centro"] = dfp2["Centro"].astype(str)
        carga2 = dfp2.groupby(["Semana", "Centro"])["Horas"].sum().unstack().fillna(0)
        st.bar_chart(carga2)
        st.dataframe(carga2.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle final")
        st.dataframe(df_final)

        # Exportación XLSX de propuesta replanificada
        path_fin = os.path.join(UPLOAD_DIR, f"Propuesta_Replanificada_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_final.to_excel(path_fin, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_fin, "rb") as f:
                st.download_button("Descargar Propuesta Replanificada", f, file_name="Propuesta_Replanificada.xlsx")
