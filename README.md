========================================================
 GMN AI — Panel de Control para Modelos de IA Locales
 Creado por G.M.N TechLab
========================================================

¿Qué es esto?
--------------
GMN AI es una interfaz gráfica (Windows) para cargar y usar modelos de
lenguaje GGUF con llama.cpp, sin necesidad de escribir comandos ni usar
la terminal. Corre 100% en tu propia PC — nada sale a internet salvo que
tú actives explícitamente una función que lo requiera (búsqueda web,
descarga de modelos, proveedores en la nube).

Requisitos
----------
- Windows 10 / 11 (64 bits)
- Tu propia copia de llama-server.exe (llama.cpp), compilada para tu
  hardware: CUDA si tienes GPU NVIDIA, o el build CPU/Vulkan si no.
  Descárgalo de: https://github.com/ggml-org/llama.cpp/releases
- GPU con VRAM dedicada recomendada, pero no obligatoria (el programa
  detecta tu CPU/GPU y funciona igual, solo más lento sin GPU).
- Modelos en formato .gguf (puedes descargarlos desde la pestaña
  "Descargar (Hugging Face)" incluida en el programa).

Cómo empezar
------------
1. Descomprime "gmn ai" donde quieras (no hace falta instalador).
2. Abre "interfaz_agentes.exe".
3. En la pestaña "Modelos": agrega la carpeta donde tengas tus .gguf,
   o descarga uno nuevo desde "Descargar (Hugging Face)".
4. En "TurboQuant": apunta a tu llama-server.exe (una sola vez).
5. Elige tu modelo y presiona "🚀 Cargar modelo (1 clic)".
6. Prueba el modelo en "Chat / Playground", o conecta VS Code / Roo
   Code / Continue / Cline / OpenCode al endpoint que te muestra la
   pestaña "Conexión".

Funciones principales
----------------------
- Selector visual de modelos GGUF, con varias carpetas guardadas.
- TurboQuant: cuantización de la caché KV para ahorrar VRAM.
- Auto-ajuste de contexto a la VRAM libre (--fit), con margen de
  seguridad configurable para no saturar la memoria de video.
- Contexto configurable hasta 1,000,000 de tokens.
- Modo Router: sirve varios modelos a la vez, con auto-carga bajo
  demanda.
- Decodificación especulativa (N-gram, MTP, o con modelo draft), con
  ajuste fino de tokens por pasada y umbral de aceptación.
- Offload de expertos MoE a la CPU, para cargar modelos grandes en
  poca VRAM.
- Adaptadores LoRA, y control del modo de carga del modelo
  (--load-mode: auto / mmap / mlock / none).
- Búsqueda web integrada en el Chat/Playground — sin API key, usa
  DuckDuckGo directamente.
- Proveedores en la nube: conecta OpenAI, Anthropic (Claude) u otro
  compatible con tu propia API key, para usarlos junto a tus modelos
  locales desde la misma ventana de chat.
- Perfiles de configuración guardables (cargar/guardar toda la
  configuración de una página con un clic).
- Monitor en vivo de GPU, VRAM, CPU y RAM.
- Descarga de modelos directo desde Hugging Face, con confirmación
  antes de bajar cualquier archivo.
- Túnel remoto (cloudflared) para exponer el servidor fuera de tu red,
  si lo necesitas.
- Temas de color (incluye modo Día ☀️ / Noche 🌙 con combinación
  automática de colores) y apariencia personalizable.

Seguridad
---------
- El servidor local no tiene clave de acceso por defecto: cualquier
  programa en tu red local podría usarlo. Configura una "API Key" en
  TurboQuant → Seguridad del servidor si te conecta desde otra PC.
- Ninguna clave (API keys de proveedores en la nube, contraseña del
  servidor) se envía a G.M.N TechLab ni a nadie más — se guarda solo
  en tu propia PC, en archivos de configuración locales.

Código abierto
--------------
El código fuente de este programa está disponible en:
  https://github.com/jediknightgeorge-ship-it/gmn-ai

Créditos
--------
Creado por G.M.N TechLab, construido sobre llama.cpp
(https://github.com/ggml-org/llama.cpp).
