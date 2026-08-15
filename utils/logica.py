"""
Lógica de negocio: agregaciones y cálculo de estados de entrega/recepción.

Reglas clave:
  - "programado"  = cantidad de OFs (filas del Excel de SAP) para ese
                     producto + línea + fecha de vencimiento.
  - "entregado"   = suma de todos los parciales que Dosimetría registró
                     para ese producto + línea + fecha.
  - "recibido"    = suma de todos los parciales que Producción registró
                     para ese producto + línea + fecha.
  - "alineado"    = True si lo que Dosimetría dice haber entregado
                     coincide exactamente con lo que Producción dice
                     haber recibido (conciliación entre áreas).
"""
from __future__ import annotations

import pandas as pd

CLAVES = ["fecha_vencimiento", "linea_prod", "cod_item", "item"]


def _estado(cantidad: float, total: float) -> str:
    if total <= 0:
        return "—"
    if cantidad <= 0:
        return "🔴 Pendiente"
    if cantidad > total:
        return "⚠️ Exceso"
    if cantidad >= total:
        return "✅ Completo"
    return "🟡 Parcial"


def resumen_detallado(
    df_prog: pd.DataFrame, df_ent: pd.DataFrame, df_rec: pd.DataFrame
) -> pd.DataFrame:
    columnas_finales = CLAVES + [
        "programado", "cantidad_planificada", "u_medida",
        "entregado", "recibido",
        "pendiente_entregar", "pendiente_recibir", "diferencia",
        "estado_entrega", "estado_recepcion", "estado", "alineado",
    ]

    if df_prog.empty:
        return pd.DataFrame(columns=columnas_finales)

    prog = (
        df_prog.groupby(CLAVES)
        .agg(
            programado=("nro_documento", "count"),
            cantidad_planificada=("cantidad_planificada", "sum"),
            u_medida=("u_medida", "first"),
        )
        .reset_index()
    )

    if df_ent.empty:
        ent = pd.DataFrame(columns=CLAVES + ["entregado"])
    else:
        ent = df_ent.groupby(CLAVES).agg(entregado=("cantidad_ofs", "sum")).reset_index()

    if df_rec.empty:
        rec = pd.DataFrame(columns=CLAVES + ["recibido"])
    else:
        rec = df_rec.groupby(CLAVES).agg(recibido=("cantidad_ofs", "sum")).reset_index()

    res = prog.merge(ent, on=CLAVES, how="left").merge(rec, on=CLAVES, how="left")
    res["entregado"] = res["entregado"].fillna(0)
    res["recibido"] = res["recibido"].fillna(0)

    res["pendiente_entregar"] = res["programado"] - res["entregado"]
    res["pendiente_recibir"] = res["programado"] - res["recibido"]
    res["diferencia"] = res["entregado"] - res["recibido"]
    res["alineado"] = res["entregado"] == res["recibido"]

    res["estado_entrega"] = res.apply(
        lambda r: _estado(r["entregado"], r["programado"]), axis=1
    )
    res["estado_recepcion"] = res.apply(
        lambda r: _estado(r["recibido"], r["programado"]), axis=1
    )
    res["estado"] = res["estado_recepcion"]

    return res[columnas_finales].sort_values(
        ["fecha_vencimiento", "linea_prod", "item"]
    ).reset_index(drop=True)


def resumen_por_linea(detallado: pd.DataFrame) -> pd.DataFrame:
    columnas = [
        "fecha_vencimiento", "linea_prod", "productos_totales",
        "programado", "entregado", "recibido",
        "pendiente_recibir", "pct_completado",
        "productos_completos", "descuadres",
    ]
    if detallado.empty:
        return pd.DataFrame(columns=columnas)

    g = (
        detallado.groupby(["fecha_vencimiento", "linea_prod"])
        .agg(
            productos_totales=("item", "count"),
            programado=("programado", "sum"),
            entregado=("entregado", "sum"),
            recibido=("recibido", "sum"),
            productos_completos=("estado", lambda s: (s == "✅ Completo").sum()),
            descuadres=("alineado", lambda s: int((~s).sum())),
        )
        .reset_index()
    )
    g["pendiente_recibir"] = g["programado"] - g["recibido"]
    g["pct_completado"] = (
        (g["recibido"] / g["programado"] * 100).clip(lower=0, upper=100).round(1).fillna(0)
    )
    return g[columnas].sort_values(["fecha_vencimiento", "linea_prod"]).reset_index(drop=True)
