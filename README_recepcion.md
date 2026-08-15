# Recepción de OFs — Dosimetría ↔ Producción

App en Streamlit para conciliar las órdenes de fabricación (OFs) que
Dosimetría prepara/entrega y las que Producción recibe, día a día, línea
por línea y producto por producto.

## Qué resuelve

Cada día se programan varias OFs por producto (por ejemplo, 27 OFs de
`ALMIBAR RED VELVET`). Dosimetría no siempre entrega todo de una vez, y
Producción no siempre recibe todo junto. Esta app permite:

- Cargar la programación del día desde el Excel que exporta SAP B1.
- Que **Dosimetría** registre, por parciales, cuántas OFs va entregando.
- Que **Producción** registre, por parciales, cuántas OFs va recibiendo.
- Ver en todo momento cuánto está **completo** y cuánto **pendiente**,
  por producto y por línea.
- **Conciliar**: comparar lo que Dosimetría dice haber entregado contra
  lo que Producción dice haber recibido, y detectar descuadres.
- Eliminar la programación completa de un día específico (con las
  entregas/recepciones asociadas) cuando sea necesario.

## Estructura del proyecto

```
recepcion/
├── app.py                       # Dashboard general
├── pages/
│   ├── 1_📦_Dosimetria.py       # Registro de entregas
│   ├── 2_🏭_Produccion.py       # Registro de recepciones
│   ├── 3_🔍_Conciliacion.py     # Comparación Dosimetría vs Producción
│   └── 4_⚙️_Administracion.py   # Cargar Excel / eliminar día / corregir registros
├── utils/
│   ├── conexion.py              # Conexión y lectura/escritura en Google Sheets
│   ├── logica.py                # Cálculo de programado/entregado/recibido/estado
│   └── registro.py              # UI compartida entre Dosimetría y Producción
├── generar_secrets.py           # Genera .streamlit/secrets.toml localmente
├── requirements.txt
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

Los datos se guardan en una Google Sheet con 4 hojas (se crean solas la
primera vez que corre la app): `programacion`, `entregas_dosimetria`,
`recepciones_produccion`, `historial_eliminaciones`.

## 1. Crear la Google Sheet y la cuenta de servicio

1. Entra a [Google Cloud Console](https://console.cloud.google.com/) y
   crea un proyecto nuevo, por ejemplo `recepcion-ma`.
2. Habilita las APIs **Google Sheets API** y **Google Drive API**.
3. Ve a *IAM y administración → Cuentas de servicio* y crea una cuenta
   de servicio (por ejemplo `streamlit-recepcion`). Genera una clave
   nueva en formato **JSON** y descárgala.
4. Crea una Google Sheet nueva y vacía (puede llamarse "Recepción OFs
   María Almenara"). Cópiate el ID de la hoja (la parte de la URL entre
   `/d/` y `/edit`).
5. **Comparte la Google Sheet como Editor** con el correo de la cuenta
   de servicio (el campo `client_email` del JSON descargado).

## 2. Generar tus credenciales locales

Con el JSON descargado y el ID de la hoja, desde la carpeta del
proyecto:

```bash
python generar_secrets.py ruta\a\credenciales.json ID_DE_LA_HOJA tu_clave_admin
```

Esto crea `.streamlit/secrets.toml` (ese archivo **no se sube a
GitHub**, ya está en `.gitignore`). La `clave_admin` es la contraseña
que pedirá la página de Administración antes de dejar cargar/eliminar
datos.

## 3. Probar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 4. Subir a GitHub

```bash
cd C:\Users\sergioruiz\Reportes\recepcion
git init
git add .
git commit -m "App de recepción de OFs Dosimetría-Producción"
git branch -M main
git remote add origin https://github.com/ruizleyva1982-lab/recepcion.git
git push -u origin main
```

(`.streamlit/secrets.toml` no se sube porque está en `.gitignore`;
solo se sube `secrets.toml.example` como plantilla).

## 5. Desplegar en Streamlit Cloud

1. En [share.streamlit.io](https://share.streamlit.io), crea una app
   nueva apuntando al repo `recepcion`, archivo principal `app.py`.
2. En **Settings → Secrets**, pega el contenido completo de tu
   `.streamlit/secrets.toml` local.
3. Deploy. Comparte el link con Dosimetría y Producción.

## Uso diario

1. **Administración → Cargar programación**: sube el Excel del día
   exportado de SAP B1 (mismas columnas que `DATA.xlsx`: `Nro
   Documento`, `Cod Item`, `ITEM`, `Fecha de Vencimiento`, `Cantidad
   Planificada`, `U Medida`, `Cod Almacén`, `Almacén`, `Linea Prod`).
   La app detecta OFs ya cargadas y no las duplica, así que puedes
   volver a subir el mismo archivo sin miedo.
2. **Dosimetría**: cada vez que se entrega un lote de OFs de un
   producto, se registra la cantidad ahí. Se puede registrar varias
   veces en el día para el mismo producto — se va sumando.
3. **Producción**: igual, pero registrando lo que efectivamente se
   recibe.
4. **Conciliación**: ambas áreas pueden revisar si sus números
   coinciden. Si Dosimetría entregó 27 y Producción registró 20, esa
   fila queda marcada como descuadre.
5. **Administración → Eliminar un día completo**: para cuando se cargó
   una programación equivocada o hay que rehacer un día entero.

## Notas técnicas

- Las versiones de `streamlit`, `pandas` y `numpy` están fijadas
  deliberadamente (`1.38.0` / `2.1.4` / `1.26.4`) y la app evita
  `pandas.Styler` en las tablas — por la experiencia previa de crashes
  (segmentation fault) en Streamlit Cloud con combinaciones más
  nuevas. El estado visual se muestra con texto + emoji en vez de
  colorear celdas con Styler.
- Los timestamps usan `zoneinfo("America/Lima")`.
- Cada registro de entrega/recepción se guarda como una fila
  independiente (no se sobrescribe), así queda historial completo de
  quién registró qué y cuándo — eso es lo que permite acumular
  parciales y también auditar.
