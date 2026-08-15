r"""
Genera el archivo .streamlit/secrets.toml a partir del JSON de la cuenta de
servicio de Google Cloud descargado y del ID de la Google Sheet.

Uso:
    python generar_secrets.py ruta\a\credenciales.json ID_DE_LA_HOJA [clave_admin]
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print("Uso: python generar_secrets.py <credenciales.json> <sheet_id> [clave_admin]")
        sys.exit(1)

    ruta_json = Path(sys.argv[1])
    sheet_id = sys.argv[2]
    admin_password = sys.argv[3] if len(sys.argv) > 3 else "cambia_esta_clave"

    if not ruta_json.exists():
        print(f"No se encontró el archivo {ruta_json}")
        sys.exit(1)

    datos = json.loads(ruta_json.read_text(encoding="utf-8"))

    destino = Path(".streamlit")
    destino.mkdir(exist_ok=True)
    archivo = destino / "secrets.toml"

    with archivo.open("w", encoding="utf-8") as f:
        f.write(f'sheet_id = "{sheet_id}"\n')
        f.write(f'admin_password = "{admin_password}"\n\n')
        f.write("[gcp_service_account]\n")
        for clave, valor in datos.items():
            valor_str = str(valor).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
            f.write(f'{clave} = "{valor_str}"\n')

    print(f"Archivo generado en {archivo.resolve()}")
    print("Recuerda compartir la Google Sheet (como Editor) con:", datos.get("client_email"))


if __name__ == "__main__":
    main()
