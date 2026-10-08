# Instrucciones Excel App

Aplicación web dedicada a la empresa gualeguaychence Hermann para crear , editar e importar instrucciones de trabajo de piezas metálicas en formato Excel.

## Descripción

Esta herramienta permite generar documentos de instrucciones operativas con estructura estandarizada, cargar información de producción, adjuntar imágenes por paso, validar contenido y exportar el resultado final en un archivo Excel listo para uso.

La app está desarrollada en Python con Flask y se ejecuta localmente en Windows.

## Funcionalidades

- Crear nuevas instrucciones de trabajo.
- Editar datos generales, secuencias, controles y revisiones.
- Importar archivos Excel existentes.
- Adjuntar imágenes a cada paso.
- Validar campos obligatorios y formatos.
- Generar un archivo Excel final con el layout definido por la aplicación.
- Visualizar y administrar instrucciones guardadas en la base local.

## Requisitos

- Windows 10 o 11
- Python 3.11 o superior
- Una edición de Excel de escritorio compatible

## Instalación

### Opción 1: usando los scripts del proyecto

Desde la carpeta del proyecto, ejecutá:

```powershell
install.bat
```

Esto crea el entorno virtual y instala las dependencias.

## Ejecución

Para abrir la aplicación:

```powershell
run.bat
```

La app queda disponible en:

```text
http://127.0.0.1:5000
```

## Estructura del proyecto

```text
instrucciones_excel_app/
├── app.py
├── install.bat
├── run.bat
├── requirements.txt
├── README.md
├── instruction_app/
│   ├── __init__.py
│   ├── db.py
│   ├── generation_plan.py
│   ├── routes.py
│   ├── validation.py
│   ├── excel_templates/
│   ├── services/
│   └── static/
│       └── templates/
├── tests/
└── start.py
```

## Flujo de uso

1. Ejecutá la aplicación.
2. Creá una nueva instrucción.
3. Completá los datos generales del trabajo.
4. Agregá secuencias, controles y documentos relevantes.
5. Adjuntá imágenes si corresponde.
6. Validá la información.
7. Generá y descargá el archivo Excel final.

## Notas importantes

- La aplicación guarda datos localmente en la carpeta de instancia de Flask.
- La versión actual está pensada para uso local y Windows.

## Licencia

El código y diseño no deben ser reutilizados comercialmente sin autorización.

---

Proyecto desarrollado para generar instrucciones de trabajo en Excel desde una interfaz web local.
