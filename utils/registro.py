
"""
Módulo genérico para las páginas de registro (Dosimetría y Producción).
"""
import pandas as pd
import streamlit as st

from utils import conexion


def pagina_registro(rol: str, icono: str):
    st.title(f"{icono} {rol}")

    # Determine la tabla según el rol
    es_dosimetria = rol == "Dosimetría"
    nombre_tabla = "entregas_dosimetria" if es_dosimetria else "recepciones_produccion"

    # 1. Controles principales (Fecha y Usuario)
    col_f, col_u = st.columns([1, 2])
    with col_f:
        fecha_sel = st.date_input("Fecha de programación", value=conexion.ahora_lima().date())
    with col_u:
        usuario = st.text_input("Tu nombre (quien registra)", key=f"usr_{rol}")

    if not usuario.strip():
        st.warning("⚠️ Por favor, ingresa tu nombre arriba para poder registrar.")
        st.stop()

    # 2. Cargar datos actualizados
    df_prog = conexion.cargar("programacion")
    df_logs = conexion.cargar(nombre_tabla)

    if df_prog.empty:
        st.info("No hay programación cargada en el sistema.")
        st.stop()

    # Filtrar programación por fecha
    df_prog["fecha_vencimiento"] = pd.to_datetime(df_prog["fecha_vencimiento"], errors="coerce").dt.date
    prog_fecha = df_prog[df_prog["fecha_vencimiento"] == fecha_sel].copy()

    if prog_fecha.empty:
        st.info(f"No hay OFs programadas para el {fecha_sel.strftime('%d/%m/%Y')}.")
        st.stop()

    # Consolidar planificado por producto/línea
    resumen = (
        prog_fecha.groupby(["cod_item", "item", "linea_prod"])["cantidad_planificada"]
        .sum()
        .reset_index()
    )

    # Consolidar ya entregado/recibido acumulado
    if not df_logs.empty:
        df_logs["fecha_vencimiento"] = pd.to_datetime(df_logs["fecha_vencimiento"], errors="coerce").dt.date
        logs_fecha = df_logs[df_logs["fecha_vencimiento"] == fecha_sel]
        
        if not logs_fecha.empty:
            registrados = (
                logs_fecha.groupby(["cod_item", "linea_prod"])["cantidad_ofs"]
                .sum()
                .reset_index()
                .rename(columns={"cantidad_ofs": "ya_registrado"})
            )
            resumen = resumen.merge(registrados, on=["cod_item", "linea_prod"], how="left")
            resumen["ya_registrado"] = resumen["ya_registrado"].fillna(0)
        else:
            resumen["ya_registrado"] = 0
    else:
        resumen["ya_registrado"] = 0

    resumen["pendiente"] = resumen["cantidad_planificada"] - resumen["ya_registrado"]

    # 3. Formulario de registro
    st.subheader("Registrar entrega parcial")

    opciones = []
    mapa_items = {}
    for _, r in resumen.iterrows():
        # Etiqueta legible para el desplegable
        label = f"{r['item']} ({r['cod_item']}) · {r['linea_prod']} — pendiente {int(r['pendiente'])}"
        opciones.append(label)
        mapa_items[label] = r

    if not opciones:
        st.success("🎉 Todo lo programado para esta fecha ya fue registrado al 100%.")
        st.stop()

    item_elegido = st.selectbox("Producto", options=opciones)
    info_item = mapa_items[item_elegido]

    c1, c2 = st.columns(2)
    c1.metric("Programado", int(info_item["cantidad_planificada"]))
    c2.metric("Pendiente", int(info_item["pendiente"]))

    max_val = max(1, int(info_item["pendiente"]))

    # Formulario estricto de envio
    with st.form("form_entrega", clear_on_submit=True):
        cant_ingresada = st.number_input(
            "Cantidad de OFs a registrar ahora",
            min_value=1,
            max_value=max_val if max_val > 0 else 1,
            value=min(1, max_val),
            step=1,
        )
        comentario = st.text_input("Comentario (opcional)")
        submit = st.form_submit_button("✅ Registrar", type="primary")

        if submit:
            if info_item["pendiente"] <= 0:
                st.error("Este producto ya no tiene cantidad pendiente por registrar.")
            else:
                nuevo_registro = {
                    "id": conexion.nuevo_id(),
                    "timestamp": conexion.ahora_lima().isoformat(timespec="seconds"),
                    "fecha_vencimiento": fecha_sel.isoformat(),
                    "cod_item": str(info_item["cod_item"]),
                    "item": str(info_item["item"]),
                    "linea_prod": str(info_item["linea_prod"]),
                    "cantidad_ofs": int(cant_ingresada),
                    "usuario": usuario.strip(),
                    "comentario": comentario.strip(),
                }

                res = conexion.agregar_fila(nombre_tabla, nuevo_registro)
                if res is not None:
                    # Limpiar la caché de Streamlit para que actualice las métricas
                    st.cache_data.clear()
                    st.success(
                        f"¡Registrado con éxito! Se guardaron {cant_ingresada} OF(s) para {info_item['item']}."
                    )
                    st.info("💡 Haz clic en 'Ver historial de registros' abajo para verificar el envío.")
                else:
                    st.error("Ocurrió un problema al intentar guardar el registro en Supabase.")

    # 4. Historial desplegable
    with st.expander("📜 Ver historial de registros de esta fecha"):
        if not df_logs.empty:
            logs_ver = df_logs[df_logs["fecha_vencimiento"] == fecha_sel].sort_values("timestamp", ascending=False)
            if not logs_ver.empty:
                st.dataframe(
                    logs_ver[["timestamp", "item", "linea_prod", "cantidad_ofs", "usuario", "comentario"]].rename(
                        columns={
                            "timestamp": "Hora",
                            "item": "Producto",
                            "linea_prod": "Línea",
                            "cantidad_ofs": "Cantidad",
                            "usuario": "Usuario",
                            "comentario": "Comentario",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("No hay entregas registradas para esta fecha aún.")
        else:
            st.caption("No hay entregas registradas para esta fecha aún.")
