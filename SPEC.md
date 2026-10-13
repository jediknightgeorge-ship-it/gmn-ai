# GMN AI — Build & Release Spec

## Regla obligatoria antes de subir a GitHub o a la landing

> **Toda compilacion DEBE ser probada corriendo el .exe real antes de publicarse.**
> No se sube nada a GitHub ni se actualiza la landing page sin haber verificado
> que el exe arranca, carga la interfaz y no lanza errores.

### Checklist de verificacion post-compilacion

- [ ] El exe abre sin cuadro de error (`Unhandled exception in script`)
- [ ] La pagina "Modelos" carga sin crash
- [ ] El selector de modelos muestra la lista (o el aviso de "no hay modelos")
- [ ] La pagina "Proveedores" abre y muestra el catalogo de 28 proveedores
- [ ] El Chat envia un mensaje y recibe respuesta (local o cloud)
- [ ] No hay rastro de `TypeError: 'dict' object is not callable` ni similares

### Flujo de compilacion correcto

```
1. Editar interfaz_agentes.py
2. python -c "import ast; ast.parse(open('interfaz_agentes.py', encoding='utf-8').read())"
   -> debe imprimir nada (sin errores de sintaxis)
3. python -m PyInstaller interfaz_agentes.spec --noconfirm --clean
   -> --clean es OBLIGATORIO para evitar que PyInstaller use cache vieja
4. Correr dist\gmn ai\interfaz_agentes.exe y verificar el checklist de arriba
5. Si todo ok -> copiar a releases\vX.X.X\ -> crear ZIP -> subir GitHub -> actualizar landing
```

### Por que --clean es obligatorio

PyInstaller cachea los modulos compilados en `build\`. Si se omite `--clean`, puede
reutilizar archivos `.pyc` de una version anterior y el exe resultante NO refleja los
ultimos cambios del fuente, incluso si la compilacion termina con exit code 0.

Ejemplo real: v1.1.6 salio roto porque PyInstaller reutilizo cache de v1.1.5.
El exe ejecutaba codigo antiguo aunque el fuente estuviera correcto.

---

## Estructura de carpetas de compilación

```
H:\gmi_IA_desktop\
├── dist_v2\gmn ai\            ← salida temporal del compilador (se sobreescribe cada vez)
│   ├── interfaz_agentes.exe
│   └── _internal\
└── releases\                  ← una subcarpeta por versión aprobada y probada
    ├── v1.1.5\
    │   ├── interfaz_agentes.exe
    │   └── _internal\
    └── v1.1.6\
        ├── interfaz_agentes.exe
        └── _internal\
```

### Reglas de la estructura

- **`dist_v2`** es la única carpeta temporal de compilación. No crear `dist_v3`, `dist_nuevo`, etc.
- Después de compilar y **antes de subir nada**, el usuario prueba el exe de `dist_v2\gmn ai\`.
- Solo cuando el usuario da el OK: copiar `dist_v2\gmn ai\*` a `releases\vX.X.X\` y proceder con el ZIP y la publicación.
- El ZIP para GitHub se crea desde `dist_v2\gmn ai\*`, no desde `releases\`.
- Nunca borrar versiones anteriores de `releases\` sin permiso explícito del usuario.

---

Creado: 2026-10-10
