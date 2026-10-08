# Instrucciones Excel App — Hermann

Aplicación web local desarrollada para **Hermann**, empresa industrial de Gualeguaychú, Entre Ríos, destinada a crear, editar e importar instrucciones de trabajo para piezas metálicas y generar documentos Excel a partir de una plantilla estandarizada.

## Descripción

La aplicación permite digitalizar y simplificar la elaboración de instrucciones operativas utilizadas en los procesos de producción de la empresa.

Mediante una interfaz web basada en formularios, los usuarios pueden cargar información técnica siguiendo la nomenclatura establecida por Hermann, organizar las secuencias de trabajo, incorporar imágenes y generar archivos Excel con un formato definido.

La herramienta está desarrollada en Python con Flask y está diseñada para ejecutarse localmente en equipos Windows.

## Funcionalidades

* Crear nuevas instrucciones de trabajo.
* Editar instrucciones existentes.
* Importar archivos Excel para reutilizar información.
* Completar datos generales de piezas y procesos productivos.
* Organizar secuencias de trabajo, controles y revisiones.
* Adjuntar imágenes asociadas a los pasos de producción.
* Validar campos obligatorios y formatos de los datos.
* Generar archivos Excel a partir de una plantilla predefinida.
* Visualizar y administrar instrucciones guardadas localmente.
* Descargar los documentos generados para su utilización en el entorno de producción.

## Tecnologías utilizadas

* **Python 3.11 o superior:** lógica de la aplicación y procesamiento de datos.
* **Flask 3.1.2:** framework para la aplicación web y gestión de rutas.
* **Waitress 3.0.2:** servidor WSGI para ejecutar la aplicación.
* **pywin32:** integración con componentes de Windows cuando corresponde.
* **HTML, CSS y JavaScript:** interfaz web y funcionalidades del lado del cliente.
* **Excel:** formato de importación y exportación de instrucciones de trabajo.

## Requisitos

* Windows 10 u 11.
* Python 3.11 o superior.
* Microsoft Excel de escritorio compatible con las plantillas utilizadas.
* Acceso a los archivos de plantilla requeridos por la aplicación.

## Instalación

### Opción 1: mediante el instalador del proyecto

Cloná el repositorio:

```bash
git clone https://github.com/felipemjca/Generador-de-instrucciones-para-piezas-de-Hermann.git
```

Ingresá a la carpeta del proyecto:

```bash
cd Generador-de-instrucciones-para-piezas-de-Hermann
```

Ejecutá el instalador:

```powershell
install.bat
```

El script prepara el entorno virtual e instala las dependencias necesarias definidas en `requirements.txt`.

## Ejecución

Para iniciar la aplicación, ejecutá:

```powershell
run.bat
```

La aplicación queda disponible localmente en:

```text
http://127.0.0.1:5000
```

La dirección permite acceder a la interfaz desde el navegador del equipo en el que se está ejecutando el servidor.

## Estructura del proyecto

```text
Generador-de-instrucciones-para-piezas-de-Hermann/
├── app.py
├── install.bat
├── run.bat
├── requirements.txt
├── README.md
├── start.py
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
└── .gitignore
```

### Componentes principales

* `app.py`: punto de entrada de la aplicación.
* `start.py`: script auxiliar para iniciar el sistema.
* `install.bat`: automatiza la preparación del entorno y la instalación de dependencias.
* `run.bat`: facilita el inicio de la aplicación en Windows.
* `requirements.txt`: define las dependencias de Python.
* `instruction_app/db.py`: gestión de los datos almacenados localmente.
* `instruction_app/routes.py`: rutas y operaciones disponibles desde la interfaz web.
* `instruction_app/validation.py`: validación de los datos ingresados.
* `instruction_app/generation_plan.py`: lógica relacionada con la preparación de la generación de instrucciones.
* `instruction_app/excel_templates/`: plantillas Excel utilizadas por la aplicación.
* `instruction_app/services/`: módulos de servicios y lógica auxiliar.
* `instruction_app/static/`: recursos estáticos de la interfaz.
* `tests/`: pruebas del proyecto.

## Flujo de uso

1. Iniciar la aplicación mediante `run.bat`.
2. Acceder a la interfaz desde el navegador.
3. Crear una instrucción nueva o importar un archivo existente.
4. Completar los datos generales de la pieza y del proceso.
5. Definir las secuencias de trabajo, controles y revisiones.
6. Adjuntar imágenes cuando sea necesario.
7. Validar la información ingresada.
8. Generar y descargar el archivo Excel final.

## Almacenamiento y consideraciones

* La aplicación está orientada al uso local en Windows.
* Los datos se almacenan localmente en la ubicación de instancia configurada por Flask.
* La generación de documentos depende de las plantillas y del formato definido para las instrucciones de Hermann.
* Para utilizar la aplicación en otro equipo, es necesario preparar el entorno y disponer de los recursos requeridos por el proyecto.

## Desarrollador

**Felipe Mujica**

Estudiante de la especialidad Computación en la Escuela de Educación Técnica N.º 2 de Gualeguaychú, Entre Ríos.

Interesado en el desarrollo de software, la automatización de procesos y la creación de herramientas digitales para resolver necesidades concretas de empresas y organizaciones.

Este proyecto representa una experiencia práctica de desarrollo de una aplicación orientada a un entorno industrial, integrando una interfaz web, procesamiento de información y generación automatizada de documentos Excel.

## Repositorio

Código fuente disponible en GitHub:

https://github.com/felipemjca/Generador-de-instrucciones-para-piezas-de-Hermann

## Licencia

El código fuente, el diseño y los recursos asociados están sujetos a las autorizaciones correspondientes de sus titulares. Su reutilización comercial requiere autorización previa.

---

Proyecto desarrollado para **Hermann**, Gualeguaychú, Entre Ríos, Argentina.
