"""
Internationalisation for GMN AI.
Supported languages: en (default), es, zh
Language is loaded once at startup from lang_config.json.
A restart is required after changing the language.
"""
import json
import os

_LANG_FILE = None   # set by init() after CARPETA_BASE is known

# ---------------------------------------------------------------------------
# TRANSLATION DICTIONARY
# ---------------------------------------------------------------------------
STRINGS = {
    # ── Sidebar nav ─────────────────────────────────────────────────────────
    "nav_modelos":     {"en": "Models",                       "es": "Modelos",                      "zh": "模型"},
    "nav_descargar":   {"en": "Download (Hugging Face)",      "es": "Descargar (Hugging Face)",      "zh": "下载 (HuggingFace)"},
    "nav_turboquant":  {"en": "TurboQuant",                   "es": "TurboQuant",                   "zh": "TurboQuant"},
    "nav_monitor":     {"en": "Live Monitor",                 "es": "Monitor en vivo",               "zh": "实时监控"},
    "nav_chat":        {"en": "Chat / Playground",            "es": "Chat / Playground",             "zh": "聊天 / 测试"},
    "nav_proveedores": {"en": "Cloud Providers",              "es": "Proveedores en la nube",        "zh": "云服务商"},
    "nav_agentes":     {"en": "Agents (Crew)",                "es": "Agentes (Crew)",                "zh": "智能体 (Crew)"},
    "nav_conexion":    {"en": "Connection",                   "es": "Conexión",                     "zh": "连接"},
    "nav_tunel":       {"en": "Remote Tunnel",                "es": "Túnel remoto",                  "zh": "远程隧道"},
    "nav_apariencia":  {"en": "Appearance",                   "es": "Apariencia",                   "zh": "外观"},
    "nav_acerca":      {"en": "About",                        "es": "Acerca de",                    "zh": "关于"},

    # ── Status bar ───────────────────────────────────────────────────────────
    "status_ready":        {"en": "Status: Ready",            "es": "Estado: Listo",                "zh": "状态: 就绪"},
    "status_ready_start":  {"en": "Status: Ready to start.",  "es": "Estado: Listo para iniciar.",  "zh": "状态: 准备就绪。"},
    "status_searching_hf": {"en": "Searching Hugging Face...","es": "Buscando en Hugging Face...",  "zh": "正在搜索 Hugging Face…"},
    "status_no_gguf":      {"en": "No .gguf files found for that search.",
                            "es": "No se encontraron archivos .gguf para esa búsqueda.",
                            "zh": "未找到匹配的 .gguf 文件。"},
    "status_no_model":     {"en": "❌ No .gguf files found in the configured folders.",
                            "es": "❌ No se encontraron archivos .gguf en las carpetas configuradas.",
                            "zh": "❌ 在已配置文件夹中未找到 .gguf 文件。"},
    "status_server_off":   {"en": "Server is not running.",
                            "es": "El servidor no está corriendo.",
                            "zh": "服务器未运行。"},

    # ── Header ───────────────────────────────────────────────────────────────
    "header_subtitle": {"en": "Control panel · llama.cpp + TurboQuant · Created by G.M.N TechLab",
                        "es": "Panel de control · llama.cpp + TurboQuant · Creado por G.M.N TechLab",
                        "zh": "控制面板 · llama.cpp + TurboQuant · 由 G.M.N TechLab 创建"},

    # ── Page titles ──────────────────────────────────────────────────────────
    "page_modelos":    {"en": "🧩 GGUF Model Selector",              "es": "🧩 Selector de modelos GGUF",               "zh": "🧩 GGUF 模型选择"},
    "page_turboquant": {"en": "🧠 TurboQuant & Server Configuration", "es": "🧠 TurboQuant y configuración del servidor", "zh": "🧠 TurboQuant 与服务器配置"},
    "page_monitor":    {"en": "📊 Live Monitor",                     "es": "📊 Monitor en vivo",                        "zh": "📊 实时监控"},
    "page_chat":       {"en": "💬 Chat / Playground",                "es": "💬 Chat / Playground",                     "zh": "💬 聊天 / 测试"},
    "page_agentes":    {"en": "🤖 Agent Team (CrewAI)",              "es": "🤖 Equipo de Agentes (CrewAI)",             "zh": "🤖 智能体团队 (CrewAI)"},
    "page_conexion":   {"en": "🔌 Agent Connection",                 "es": "🔌 Conexión del agente",                   "zh": "🔌 智能体连接"},
    "page_tunel":      {"en": "🌐 Remote Tunnel",                    "es": "🌐 Túnel remoto",                          "zh": "🌐 远程隧道"},
    "page_apariencia": {"en": "🎨 Appearance",                       "es": "🎨 Apariencia",                            "zh": "🎨 外观"},
    "page_acerca":     {"en": "ℹ️ About this program",               "es": "ℹ️ Acerca de este programa",               "zh": "ℹ️ 关于本程序"},
    "page_descargar":  {"en": "🔍 Download Models from Hugging Face", "es": "🔍 Descargar modelos desde Hugging Face",    "zh": "🔍 从 Hugging Face 下载模型"},
    "page_proveedores":{"en": "☁️ Cloud Providers",                  "es": "☁️ Proveedores en la nube",                 "zh": "☁️ 云服务商"},

    # ── Panel headers ────────────────────────────────────────────────────────
    "panel_carpetas":      {"en": "📁 Folders to search for models (.gguf)",    "es": "📁 Carpetas donde buscar modelos (.gguf)",           "zh": "📁 模型搜索文件夹 (.gguf)"},
    "panel_perfiles":      {"en": "💾 Configuration Profiles",                  "es": "💾 Perfiles de configuración",                      "zh": "💾 配置方案"},
    "panel_llama":         {"en": "🦙 llama-server.exe Location",               "es": "🦙 Ubicación de llama-server.exe",                  "zh": "🦙 llama-server.exe 路径"},
    "panel_cfg_servidor":  {"en": "⚙️ Server Configuration",                    "es": "⚙️ Configuración del servidor",                     "zh": "⚙️ 服务器配置"},
    "panel_rendimiento":   {"en": "⚡ Advanced Performance (optional)",          "es": "⚡ Rendimiento avanzado (opcional)",                 "zh": "⚡ 高级性能 (可选)"},
    "panel_lora":          {"en": "🎛️ LoRA Adapter (optional)",                 "es": "🎛️ Adaptador LoRA (opcional)",                      "zh": "🎛️ LoRA 适配器 (可选)"},
    "panel_moe":           {"en": "🧩 Large MoE Models with Low VRAM (optional)","es": "🧩 Modelos MoE grandes en poca VRAM (opcional)",    "zh": "🧩 大型 MoE 低显存运行 (可选)"},
    "panel_vision":        {"en": "👁️ Vision Model (optional)",                 "es": "👁️ Modelo de visión (opcional)",                    "zh": "👁️ 视觉模型 (可选)"},
    "panel_kv_cache":      {"en": "🗄️ KV Cache Quantization (optional)",        "es": "🗄️ Cuantización del caché KV (opcional)",           "zh": "🗄️ KV 缓存量化 (可选)"},
    "panel_rope":          {"en": "🔁 Context Extension RoPE (optional)",       "es": "🔁 Extensión de contexto RoPE (opcional)",          "zh": "🔁 上下文扩展 RoPE (可选)"},
    "panel_spec":          {"en": "⚡ Speculative Decoding (optional)",          "es": "⚡ Decodificación especulativa (opcional)",          "zh": "⚡ 推测解码 (可选)"},
    "panel_muestreo":      {"en": "🎲 Sampling",                                "es": "🎲 Muestreo",                                       "zh": "🎲 采样参数"},
    "panel_tools":         {"en": "🛠️ Tools",                                   "es": "🛠️ Herramientas",                                   "zh": "🛠️ 工具"},
    "panel_endpoint":      {"en": "Active Endpoint",                            "es": "Endpoint activo",                                   "zh": "活跃端点"},
    "panel_clientes":      {"en": "Config ready to copy",                       "es": "Configuración lista para copiar",                   "zh": "配置一键复制"},
    "panel_agente1":       {"en": "👨‍💻 Agent 1 — Developer",                    "es": "👨‍💻 Agente 1 — Desarrollador",                      "zh": "👨‍💻 智能体 1 — 开发者"},
    "panel_agente2":       {"en": "🔍 Agent 2 — QA / Reviewer",                "es": "🔍 Agente 2 — QA / Revisor",                       "zh": "🔍 智能体 2 — QA / 审核"},
    "panel_color_mode":    {"en": "Color Mode",                                 "es": "Modo de color",                                     "zh": "颜色模式"},
    "panel_paletas":       {"en": "Quick Palettes",                             "es": "Paletas rápidas",                                   "zh": "快速配色"},
    "panel_custom_color":  {"en": "Custom Colors",                              "es": "Colores personalizados",                            "zh": "自定义颜色"},
    "panel_language":      {"en": "Language",                                   "es": "Idioma",                                            "zh": "语言"},

    # ── Buttons ──────────────────────────────────────────────────────────────
    "btn_stop_server":   {"en": "⏹ Stop server",                "es": "⏹ Detener servidor",             "zh": "⏹ 停止服务器"},
    "btn_load_model":    {"en": "🚀 Load model (1 click)",       "es": "🚀 Cargar modelo (1 clic)",      "zh": "🚀 加载模型 (1键)"},
    "btn_start_router":  {"en": "🚀🔀 Start Router (multi-model)","es": "🚀🔀 Iniciar Router (varios modelos)","zh": "🚀🔀 启动路由器 (多模型)"},
    "btn_add":           {"en": "➕ Add",                        "es": "➕ Agregar",                     "zh": "➕ 添加"},
    "btn_remove":        {"en": "🗑 Remove",                     "es": "🗑 Quitar",                      "zh": "🗑 移除"},
    "btn_refresh":       {"en": "↻ Refresh",                     "es": "↻ Refrescar",                   "zh": "↻ 刷新"},
    "btn_load":          {"en": "📥 Load",                       "es": "📥 Cargar",                      "zh": "📥 载入"},
    "btn_save":          {"en": "💾 Save",                       "es": "💾 Guardar",                     "zh": "💾 保存"},
    "btn_delete":        {"en": "🗑 Delete",                     "es": "🗑 Eliminar",                    "zh": "🗑 删除"},
    "btn_change":        {"en": "📂 Change...",                  "es": "📂 Cambiar...",                  "zh": "📂 更改…"},
    "btn_browse":        {"en": "📂 Browse...",                  "es": "📂 Elegir...",                   "zh": "📂 浏览…"},
    "btn_copy":          {"en": "📋 Copy",                       "es": "📋 Copiar",                      "zh": "📋 复制"},
    "btn_copy_continue": {"en": "🧩 Copy Continue config (YAML)","es": "🧩 Copiar config Continue (YAML)","zh": "🧩 复制 Continue 配置 (YAML)"},
    "btn_copy_cline":    {"en": "🖇️ Copy Cline / OpenAI-Compatible config","es": "🖇️ Copiar config Cline / OpenAI-Compatible","zh": "🖇️ 复制 Cline 配置"},
    "btn_copy_opencode": {"en": "💻 Copy OpenCode config (JSON)","es": "💻 Copiar config OpenCode (JSON)","zh": "💻 复制 OpenCode 配置 (JSON)"},
    "btn_run_agents":    {"en": "🤖 Run Agent Team (Crew)",      "es": "🤖 Ejecutar equipo de Agentes (Crew)","zh": "🤖 运行智能体团队 (Crew)"},
    "btn_day":           {"en": "☀️ Day",                        "es": "☀️ Día",                         "zh": "☀️ 日间"},
    "btn_night":         {"en": "🌙 Night",                      "es": "🌙 Noche",                       "zh": "🌙 夜间"},
    "btn_reset_theme":   {"en": "↺ Reset to default theme",      "es": "↺ Restablecer tema por defecto", "zh": "↺ 重置默认主题"},
    "btn_preset_large":  {"en": "⚡ Preset: large model fast",    "es": "⚡ Preset: modelo grande rápido", "zh": "⚡ 预设: 大模型快速"},
    "btn_send":          {"en": "Send",                          "es": "Enviar",                         "zh": "发送"},
    "btn_clear_chat":    {"en": "🗑 Clear",                      "es": "🗑 Limpiar",                     "zh": "🗑 清空"},
    "btn_lang_en":       {"en": "🇬🇧 English",                   "es": "🇬🇧 English",                    "zh": "🇬🇧 English"},
    "btn_lang_es":       {"en": "🇪🇸 Español",                   "es": "🇪🇸 Español",                    "zh": "🇪🇸 Español"},
    "btn_lang_zh":       {"en": "🇨🇳 中文",                      "es": "🇨🇳 中文",                       "zh": "🇨🇳 中文"},
    "btn_search_hf":     {"en": "🔍 Search",                     "es": "🔍 Buscar",                      "zh": "🔍 搜索"},
    "btn_download":      {"en": "⬇️ Download",                   "es": "⬇️ Descargar",                  "zh": "⬇️ 下载"},
    "btn_start_tunnel":  {"en": "🌐 Start Tunnel",               "es": "🌐 Iniciar Túnel",               "zh": "🌐 启动隧道"},
    "btn_stop_tunnel":   {"en": "⏹ Stop Tunnel",                 "es": "⏹ Detener Túnel",               "zh": "⏹ 停止隧道"},
    "btn_copy_tunnel":   {"en": "📋 Copy URL",                   "es": "📋 Copiar URL",                  "zh": "📋 复制链接"},

    # ── Form labels ──────────────────────────────────────────────────────────
    "lbl_host":              {"en": "Host:",                          "es": "Host:",                              "zh": "主机:"},
    "lbl_port":              {"en": "Port:",                          "es": "Puerto:",                            "zh": "端口:"},
    "lbl_context":           {"en": "Context (tokens):",              "es": "Contexto (tokens):",                 "zh": "上下文 (tokens):"},
    "lbl_ngl":               {"en": "GPU Layers (-ngl):",             "es": "Capas en GPU (-ngl):",              "zh": "GPU 层数 (-ngl):"},
    "lbl_threads":           {"en": "CPU Threads (-t):",              "es": "Hilos de CPU (-t):",                "zh": "CPU 线程 (-t):"},
    "lbl_max_models":        {"en": "Max models at once:",            "es": "Máx. modelos a la vez:",            "zh": "最多同时加载:"},
    "lbl_batch_threads":     {"en": "Batch threads (-tb):",           "es": "Hilos para batch (-tb):",           "zh": "批处理线程 (-tb):"},
    "lbl_batch":             {"en": "Batch size (-b):",               "es": "Batch size (-b):",                  "zh": "批量大小 (-b):"},
    "lbl_ubatch":            {"en": "Ubatch size (-ub):",             "es": "Ubatch size (-ub):",                "zh": "微批大小 (-ub):"},
    "lbl_ctx_checkpoints":   {"en": "Context checkpoints (--ctx-checkpoints):", "es": "Checkpoints de contexto (--ctx-checkpoints):", "zh": "上下文检查点:"},
    "lbl_numa":              {"en": "NUMA (--numa):",                 "es": "NUMA (--numa):",                    "zh": "NUMA (--numa):"},
    "lbl_load_mode":         {"en": "Load mode (--load-mode):",       "es": "Modo de carga (--load-mode):",      "zh": "加载模式 (--load-mode):"},
    "lbl_vram_margin":       {"en": "VRAM margin to reserve (MB):",   "es": "Margen de VRAM libre a reservar (MB):", "zh": "保留显存空间 (MB):"},
    "lbl_lora_scale":        {"en": "Scale (optional, e.g. 0.8):",    "es": "Escala (opcional, ej. 0.8):",       "zh": "缩放 (可选, 如 0.8):"},
    "lbl_moe_mode":          {"en": "Mode:",                          "es": "Modo:",                             "zh": "模式:"},
    "lbl_moe_layers":        {"en": "N layers:",                      "es": "N capas:",                          "zh": "N 层:"},
    "lbl_rol":               {"en": "Role:",                          "es": "Rol:",                              "zh": "角色:"},
    "lbl_goal":              {"en": "Goal:",                          "es": "Objetivo:",                         "zh": "目标:"},
    "lbl_task":              {"en": "Task:",                          "es": "Tarea:",                            "zh": "任务:"},
    "lbl_api_key":           {"en": "API Key:",                       "es": "API Key:",                          "zh": "API 密钥:"},
    "lbl_kv_k":              {"en": "KV Key type:",                   "es": "Tipo KV Key:",                      "zh": "KV Key 类型:"},
    "lbl_kv_v":              {"en": "KV Value type:",                 "es": "Tipo KV Value:",                    "zh": "KV Value 类型:"},
    "lbl_rope_mode":         {"en": "Extension mode:",                "es": "Modo de extensión:",                "zh": "扩展模式:"},
    "lbl_yarn_orig":         {"en": "Original context (--yarn-orig-ctx):", "es": "Contexto original (--yarn-orig-ctx):", "zh": "原始上下文 (--yarn-orig-ctx):"},
    "lbl_spec_type":         {"en": "Speculative type:",              "es": "Tipo especulativo:",                "zh": "推测类型:"},
    "lbl_spec_n_max":        {"en": "Draft tokens (--draft-max):",    "es": "Tokens draft (--draft-max):",       "zh": "Draft tokens (--draft-max):"},
    "lbl_spec_p_min":        {"en": "Min. prob. (--draft-p-min):",    "es": "Prob. mín. (--draft-p-min):",       "zh": "最低概率 (--draft-p-min):"},
    "lbl_spec_draft_ngl":    {"en": "Draft GPU layers (--draft-ngl):","es": "Capas GPU draft (--draft-ngl):",    "zh": "Draft GPU 层数 (--draft-ngl):"},
    "lbl_spec_kv_k":         {"en": "Draft KV Key:",                  "es": "Draft KV Key:",                     "zh": "Draft KV Key:"},
    "lbl_spec_kv_v":         {"en": "Draft KV Value:",                "es": "Draft KV Value:",                   "zh": "Draft KV Value:"},
    "lbl_acento":            {"en": "Accent",                         "es": "Acento",                            "zh": "强调色"},
    "lbl_fondo":             {"en": "Background",                     "es": "Fondo",                             "zh": "背景"},
    "lbl_panel_color":       {"en": "Panel",                          "es": "Panel",                             "zh": "面板"},
    "lbl_texto":             {"en": "Text",                           "es": "Texto",                             "zh": "文字"},
    "lbl_provider_chat":     {"en": "☁️ Reply with:",                 "es": "☁️ Responder con:",                 "zh": "☁️ 回复方式:"},
    "lbl_model_router":      {"en": "🔀 Model (Router):",             "es": "🔀 Modelo (Router):",               "zh": "🔀 模型 (路由器):"},

    # ── Checkboxes ───────────────────────────────────────────────────────────
    "chk_auto_fit":    {"en": "--fit: let llama.cpp auto-fit context to available VRAM",
                        "es": "--fit: dejar que llama.cpp ajuste el contexto solo para que quepa en la VRAM",
                        "zh": "--fit: 让 llama.cpp 自动调整上下文以适配显存"},
    "chk_router_mode": {"en": "🔀 Router Mode: serve multiple models at once (hot-swap)",
                        "es": "🔀 Modo Router: servir varios modelos a la vez (cambia sin reiniciar)",
                        "zh": "🔀 路由器模式: 同时服务多个模型 (热切换)"},
    "chk_autoload":    {"en": "Auto-load model on each request",
                        "es": "Auto-cargar el modelo que pida cada request",
                        "zh": "按请求自动加载模型"},
    "chk_fx_mode":     {"en": "🧬 FX-8320E Mode: use native AVX + FMA4 routines (no AVX2/FMA3)",
                        "es": "🧬 Modo FX-8320E: usar rutinas nativas AVX + FMA4 (sin AVX2/FMA3)",
                        "zh": "🧬 FX-8320E 模式: 使用原生 AVX + FMA4 (无 AVX2/FMA3)"},
    "chk_turboquant":  {"en": "Enable TurboQuant on server start",
                        "es": "Activar TurboQuant al iniciar el servidor",
                        "zh": "启动服务器时启用 TurboQuant"},
    "chk_websearch":   {"en": "Web search (model can search the internet when needed)",
                        "es": "Búsqueda web (el modelo puede buscar en internet cuando lo necesite)",
                        "zh": "网络搜索 (模型可按需搜索互联网)"},
    "chk_spec_backend_sampling": {
        "en": "⚡ Draft sampling on GPU (--spec-draft-backend-sampling, experimental)",
        "es": "⚡ Muestreo del draft en la GPU (--spec-draft-backend-sampling, experimental)",
        "zh": "⚡ Draft GPU 采样 (--spec-draft-backend-sampling, 实验性)"},
    "chk_reasoning_preserve": {
        "en": "🧠 Preserve reasoning between turns (--reasoning-preserve)",
        "es": "🧠 Preservar razonamiento entre turnos (--reasoning-preserve)",
        "zh": "🧠 跨轮次保留推理 (--reasoning-preserve)"},

    # ── Legends / misc ───────────────────────────────────────────────────────
    "legend_vram":       {"en": "🟢 Fits comfortably in 11GB   🟡 Tight (lower context)   🔴 May not fit in VRAM",
                          "es": "🟢 Cabe cómodo en 11GB   🟡 Ajustado (baja el contexto)   🔴 Puede no caber en VRAM",
                          "zh": "🟢 11GB内轻松运行   🟡 偏紧 (降低上下文)   🔴 可能超出显存"},
    "lang_restart_note": {"en": "Restart the app to apply the new language.",
                          "es": "Reinicia la app para aplicar el nuevo idioma.",
                          "zh": "重启应用以应用新语言。"},
    "agents_result_note":{"en": "The result is saved to 'resultado_agentes.md' next to the program.",
                          "es": "El resultado se guarda en 'resultado_agentes.md' junto al programa.",
                          "zh": "结果保存在程序旁边的 'resultado_agentes.md' 中。"},
    "profile_hint":      {"en": "Choose a ★ profile to apply instantly (⚡ fast, 📚 large context, 🐘 big model, 🧩 MoE, 🛡️ safe).",
                          "es": "Elige un perfil con ★ para aplicarlo al instante (⚡ rápido, 📚 gran contexto, 🐘 modelo grande, 🧩 MoE, 🛡️ seguro).",
                          "zh": "选择带 ★ 的方案即时应用 (⚡ 快速, 📚 大上下文, 🐘 大模型, 🧩 MoE, 🛡️ 安全)。"},
    "about_text":        {"en": "© 2026 G.M.N TechLab\nCreated by G.M.N TechLab · built on llama.cpp\nOpen source: github.com/jediknightgeorge-ship-it/gmn-ai",
                          "es": "© 2026 G.M.N TechLab\nCreado por G.M.N TechLab · construido sobre llama.cpp\nCódigo abierto: github.com/jediknightgeorge-ship-it/gmn-ai",
                          "zh": "© 2026 G.M.N TechLab\n由 G.M.N TechLab 创建 · 基于 llama.cpp 构建\n开源: github.com/jediknightgeorge-ship-it/gmn-ai"},
}

# ---------------------------------------------------------------------------
# RUNTIME
# ---------------------------------------------------------------------------
_current_lang = "en"


def init(base_folder: str):
    """Call once right after CARPETA_BASE is known, before any t() call."""
    global _LANG_FILE, _current_lang
    _LANG_FILE = os.path.join(base_folder, "lang_config.json")
    try:
        if os.path.isfile(_LANG_FILE):
            with open(_LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            lang = data.get("lang", "en")
            if lang in ("en", "es", "zh"):
                _current_lang = lang
    except Exception:
        pass


def t(key: str) -> str:
    """Return the translated string for the current language."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_current_lang, entry.get("en", key))


def get_lang() -> str:
    return _current_lang


def set_lang(code: str):
    """Persist the language choice — takes effect on next restart."""
    if code not in ("en", "es", "zh"):
        return
    if _LANG_FILE is None:
        return
    try:
        with open(_LANG_FILE, "w", encoding="utf-8") as f:
            json.dump({"lang": code}, f)
    except Exception:
        pass
