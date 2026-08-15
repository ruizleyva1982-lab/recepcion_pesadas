from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    """Crea y almacena en caché la conexión con Supabase."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def ahora_lima() -> datetime:
    """Devuelve la fecha y hora actual en la zona horaria de Lima (America/Lima)."""
    return datetime.now(ZoneInfo("America/Lima"))


def inicializar_hojas():
    """Valida la conexión con Supabase."""
    try:
        supabase = get_supabase_client()
        supabase.table("programacion").select("id").limit(1).execute()
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")


@st.cache_data(ttl=60)
def cargar(tabla_nombre: str) -> pd.DataFrame:
    """Lee una tabla completa de Supabase y devuelve un DataFrame de pandas."""
    supabase = get_supabase_client()
    try:
        res = supabase.table(tabla_nombre).select("*").execute()
        data = res.data

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Eliminar columna ID autonumérico si existe
        if "id" in df.columns:
            df = df.drop(columns=["id"])

        # Convertir fechas a objeto date de Python
        if "fecha_vencimiento" in df.columns and not df.empty:
            df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"]).dt.date

        return df
    except Exception as e:
        st.error(f"Error al cargar la tabla '{tabla_nombre}': {e}")
        return pd.DataFrame()


def guardar_registros(tabla_nombre: str, registros: list[dict]):
    """Inserta una lista de registros/filas en Supabase."""
    if not registros:
        return

    supabase = get_supabase_client()

    # Formatear objetos date a texto YYYY-MM-DD para Supabase
    for r in registros:
        if "fecha_vencimiento" in r and hasattr(r["fecha_vencimiento"], "isoformat"):
            r["fecha_vencimiento"] = r["fecha_vencimiento"].isoformat()

    supabase.table(tabla_nombre).insert(registros).execute()
    refrescar()


def eliminar_por_fecha(fecha_str: str):
    """Elimina la programación, entregas y recepciones de una fecha específica."""
    supabase = get_supabase_client()

    supabase.table("programacion").delete().eq("fecha_vencimiento", fecha_str).execute()
    supabase.table("entregas_dosimetria").delete().eq("fecha_vencimiento", fecha_str).execute()
    supabase.table("recepciones_produccion").delete().eq("fecha_vencimiento", fecha_str).execute()

    refrescar()


def refrescar():
    """Limpia la caché de Streamlit."""
    st.cache_data.clear()