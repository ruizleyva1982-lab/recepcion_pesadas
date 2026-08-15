"""Página de registro para Dosimetría: entregas de insumos a Producción."""
from utils.registro import pagina_registro

pagina_registro(
    rol="Dosimetría",
    hoja="entregas_dosimetria",
    columna_propia="entregado",
    columna_contraria="recibido",
    color_primario="#8c1c1c",
    icono="📦",
)
