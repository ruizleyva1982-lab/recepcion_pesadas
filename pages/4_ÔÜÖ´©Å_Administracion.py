"""
Página de Administración:
  - Cargar una nueva programación de OFs (Excel exportado de SAP B1)
  - Eliminar toda la programación de una fecha específica (y sus registros
    de entregas/recepciones asociados)
  - Corregir/eliminar un registro puntual de entrega o recepción
  - Ver historial de eliminaciones
Protegida con clave de administrador (st.secrets["admin_password"]).
"""
import pandas as pd
import streamlit as st

from utils import conexion

st.set_page_config(page_title="Administración · Recepción OFs", page_icon="⚙️", layout="wide")
st.markdown("<style>h1,h2,h3{color:#8c1c1c;}</style>", unsafe_allow_html=True)

st.title("⚙️ Administración")

# 1. Manejo del estado de autenticación
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

if not st.session_state.admin_ok:
    st.info("Esta sección requiere clave de administrador.")
    clave = st.text_input("Clave de administrador", type="password")
    if st.button("Ingresar"):
        # Revisa si la clave coincide con la de los Secrets
        if clave == st.secrets.get("admin_password") or clave == st.secrets.get("ADMIN_PASSWORD"):
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")
else:
    # 2. Todo el contenido protegido se ejecuta si la contraseña es correcta
    conexion.inicializar_hojas()

    tab_cargar, tab_eliminar, tab_corregir, tab_historial = st.tabs(
        ["📥 Cargar programación", "🗑️ Eliminar un día completo", "✏️ Corregir un registro", "📜 Historial de eliminaciones"]
    )

    COLUMNAS_SAP = {
        "Nro Documento": "nro_documento",
        "Cod Item": "cod_item",
        "ITEM": "item",
        "Fecha de Vencimiento": "fecha_vencimiento",
        "Cantidad Planificada": "cantidad_planificada",
        "U Medida": "u_medida",
        "Cod Almacén": "cod_almacen",
        "Almacén": "almacen",
        "Linea Prod": "linea_prod",
    }

    # ============================================================== CARGAR
    with tab_cargar:
        st.subheader("Cargar Excel de OFs programadas (exportado de SAP B1)")
        st.caption(
            "El archivo debe tener las columnas: "
            + ", ".join(COLUMNAS_SAP.keys())
        )
        archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])

        if archivo is not None:
            try:
                nuevo = pd.read_excel(archivo)
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")
                st.stop()

            faltantes = [c for c in COLUMNAS_SAP if c not in nuevo.columns]
            if faltantes:
                st.error(f"Faltan columnas en el archivo: {', '.join(faltantes)}")
                st.stop()

            nuevo = nuevo.rename(columns=COLUMNAS_SAP)[list(COLUMNAS_SAP.values())].copy()
            nuevo["nro_documento"] = nuevo["nro_documento"].astype(str)
            nuevo["fecha_vencimiento"] = pd.to_datetime(nuevo["fecha_vencimiento"], errors="coerce")
            nuevo = nuevo.dropna(subset=["fecha_vencimiento"])
            nuevo["cantidad_planificada"] = pd.to_numeric(nuevo["cantidad_planificada"], errors="coerce").fillna(0)

            existentes = conexion.cargar("programacion")
            ya_cargados = set(existentes["nro_documento"].astype(str)) if not existentes.empty else set()

            nuevo["ya_existe"] = nuevo["nro_documento"].isin(ya_cargados)
            a_cargar = nuevo[~nuevo["ya_existe"]].copy()
            duplicados = int(nuevo["ya_existe"].sum())

            st.markdown("**Vista previa**")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Filas leídas", len(nuevo))
            m2.metric("Ya existían (se omiten)", duplicados)
            m3.metric("OFs nuevas a cargar", len(a_cargar))
            m4.metric("Fechas detectadas", nuevo["fecha_vencimiento"].dt.date.nunique())

            if not a_cargar.empty:
                resumen_prev = (
                    a_cargar.groupby(["fecha_vencimiento", "linea_prod"])
                    .size()
                    .reset_index(name="OFs nuevas")
                    .sort_values(["fecha_vencimiento", "linea_prod"])
                )
                resumen_prev["fecha_vencimiento"] = resumen_prev["fecha_vencimiento"].dt.strftime("%d/%m/%Y")
                st.dataframe(resumen_prev, use_container_width=True, hide_index=True)

                if st.button("✅ Confirmar carga", type="primary"):
                    try:
                        filas = []
                        fecha_carga = conexion.ahora_lima().isoformat(timespec="seconds")
                        for _, r in a_cargar.iterrows():
                            filas.append(
                                {
                                    "nro_documento": r["nro_documento"],
                                    "cod_item": r["cod_item"],
                                    "item": r["item"],
                                    "fecha_vencimiento": r["fecha_vencimiento"].date().isoformat(),
                                    "cantidad_planificada": r["cantidad_planificada"],
                                    "u_medida": r["u_medida"],
                                    "cod_almacen": r["cod_almacen"],
                                    "almacen": r["almacen"],
                                    "linea_prod": r["linea_prod"],
                                    "fecha_carga": fecha_carga,
                                }
                            )
                        conexion.agregar_filas("programacion", filas)
                        st.success(f"Se cargaron {len(filas)} OFs nuevas correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error detectado durante la carga: {e}")
                        st.exception(e)
                        st.stop()
            else:
                st.info("Todas las OFs de este archivo ya estaban cargadas. No hay nada nuevo por agregar.")

    # ============================================================== ELIMINAR
    with tab_eliminar:
        st.subheader("Eliminar toda la programación de una fecha")
        st.caption(
            "Esto elimina las OFs programadas de esa fecha y también todos los "
            "registros de entregas y recepciones asociados a ella. No se puede deshacer."
        )

        df_prog = conexion.cargar("programacion")
        if df_prog.empty:
            st.info("No hay programación cargada.")
        else:
            fechas_disp = sorted(df_prog["fecha_vencimiento"].dropna().unique())
            fecha_sel = st.selectbox(
                "Fecha a eliminar", options=fechas_disp, format_func=lambda d: d.strftime("%d/%m/%Y")
            )

            df_ent = conexion.cargar("entregas_dosimetria")
            df_rec = conexion.cargar("recepciones_produccion")

            n_of = int((df_prog["fecha_vencimiento"] == fecha_sel).sum())
            n_ent = int((df_ent["fecha_vencimiento"] == fecha_sel).sum()) if not df_ent.empty else 0
            n_rec = int((df_rec["fecha_vencimiento"] == fecha_sel).sum()) if not df_rec.empty else 0

            st.warning(
                f"Se eliminarán **{n_of} OFs programadas**, **{n_ent} registros de entregas** "
                f"y **{n_rec} registros de recepciones** de la fecha **{fecha_sel.strftime('%d/%m/%Y')}**."
            )

            usuario_elim = st.text_input("Tu nombre (para el registro de auditoría)", key="usuario_elim")
            confirmar = st.checkbox("Entiendo que esta acción no se puede deshacer")
            texto = st.text_input('Escribe "ELIMINAR" para confirmar')

            if st.button(
                "🗑️ Eliminar definitivamente",
                type="primary",
                disabled=not (confirmar and texto == "ELIMINAR" and usuario_elim.strip()),
            ):
                n1 = conexion.eliminar_por_fecha("programacion", fecha_sel)
                n2 = conexion.eliminar_por_fecha("entregas_dosimetria", fecha_sel)
                n3 = conexion.eliminar_por_fecha("recepciones_produccion", fecha_sel)
                conexion.agregar_fila(
                    "historial_eliminaciones",
                    {
                        "timestamp": conexion.ahora_lima().isoformat(timespec="seconds"),
                        "fecha_eliminada": fecha_sel.isoformat(),
                        "usuario": usuario_elim.strip(),
                        "ofs_eliminadas": n1,
                        "entregas_eliminadas": n2,
                        "recepciones_eliminadas": n3,
                    },
                )
                st.success(f"Se eliminó la programación del {fecha_sel.strftime('%d/%m/%Y')} correctamente.")
                st.rerun()

    # ============================================================== CORREGIR
    with tab_corregir:
        st.subheader("Corregir o eliminar un registro puntual")
        st.caption("Útil cuando alguien registró una cantidad incorrecta por error.")

        hoja_sel = st.radio(
            "¿De qué registro se trata?", ["Entregas (Dosimetría)", "Recepciones (Producción)"], horizontal=True
        )
        nombre_hoja = "entregas_dosimetria" if hoja_sel.startswith("Entregas") else "recepciones_produccion"

        df_logs = conexion.cargar(nombre_hoja)
        if df_logs.empty:
            st.info("No hay registros en esta hoja todavía.")
        else:
            fechas_log = sorted(df_logs["fecha_vencimiento"].dropna().unique())
            fecha_log_sel = st.selectbox(
                "Fecha", options=fechas_log, format_func=lambda d: d.strftime("%d/%m/%Y"), key="fecha_corregir"
            )
            vista_log = df_logs[df_logs["fecha_vencimiento"] == fecha_log_sel].sort_values("timestamp", ascending=False)

            if vista_log.empty:
                st.info("No hay registros para esta fecha.")
            else:
                etiquetas = vista_log.apply(
                    lambda r: f"{r['timestamp']} · {r['item']} ({r['linea_prod']}) · {r['cantidad_ofs']:.0f} OFs · {r['usuario']}",
                    axis=1,
                ).tolist()
                ids = vista_log["id"].tolist()
                mapa = dict(zip(etiquetas, ids))

                elegido = st.selectbox("Selecciona el registro a eliminar", options=etiquetas)
                if st.button("🗑️ Eliminar este registro", type="primary"):
                    ok = conexion.eliminar_registro_por_id(nombre_hoja, mapa[elegido])
                    if ok:
                        st.success("Registro eliminado.")
                        st.rerun()
                    else:
                        st.error("No se pudo eliminar el registro (puede que ya no exista).")

    # ============================================================== HISTORIAL
    with tab_historial:
        st.subheader("Historial de eliminaciones de programaciones")
        df_hist = conexion.cargar("historial_eliminaciones")
        if df_hist.empty:
            st.caption("Todavía no se ha eliminado ninguna programación.")
        else:
            st.dataframe(
                df_hist.sort_values("timestamp", ascending=False).rename(
                    columns={
                        "timestamp": "Fecha/hora",
                        "fecha_eliminada": "Fecha eliminada",
                        "usuario": "Usuario",
                        "ofs_eliminadas": "OFs eliminadas",
                        "entregas_eliminadas": "Entregas eliminadas",
                        "recepciones_eliminadas": "Recepciones eliminadas",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
