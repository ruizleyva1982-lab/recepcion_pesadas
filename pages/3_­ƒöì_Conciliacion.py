"""
Página de Conciliación: compara lado a lado lo que Dosimetría dice haber
entregado contra lo que Producción dice haber recibido, para que ambas
áreas puedan verificar que están alineadas.
"""
import io

import pandas as pd
import streamlit as st

from utils import conexion, logica

st.set_page_config(page_title="Conciliación · Recepción OFs", page_icon="🔍", layout="wide")
st.markdown("<style>h1,h2,h3{color:#5a2a83;}</style>", unsafe_allow_html=True)

conexion.inicializar_hojas()

col_t, col_r = st.columns([6, 1])
with col_t:
    st.title("🔍 Conciliación Dosimetría vs Producción")
    st.caption("Verifica que lo entregado por Dosimetría coincida con lo recibido por Producción.")
with col_r:
    st.write("")
    if st.button("🔄 Actualizar", use_container_width=True):
        conexion.refrescar()
        st.rerun()

df_prog = conexion.cargar("programacion")
if df_prog.empty:
    st.info("Todavía no hay ninguna programación cargada. Ve a **⚙️ Administración** para cargarla.")
    st.stop()

df_ent = conexion.cargar("entregas_dosimetria")
df_rec = conexion.cargar("recepciones_produccion")

fechas_disp = sorted(df_prog["fecha_vencimiento"].dropna().unique())
lineas_disp = sorted(df_prog["linea_prod"].dropna().unique())

c1, c2, c3 = st.columns([2, 3, 2])
with c1:
    fechas_sel = st.multiselect(
        "Fecha de vencimiento", options=fechas_disp, default=fechas_disp,
        format_func=lambda d: d.strftime("%d/%m/%Y"),
    )
with c2:
    lineas_sel = st.multiselect("Línea de producción", options=lineas_disp, default=lineas_disp)
with c3:
    vista = st.selectbox(
        "Vista", ["Todos", "Solo descuadres", "Solo pendientes", "Solo completos"]
    )

if not fechas_sel or not lineas_sel:
    st.warning("Selecciona al menos una fecha y una línea.")
    st.stop()

f_prog = df_prog[df_prog["fecha_vencimiento"].isin(fechas_sel) & df_prog["linea_prod"].isin(lineas_sel)]
f_ent = df_ent[df_ent["fecha_vencimiento"].isin(fechas_sel) & df_ent["linea_prod"].isin(lineas_sel)] if not df_ent.empty else df_ent
f_rec = df_rec[df_rec["fecha_vencimiento"].isin(fechas_sel) & df_rec["linea_prod"].isin(lineas_sel)] if not df_rec.empty else df_rec

detalle = logica.resumen_detallado(f_prog, f_ent, f_rec)

descuadres = detalle[~detalle["alineado"]]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Productos comparados", len(detalle))
k2.metric("Alineados ✅", int(detalle["alineado"].sum()))
k3.metric("Con descuadre ⚠️", len(descuadres), delta_color="inverse" if len(descuadres) else "off")
k4.metric(
    "OFs de diferencia (abs.)",
    int(detalle["diferencia"].abs().sum()),
)

if len(descuadres):
    st.warning(
        f"Hay **{len(descuadres)}** producto(s) donde lo entregado por Dosimetría "
        "no coincide con lo recibido por Producción. Revísalos con el área correspondiente."
    )

st.divider()

tabla = detalle.copy()
if vista == "Solo descuadres":
    tabla = tabla[~tabla["alineado"]]
elif vista == "Solo pendientes":
    tabla = tabla[tabla["estado"] == "🔴 Pendiente"]
elif vista == "Solo completos":
    tabla = tabla[tabla["estado"] == "✅ Completo"]

tabla_mostrar = tabla.assign(
    alineado_txt=tabla["alineado"].map({True: "✅ Sí", False: "❌ No"})
).rename(
    columns={
        "fecha_vencimiento": "Fecha",
        "linea_prod": "Línea",
        "cod_item": "Código",
        "item": "Producto",
        "programado": "Programado",
        "entregado": "Entregado (Dosimetría)",
        "recibido": "Recibido (Producción)",
        "diferencia": "Diferencia",
        "estado_entrega": "Estado entrega",
        "estado_recepcion": "Estado recepción",
        "alineado_txt": "¿Coinciden?",
    }
)[
    [
        "Fecha", "Línea", "Código", "Producto", "Programado",
        "Entregado (Dosimetría)", "Recibido (Producción)", "Diferencia",
        "Estado entrega", "Estado recepción", "¿Coinciden?",
    ]
]

st.dataframe(tabla_mostrar, use_container_width=True, hide_index=True)
st.caption(f"{len(tabla_mostrar)} producto(s) mostrados de {len(detalle)} en total.")

# ------------------------------------------------------------ exportar
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    tabla_mostrar.to_excel(writer, index=False, sheet_name="Conciliacion")
buffer.seek(0)

st.download_button(
    "⬇️ Exportar esta vista a Excel",
    data=buffer,
    file_name=f"conciliacion_recepcion_ofs_{conexion.ahora_lima().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
