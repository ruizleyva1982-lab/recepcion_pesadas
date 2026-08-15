"""
Página de registro compartida entre Dosimetría (entregas) y Producción
(recepciones). Ambas páginas llaman a `pagina_registro(...)` con su propio
rol para no duplicar la lógica.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import conexion, logica


def pagina_registro(
    rol: str,
    hoja: str,
    columna_propia: str,
    columna_contraria: str,
    color_primario: str,
    icono: str,
):
    """
    rol: "Dosimetría" o "Producción" (para textos)
    hoja: nombre de la hoja de Sheets donde se registra ("entregas_dosimetria" / "recepciones_produccion")
    columna_propia: "entregado" o "recibido" (la que este rol construye)
    columna_contraria: la columna del otro rol, para mostrar contexto de conciliación
    """
    st.set_page_config(page_title=f"{rol} · Recepción OFs", page_icon=icono, layout="wide")

    st.markdown(
        f"""
        <style>
            h1, h2, h3 {{ color: {color_primario}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    conexion.inicializar_hojas()

    col_t, col_r = st.columns([6, 1])
    with col_t:
        st.title(f"{icono} {rol}")
        verbo = "entregar" if columna_propia == "entregado" else "recibir"
        st.caption(f"Registra por parciales lo que vas a {verbo} y compáralo con lo programado.")
    with col_r:
        st.write("")
        if st.button("🔄 Actualizar", use_container_width=True, key=f"refrescar_{hoja}"):
            conexion.refrescar()
            st.rerun()

    df_prog = conexion.cargar("programacion")
    if df_prog.empty:
        st.info(
            "Todavía no hay ninguna programación cargada. Ve a "
            "**⚙️ Administración** para cargar el Excel de OFs."
        )
        st.stop()

    df_ent = conexion.cargar("entregas_dosimetria")
    df_rec = conexion.cargar("recepciones_produccion")
    df_propia = df_ent if hoja == "entregas_dosimetria" else df_rec

    # ------------------------------------------------------------ filtros
    fechas_disp = sorted(df_prog["fecha_vencimiento"].dropna().unique())
    hoy = conexion.ahora_lima().date()
    default_fecha = hoy if hoy in fechas_disp else fechas_disp[0]

    c1, c2 = st.columns([1, 2])
    with c1:
        fecha_sel = st.selectbox(
            "Fecha de vencimiento",
            options=fechas_disp,
            index=fechas_disp.index(default_fecha),
            format_func=lambda d: d.strftime("%d/%m/%Y"),
        )
    with c2:
        lineas_disp = sorted(df_prog.loc[df_prog["fecha_vencimiento"] == fecha_sel, "linea_prod"].unique())
        lineas_sel = st.multiselect("Línea de producción", options=lineas_disp, default=lineas_disp)

    if "usuario_" + hoja not in st.session_state:
        st.session_state["usuario_" + hoja] = ""
    st.session_state["usuario_" + hoja] = st.text_input(
        "Tu nombre (para el registro)", value=st.session_state["usuario_" + hoja], key=f"nombre_{hoja}"
    )
    usuario = st.session_state["usuario_" + hoja].strip()

    if not lineas_sel:
        st.warning("Selecciona al menos una línea.")
        st.stop()

    f_prog = df_prog[(df_prog["fecha_vencimiento"] == fecha_sel) & (df_prog["linea_prod"].isin(lineas_sel))]
    f_ent = df_ent[(df_ent["fecha_vencimiento"] == fecha_sel) & (df_ent["linea_prod"].isin(lineas_sel))] if not df_ent.empty else df_ent
    f_rec = df_rec[(df_rec["fecha_vencimiento"] == fecha_sel) & (df_rec["linea_prod"].isin(lineas_sel))] if not df_rec.empty else df_rec

    detalle = logica.resumen_detallado(f_prog, f_ent, f_rec)

    if detalle.empty:
        st.info("No hay productos programados para esta fecha y línea(s).")
        st.stop()

    pendiente_col = "pendiente_entregar" if columna_propia == "entregado" else "pendiente_recibir"
    estado_col = "estado_entrega" if columna_propia == "entregado" else "estado_recepcion"

    # ------------------------------------------------------------ KPIs
    total_prog = int(detalle["programado"].sum())
    total_propia = int(detalle[columna_propia].sum())
    pct = round(total_propia / total_prog * 100, 1) if total_prog else 0
    completos = int((detalle[estado_col] == "✅ Completo").sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("OFs programadas", total_prog)
    k2.metric(f"OFs {('entregadas' if columna_propia=='entregado' else 'recibidas')}", total_propia, f"{pct}%")
    k3.metric("Productos completos", f"{completos}/{len(detalle)}")

    st.divider()

    # ------------------------------------------------------------ tabla resumen
    st.subheader("Productos programados")
    tabla = detalle.sort_values(pendiente_col, ascending=False).rename(
        columns={
            "linea_prod": "Línea",
            "cod_item": "Código",
            "item": "Producto",
            "programado": "Programado",
            columna_propia: "Registrado por ti",
            columna_contraria: f"Registrado por {'Producción' if columna_propia == 'entregado' else 'Dosimetría'}",
            pendiente_col: "Pendiente",
            estado_col: "Estado",
        }
    )[["Línea", "Código", "Producto", "Programado", "Registrado por ti",
       f"Registrado por {'Producción' if columna_propia == 'entregado' else 'Dosimetría'}",
       "Pendiente", "Estado"]]
    st.dataframe(tabla, use_container_width=True, hide_index=True)

    st.divider()

    # ------------------------------------------------------------ formulario de registro
    st.subheader(f"Registrar {'entrega' if columna_propia == 'entregado' else 'recepción'} parcial")

    opciones = detalle.apply(
        lambda r: f"{r['item']} ({r['cod_item']}) · {r['linea_prod']} — pendiente {r[pendiente_col]:.0f}",
        axis=1,
    ).tolist()
    indice_map = {opciones[i]: i for i in range(len(opciones))}

    seleccion = st.selectbox("Producto", options=opciones)
    fila = detalle.iloc[indice_map[seleccion]]

    colf1, colf2, colf3 = st.columns([1, 1, 2])
    with colf1:
        st.metric("Programado", f"{fila['programado']:.0f}")
    with colf2:
        st.metric("Pendiente", f"{fila[pendiente_col]:.0f}")

    with st.form(key=f"form_{hoja}", clear_on_submit=True):
        cantidad = st.number_input(
            "Cantidad de OFs a registrar ahora",
            min_value=0,
            step=1,
            value=0,
        )
        comentario = st.text_input("Comentario (opcional)")
        enviar = st.form_submit_button("✅ Registrar", use_container_width=True)

        if enviar:
            if cantidad <= 0:
                st.error("Ingresa una cantidad mayor a 0.")
            elif not usuario:
                st.error("Escribe tu nombre antes de registrar.")
            else:
                if cantidad > fila[pendiente_col]:
                    st.warning(
                        f"Estás registrando {cantidad:.0f} OFs, más de lo pendiente "
                        f"({fila[pendiente_col]:.0f}). Se guardará igual, revisa que sea correcto."
                    )
                conexion.agregar_fila(
                    hoja,
                    {
                        "id": conexion.nuevo_id(),
                        "timestamp": conexion.ahora_lima().isoformat(timespec="seconds"),
                        "fecha_vencimiento": fecha_sel.isoformat(),
                        "cod_item": fila["cod_item"],
                        "item": fila["item"],
                        "linea_prod": fila["linea_prod"],
                        "cantidad_ofs": cantidad,
                        "usuario": usuario,
                        "comentario": comentario,
                    },
                )
                st.success(f"Registrado: {cantidad:.0f} OFs de '{fila['item']}'.")
                st.rerun()

    # ------------------------------------------------------------ historial
    with st.expander("📜 Ver historial de registros de esta fecha"):
        hist = df_propia[
            (df_propia["fecha_vencimiento"] == fecha_sel) & (df_propia["linea_prod"].isin(lineas_sel))
        ] if not df_propia.empty else df_propia
        if hist.empty:
            st.caption("Todavía no hay registros para esta fecha.")
        else:
            hist_mostrar = hist.sort_values("timestamp", ascending=False).rename(
                columns={
                    "timestamp": "Fecha/hora",
                    "item": "Producto",
                    "linea_prod": "Línea",
                    "cantidad_ofs": "OFs",
                    "usuario": "Usuario",
                    "comentario": "Comentario",
                }
            )[["Fecha/hora", "Producto", "Línea", "OFs", "Usuario", "Comentario"]]
            st.dataframe(hist_mostrar, use_container_width=True, hide_index=True)
