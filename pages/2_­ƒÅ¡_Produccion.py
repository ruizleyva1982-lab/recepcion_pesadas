"""Página de registro para Producción: recepción de insumos de Dosimetría."""
from utils.registro import pagina_registro

pagina_registro(
    rol="Producción",
    hoja="recepciones_produccion",
    columna_propia="recibido",
    columna_contraria="entregado",
    color_primario="#1c4b8c",
    icono="🏭",
)
