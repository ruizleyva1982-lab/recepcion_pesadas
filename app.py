"""
Panel de Recepción de OFs — Dosimetría ↔ Producción
María Almenara

Dashboard general: KPIs, resumen por línea y detalle por producto.
"""
import streamlit as st
import pandas as pd

from utils import conexion, logica

st.set_page_config(
    page_title="Recepción OFs · Dashboard",
    page_icon="📊",
    layout="wide",
)

conexion.inicializar_hojas()

# ---------------------------------------------------------------- estilos
st.markdown(
    """
    <style>
        div[data-testid="stMetric"] {
            background-color: #fff5f5;
            border: 1px solid #f1c0c0;
            border-radius: 10px;
            padding: 14px 10px;
        }
        div[data-testid="stMetricLabel"] { font-weight: 600; }
        h1, h2, h3 { color: #8c1c1c; }
    </style>
    """,
    unsafe_allow_html=True,
)

col_titulo, col_refrescar = st.columns([6, 1])
with col_titulo:
    st.title("📊 Recepción de OFs — Dosimetría ↔ Producción")
    st.caption("Conciliación de órdenes de fabricación programadas, entregadas y recibidas")
with col_refrescar:
    st.write("")
    if st.button("🔄 Actualizar", use_container_width=True):
        conexion.refrescar()
        st.rerun()

df_prog = conexion.cargar("programacion")

if df_prog.empty:
    st.info(
        "Todavía no hay ninguna programación cargada. Ve a la página "
        "**⚙️ Administración** para cargar el Excel de OFs exportado de SAP B1."
    )
    st.stop()

df_ent = conexion.cargar("entregas_dosimetria")
df_rec = conexion.cargar("recepciones_produccion")

# ---------------------------------------------------------------- filtros
fechas_disp = sorted(df_prog["fecha_vencimiento"].dropna().unique())
lineas_disp = sorted(df_prog["linea_prod"].dropna().unique())

c1, c2 = st.columns([2, 3])
with c1:
    fechas_sel = st.multiselect(
        "Fecha de vencimiento (programación)",
        options=fechas_disp,
        default=fechas_disp,
        format_func=lambda d: d.strftime("%d/%m/%Y"),
    )
with c2:
    lineas_sel = st.multiselect("Línea de producción", options=lineas_disp, default=lineas_disp)

if not fechas_sel or not lineas_sel:
    st.warning("Selecciona al menos una fecha y una línea para ver el resumen.")
    st.stop()

f_prog = df_prog[df_prog["fecha_vencimiento"].isin(fechas_sel) & df_prog["linea_prod"].isin(lineas_sel)]
f_ent = df_ent[df_ent["fecha_vencimiento"].isin(fechas_sel) & df_ent["linea_prod"].isin(lineas_sel)] if not df_ent.empty else df_ent
f_rec = df_rec[df_rec["fecha_vencimiento"].isin(fechas_sel) & df_rec["linea_prod"].isin(lineas_sel)] if not df_rec.empty else df_rec

detalle = logica.resumen_detallado(f_prog, f_ent, f_rec)
por_linea = logica.resumen_por_linea(detalle)

# ---------------------------------------------------------------- KPIs
total_of = int(detalle["programado"].sum())
total_recibido = int(detalle["recibido"].sum())
total_entregado = int(detalle["entregado"].sum())
pct_general = round(total_recibido / total_of * 100, 1) if total_of else 0
descuadres = int((~detalle["alineado"]).sum())
productos_pend = int((detalle["estado"] == "🔴 Pendiente").sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("OFs programadas", f"{total_of:,}".replace(",", " "))
k2.metric("OFs recibidas (Producción)", f"{total_recibido:,}".replace(",", " "), f"{pct_general}% del total")
k3.metric("OFs entregadas (Dosimetría)", f"{total_entregado:,}".replace(",", " "))
k4.metric("Productos con descuadre", descuadres, delta_color="inverse" if descuadres else "off")
k5.metric("Productos 100% pendientes", productos_pend)

st.divider()

# ---------------------------------------------------------------- resumen por línea
st.subheader("Avance por línea de producción")
if por_linea.empty:
    st.info("Sin datos para los filtros seleccionados.")
else:
    for _, fila in por_linea.iterrows():
        etiqueta = f"**{fila['linea_prod']}** · {fila['fecha_vencimiento'].strftime('%d/%m/%Y')}"
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.progress(
                min(int(fila["pct_completado"]), 100),
                text=f"{etiqueta} — {fila['recibido']:.0f} / {fila['programado']:.0f} OFs recibidas "
                     f"({fila['pct_completado']}%)",
            )
        with col_b:
            extra = f"⚠️ {int(fila['descuadres'])} descuadre(s)" if fila["descuadres"] else "✅ Alineado"
            st.caption(f"{int(fila['productos_completos'])}/{int(fila['productos_totales'])} productos completos · {extra}")

st.divider()

# ---------------------------------------------------------------- tabla detallada
st.subheader("Detalle por producto")

filtro_estado = st.selectbox(
    "Filtrar por estado de recepción",
    ["Todos", "🔴 Pendiente", "🟡 Parcial", "✅ Completo", "⚠️ Exceso"],
)
solo_descuadres = st.checkbox("Mostrar solo productos con descuadre Dosimetría vs Producción")

tabla = detalle.copy()
if filtro_estado != "Todos":
    tabla = tabla[tabla["estado"] == filtro_estado]
if solo_descuadres:
    tabla = tabla[~tabla["alineado"]]

tabla_mostrar = tabla.rename(
    columns={
        "fecha_vencimiento": "Fecha",
        "linea_prod": "Línea",
        "cod_item": "Código",
        "item": "Producto",
        "programado": "Programado (OFs)",
        "entregado": "Entregado x Dosimetría",
        "recibido": "Recibido x Producción",
        "pendiente_recibir": "Pendiente x recibir",
        "diferencia": "Diferencia (Ent. - Rec.)",
        "estado": "Estado",
    }
)[
    [
        "Fecha", "Línea", "Código", "Producto", "Programado (OFs)",
        "Entregado x Dosimetría", "Recibido x Producción",
        "Pendiente x recibir", "Diferencia (Ent. - Rec.)", "Estado",
    ]
]

st.dataframe(tabla_mostrar, use_container_width=True, hide_index=True)
st.caption(f"{len(tabla_mostrar)} producto(s) mostrados de {len(detalle)} en total.")
