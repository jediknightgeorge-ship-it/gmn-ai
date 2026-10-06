import sys

# ---------------------------------------------------------------------------
# MODO SERVIDOR MCP DE BUSQUEDA WEB
# ---------------------------------------------------------------------------
# Este bloque va antes que cualquier otro import para que arrancar en este
# modo sea rapido (sin cargar crewai/langchain/tkinter) y funcione tanto en
# modo desarrollo (python interfaz_agentes.py --mcp-web-search) como ya
# compilado (interfaz_agentes.exe --mcp-web-search). llama-server.exe lanza
# este mismo programa como subproceso (via --mcp-servers-config) cuando el
# usuario activa "Busqueda web" en TurboQuant, y le habla por stdio con el
# protocolo MCP. No necesita ninguna API key: usa DuckDuckGo directamente.
if len(sys.argv) > 1 and sys.argv[1] == "--mcp-web-search":
    from mcp.server.fastmcp import FastMCP
    import requests
    from bs4 import BeautifulSoup

    mcp_app = FastMCP("busqueda-web")

    @mcp_app.tool()
    def buscar_web(consulta: str, max_resultados: int = 5) -> str:
        """Busca en internet (via DuckDuckGo) y devuelve titulo, enlace y
        resumen de los resultados mas relevantes para la consulta."""
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": consulta},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=10,
            )
            sopa = BeautifulSoup(resp.text, "html.parser")
            resultados = []
            for bloque in sopa.select(".result")[:max(1, min(max_resultados, 10))]:
                titulo_tag = bloque.select_one(".result__title a")
                snippet_tag = bloque.select_one(".result__snippet")
                if not titulo_tag:
                    continue
                titulo = titulo_tag.get_text(strip=True)
                url = titulo_tag.get("href", "")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                resultados.append(f"- {titulo}\n  {url}\n  {snippet}")
            return "\n\n".join(resultados) if resultados else "No se encontraron resultados."
        except Exception as e:
            return f"Error al buscar en la web: {e}"

    mcp_app.run(transport="stdio")
    sys.exit(0)

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, scrolledtext, simpledialog, ttk

from estilo_apple import BotonRedondo, crear_tarjeta, imagen_redondeada, mezclar, pintar_tarjeta

from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

try:
    import psutil
except ImportError:
    psutil = None

try:
    NUCLEOS_FISICOS_CPU = psutil.cpu_count(logical=False) if psutil else os.cpu_count()
except Exception:
    NUCLEOS_FISICOS_CPU = os.cpu_count()
NUCLEOS_FISICOS_CPU = NUCLEOS_FISICOS_CPU or 4

if getattr(sys, "frozen", False):
    # Ejecutable compilado con PyInstaller: __file__ no es fiable (en modo
    # onefile apunta a la carpeta temporal _MEIxxxxx). Usamos sys.executable.
    CARPETA_BASE = os.path.dirname(os.path.abspath(sys.executable))
    # Los "datas" empaquetados (ej. jaguar_logo.png) quedan en _internal, cuya
    # ruta real Python la expone en sys._MEIPASS.
    CARPETA_ASSETS = getattr(sys, "_MEIPASS", CARPETA_BASE)
else:
    CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
    CARPETA_ASSETS = CARPETA_BASE

RUTA_LOGO_JAGUAR = os.path.join(CARPETA_ASSETS, "jaguar_logo.png")
RUTA_LOGO_GMN = os.path.join(CARPETA_ASSETS, "gmn_logo.png")


def _detectar_carpeta_recursos():
    """Encuentra la carpeta con llama-server.exe y los .gguf.

    Soporta dos casos:
    - El script/exe corre directamente en esa carpeta (uso normal).
    - El exe vive en una subcarpeta propia (ej. 'gmn ai\\interfaz_agentes.exe',
      distribucion 'onedir' de PyInstaller) colocada junto a llama-server.exe,
      en cuyo caso los recursos estan un nivel arriba.
    """
    if os.path.isfile(os.path.join(CARPETA_BASE, "llama-server.exe")):
        return CARPETA_BASE
    carpeta_padre = os.path.dirname(CARPETA_BASE)
    if os.path.isfile(os.path.join(carpeta_padre, "llama-server.exe")):
        return carpeta_padre
    return CARPETA_BASE  # ninguno tiene llama-server.exe; se avisara al usuario


CARPETA_RECURSOS = _detectar_carpeta_recursos()
LLAMA_SERVER_AUTODETECTADO = os.path.join(CARPETA_RECURSOS, "llama-server.exe")
ARCHIVO_TEMA = os.path.join(CARPETA_BASE, "tema_config.json")
ARCHIVO_CARPETAS_MODELOS = os.path.join(CARPETA_BASE, "carpetas_modelos.json")
ARCHIVO_RUTA_LLAMA = os.path.join(CARPETA_BASE, "ruta_llama_server.json")
ARCHIVO_PROVEEDORES_NUBE = os.path.join(CARPETA_BASE, "proveedores_nube.json")


def cargar_proveedores_nube():
    """Lista de proveedores en la nube guardados (OpenAI, Claude, u otro
    compatible), cada uno con su propia API key. Vacia si no hay ninguno
    configurado — el programa sigue funcionando 100% local sin esto."""
    if os.path.isfile(ARCHIVO_PROVEEDORES_NUBE):
        try:
            with open(ARCHIVO_PROVEEDORES_NUBE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def guardar_proveedores_nube(lista):
    try:
        with open(ARCHIVO_PROVEEDORES_NUBE, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cargar_ruta_llama_server():
    """Ruta a llama-server.exe elegida a mano por el usuario (si la hay).

    Permite que el programa siga encontrando llama.cpp aunque se mueva la
    carpeta del programa a cualquier otro lugar del disco, sin depender de
    que esten uno al lado del otro.
    """
    if os.path.isfile(ARCHIVO_RUTA_LLAMA):
        try:
            with open(ARCHIVO_RUTA_LLAMA, "r", encoding="utf-8") as f:
                ruta = json.load(f).get("ruta", "")
            if ruta and os.path.isfile(ruta):
                return ruta
        except Exception:
            pass
    return LLAMA_SERVER_AUTODETECTADO


def guardar_ruta_llama_server(ruta):
    try:
        with open(ARCHIVO_RUTA_LLAMA, "w", encoding="utf-8") as f:
            json.dump({"ruta": ruta}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cargar_carpetas_modelos():
    """Lista de carpetas donde buscar .gguf, guardada entre sesiones.

    Por defecto solo la carpeta de recursos (junto a llama-server.exe), pero
    el usuario puede agregar cualquier otra carpeta del disco sin tener que
    mover ni copiar los modelos.
    """
    if os.path.isfile(ARCHIVO_CARPETAS_MODELOS):
        try:
            with open(ARCHIVO_CARPETAS_MODELOS, "r", encoding="utf-8") as f:
                carpetas = json.load(f)
            if isinstance(carpetas, list) and carpetas:
                return [c for c in carpetas if isinstance(c, str)]
        except Exception:
            pass
    return [CARPETA_RECURSOS]


def guardar_carpetas_modelos(carpetas):
    try:
        with open(ARCHIVO_CARPETAS_MODELOS, "w", encoding="utf-8") as f:
            json.dump(carpetas, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


ARCHIVO_PERFILES = os.path.join(CARPETA_BASE, "perfiles_config.json")


def cargar_perfiles():
    """Perfiles de configuracion del servidor guardados por el usuario.

    Cada perfil es un dict {clave_campo: valor} con una foto de todas las
    opciones de la pagina TurboQuant/Modelos en el momento de guardarlo.
    """
    if os.path.isfile(ARCHIVO_PERFILES):
        try:
            with open(ARCHIVO_PERFILES, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                return datos
        except Exception:
            pass
    return {}


def guardar_perfiles(perfiles):
    try:
        with open(ARCHIVO_PERFILES, "w", encoding="utf-8") as f:
            json.dump(perfiles, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _detectar_cpu_amd_familia15():
    """True si el CPU es un AMD Family 15h (Bulldozer/Piledriver/Steamroller/
    Excavator — ej. FX-83xx). Esa familia trae AVX y FMA4 pero NO AVX2 ni
    FMA3: forzar FMA3 en ella hace que llama.cpp crashee ("illegal
    instruction") en vez de solo ir mas lento, asi que conviene saber si
    estamos en esa familia para no tocar nada relacionado a mano."""
    try:
        info = platform.processor() or ""
        m = re.search(r"Family (\d+)", info)
        return bool(m) and int(m.group(1)) == 21 and "AMD" in info.upper()
    except Exception:
        return False


CPU_ES_AMD_FAMILIA15 = _detectar_cpu_amd_familia15()

TIPOS_CACHE_KV = ["f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"]
CONTEXTOS = ["4096", "8192", "16384", "32768", "65536", "131072", "262144", "524288", "1000000"]

# Combinaciones de muestreo listas para usar. "repeat" es la penalizacion de
# repeticion clasica; "presence" y "dry" son las que mas ayudan contra bucles
# infinitos en modelos pequenos (ver videos de bucles/repeticiones de Nichonauta
# y la guia de Qwen). Vacio = no mandar el parametro (usa el del motor).
PRESETS_MUESTREO = {
    "Por defecto": {"temp": "", "top_p": "", "top_k": "", "min_p": "", "repeat": "1.1", "presence": "", "dry": "", "reasoning": ""},
    "Anti-bucles": {"temp": "0.7", "top_p": "0.95", "top_k": "40", "min_p": "0.05", "repeat": "1.1", "presence": "1.0", "dry": "0.8", "reasoning": ""},
    "Código preciso": {"temp": "0.2", "top_p": "0.9", "top_k": "40", "min_p": "0.05", "repeat": "1.05", "presence": "", "dry": "", "reasoning": ""},
    "Creativo": {"temp": "0.9", "top_p": "0.95", "top_k": "60", "min_p": "0.05", "repeat": "1.1", "presence": "0.5", "dry": "", "reasoning": ""},
}

# Perfiles ya hechos (aparecen arriba en "Perfiles de configuración" con una ★).
# Solo tocan las opciones de rendimiento/memoria; no cambian el modelo, el
# puerto, la clave ni el muestreo. Los valores salen de pruebas reales con
# llama-server b11223 en una RTX 2080 Ti (11 GB) + FX-8320E + 28 GB de RAM.
_BASE_RENDIMIENTO = {
    "turboquant": True, "kv_k": "q8_0", "kv_v": "q8_0", "auto_fit": False, "fit_margen": "512",
    "batch_size": "512", "ubatch_size": "256", "load_mode": "auto", "tipo_spec": "Ninguna",
    "spec_n_max": "", "spec_p_min": "", "moe_modo": "Ninguno", "moe_n_capas": "", "rope_modo": "Ninguno",
    "yarn_orig": "",
}
PERFILES_INCLUIDOS = {
    "★ ⚡ Rápido en mi GPU (el modelo cabe)": {
        "descripcion": "Todo el modelo en la GPU, contexto 8k y caché KV cuantizada. Lo más veloz cuando el\n"
                       "modelo cabe en tu VRAM (ej. un 27B en IQ2 corre a ~20 tok/s en una 2080 Ti).",
        "valores": dict(_BASE_RENDIMIENTO, contexto="8192", ngl="all"),
    },
    "★ 📚 Gran contexto y rápido": {
        "descripcion": "El motor calcula solo el contexto más grande que entra en tu VRAM libre (con 0.5 GB\n"
                       "de margen para que Windows no se cuelgue) y usa la caché KV cuantizada.",
        "valores": dict(_BASE_RENDIMIENTO, contexto="32768", ngl="auto", auto_fit=True, fit_margen="512"),
    },
    "★ 🐘 Modelo grande (solo lo que cabe en la GPU)": {
        "descripcion": "Para modelos más grandes que tu VRAM: sube a la GPU las capas que caben y deja el resto\n"
                       "en la RAM (la velocidad la limita tu RAM/CPU). Contexto automático con margen.",
        "valores": dict(_BASE_RENDIMIENTO, contexto="8192", ngl="auto", auto_fit=True, fit_margen="512",
                        batch_size="256", ubatch_size="128"),
    },
    "★ 🧩 Modelo MoE grande (expertos en la RAM)": {
        "descripcion": "Para modelos MoE (Nemotron 3 Nano 30B, Qwen 35B-A3B...): lo compartido va a la GPU y\n"
                       "los 'expertos' se quedan en la RAM, así se usa solo lo necesario. Lotes grandes (-ub 1024)\n"
                       "para leer prompts largos mucho más rápido. Aquí manda la RAM, más que la VRAM.",
        "valores": dict(_BASE_RENDIMIENTO, contexto="16384", ngl="all", auto_fit=True, fit_margen="512",
                        moe_modo="Todos los expertos en CPU (-cmoe)", batch_size="2048", ubatch_size="1024"),
    },
    "★ 🛡️ Seguro (no saturar la VRAM)": {
        "descripcion": "Contexto 4k, margen de 1 GB de VRAM libre y lotes chicos: para cuando usas la PC a la vez\n"
                       "(juegos, edición) o el sistema se pone lento al cargar un modelo.",
        "valores": dict(_BASE_RENDIMIENTO, contexto="4096", ngl="auto", auto_fit=True, fit_margen="1024",
                        batch_size="256", ubatch_size="128"),
    },
}

PRESETS_TURBOQUANT = {
    "Calidad máxima": {"activar": False, "k": "f16", "v": "f16"},
    "Balanceado (recomendado)": {"activar": True, "k": "q8_0", "v": "q8_0"},
    "Máximo ahorro VRAM": {"activar": True, "k": "q4_0", "v": "q4_0"},
}

# ---------------------------------------------------------------------------
# TEMAS DE COLOR
# ---------------------------------------------------------------------------
TEMA_POR_DEFECTO = "Azul Celeste ☀️"
PALETAS = {
    "Esmeralda 🌙": {
        "bg": "#0B0F0E", "panel": "#141C1A", "borde": "#22332C",
        "texto": "#E8F5F0", "texto_dim": "#8AA69C",
        "acento": "#1FAE7C", "acento_hover": "#2BD696", "acento_texto": "#04150F",
        "acento2": "#0E7C57",
        "ok": "#3FDD9B", "warn": "#E3B341", "peligro": "#F85149",
    },
    "Océano Neón 🌙": {
        "bg": "#070B14", "panel": "#101826", "borde": "#1E2E44",
        "texto": "#E7F0FF", "texto_dim": "#7F97B8",
        "acento": "#2E9CFF", "acento_hover": "#5CB6FF", "acento_texto": "#03111F",
        "acento2": "#1B5FA8",
        "ok": "#3FDD9B", "warn": "#E3B341", "peligro": "#FF5C7A",
    },
    "Atardecer 🌙": {
        "bg": "#120A08", "panel": "#1E120C", "borde": "#3A2317",
        "texto": "#FBEFE6", "texto_dim": "#C79A82",
        "acento": "#FF7A3D", "acento_hover": "#FF9A63", "acento_texto": "#1A0900",
        "acento2": "#B4471B",
        "ok": "#3FDD9B", "warn": "#FFC24B", "peligro": "#FF4D5E",
    },
    "Violeta Neón 🌙": {
        "bg": "#0C0A14", "panel": "#171226", "borde": "#2B2145",
        "texto": "#F1EBFF", "texto_dim": "#A493CC",
        "acento": "#A855F7", "acento_hover": "#C084FC", "acento_texto": "#140428",
        "acento2": "#6D28D9",
        "ok": "#3FDD9B", "warn": "#E3B341", "peligro": "#FB7185",
    },
    # Tema claro ("dia"). Antes usaba texto blanco sobre un verde medio en los
    # botones (contraste 2.6:1, ilegible) y ok/warn/peligro demasiado claros
    # sobre fondo blanco (<3.3:1). Corregido para cumplir WCAG AA (>=4.5:1)
    # en todas las combinaciones texto/fondo, siguiendo el mismo patron que
    # los temas oscuros: texto oscuro sobre acento vivo, nunca al reves.
    "Día ☀️": {
        "bg": "#FFFFFF", "panel": "#F4F6F5", "borde": "#DCE3E0",
        "texto": "#16211D", "texto_dim": "#5C6B65",
        "acento": "#17B37D", "acento_hover": "#3FDD9B", "acento_texto": "#04150F",
        "acento2": "#0B7A55",
        "ok": "#1B7E50", "warn": "#906909", "peligro": "#C33F3F",
    },
    # Tema por defecto del programa (estilo Apple, modo dia): fondo celeste
    # pastel muy claro, tarjetas blancas, texto casi negro y el azul de
    # sistema de Apple como acento (texto blanco encima, contraste 4.6:1).
    "Azul Celeste ☀️": {
        "bg": "#EEF5FC", "panel": "#FFFFFF", "borde": "#DCE7F2",
        "texto": "#1D1D1F", "texto_dim": "#6B7480",
        "acento": "#0071E3", "acento_hover": "#1F86F0", "acento_texto": "#FFFFFF",
        "acento2": "#0058B0",
        "ok": "#1B7E50", "warn": "#906909", "peligro": "#C33F3F",
    },
}


def cargar_tema_guardado():
    if os.path.isfile(ARCHIVO_TEMA):
        try:
            with open(ARCHIVO_TEMA, "r", encoding="utf-8") as f:
                datos = json.load(f)
            paleta = dict(PALETAS[TEMA_POR_DEFECTO])
            paleta.update(datos)
            return paleta
        except Exception:
            pass
    return dict(PALETAS[TEMA_POR_DEFECTO])


def guardar_tema(paleta):
    try:
        with open(ARCHIVO_TEMA, "w", encoding="utf-8") as f:
            json.dump(paleta, f, indent=2)
    except Exception:
        pass


def interpolar_hex(c1, c2, t):
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r = int(int(c1[0:2], 16) + (int(c2[0:2], 16) - int(c1[0:2], 16)) * t)
    g = int(int(c1[2:4], 16) + (int(c2[2:4], 16) - int(c1[2:4], 16)) * t)
    b = int(int(c1[4:6], 16) + (int(c2[4:6], 16) - int(c1[4:6], 16)) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _luminancia_relativa(color_hex):
    color_hex = color_hex.lstrip("#")
    r, g, b = [int(color_hex[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def _lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _lin(r), _lin(g), _lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste_wcag(c1, c2):
    l1 = _luminancia_relativa(c1) + 0.05
    l2 = _luminancia_relativa(c2) + 0.05
    return max(l1, l2) / min(l1, l2)


def _texto_legible_sobre(fondo_hex):
    """Blanco o negro, el que tenga mejor contraste sobre fondo_hex (WCAG)."""
    blanco, negro = "#FFFFFF", "#0A0A0A"
    if _contraste_wcag(fondo_hex, blanco) >= _contraste_wcag(fondo_hex, negro):
        return blanco
    return negro


def generar_paleta_desde_acento(acento_hex, modo_noche):
    """
    Combina un solo color de acento en una paleta completa (fondo, panel,
    bordes, texto...) para modo dia o modo noche, calculando siempre el
    color de texto con mejor contraste (WCAG) sobre cada fondo. Asi,
    cualquier color que el usuario elija se ve bien y las letras nunca
    quedan ilegibles, ya sea de dia o de noche.
    """
    # Estilo Apple: de dia, fondo con un toque del color y tarjetas blancas;
    # de noche, fondo casi negro y tarjetas gris oscuro, ambos teñidos apenas
    # con el acento elegido. El texto sale de un gris Apple (no del acento).
    if modo_noche:
        bg = interpolar_hex("#141416", acento_hex, 0.07)
        panel = interpolar_hex("#232326", acento_hex, 0.07)
        borde = interpolar_hex("#3A3A3F", acento_hex, 0.12)
        texto = interpolar_hex("#F5F5F7", acento_hex, 0.04)
        texto_dim = interpolar_hex("#A1A1A8", acento_hex, 0.08)
        ok, warn, peligro = "#3FDD9B", "#E3B341", "#F85149"
    else:
        bg = interpolar_hex(acento_hex, "#FFFFFF", 0.93)
        panel = "#FFFFFF"
        borde = interpolar_hex(acento_hex, "#FFFFFF", 0.86)
        texto = interpolar_hex("#1D1D1F", acento_hex, 0.05)
        texto_dim = interpolar_hex("#6B6B72", acento_hex, 0.10)
        ok, warn, peligro = "#1B7E50", "#906909", "#C33F3F"

    # Si el acento en si es demasiado claro (de noche) o demasiado oscuro
    # (de dia), se ajusta un poco para que siga resaltando como boton.
    acento_boton = acento_hex
    if modo_noche and _luminancia_relativa(acento_boton) < 0.12:
        acento_boton = interpolar_hex(acento_boton, "#FFFFFF", 0.35)
    elif not modo_noche and _luminancia_relativa(acento_boton) > 0.85:
        acento_boton = interpolar_hex(acento_boton, "#000000", 0.25)

    # Texto blanco sobre el boton (como Apple) siempre que se logre contraste
    # >= 4.5:1 oscureciendo el acento hasta un 30%; si no se logra, se usa el
    # texto (blanco o negro) con mejor contraste sobre el acento original.
    acento_texto = "#FFFFFF"
    if _contraste_wcag(acento_boton, "#FFFFFF") < 4.5:
        candidato = acento_boton
        for paso in range(1, 7):
            candidato = interpolar_hex(acento_boton, "#000000", paso * 0.05)
            if _contraste_wcag(candidato, "#FFFFFF") >= 4.5:
                break
        if _contraste_wcag(candidato, "#FFFFFF") >= 4.5:
            acento_boton = candidato
        else:
            acento_texto = _texto_legible_sobre(acento_boton)

    return {
        "bg": bg, "panel": panel, "borde": borde,
        "texto": texto, "texto_dim": texto_dim,
        "acento": acento_boton,
        "acento_hover": interpolar_hex(acento_boton, "#FFFFFF", 0.15),
        "acento_texto": acento_texto,
        "acento2": interpolar_hex(acento_boton, "#000000", 0.3),
        "ok": ok, "warn": warn, "peligro": peligro,
    }


# Version nocturna del tema por defecto (mismo azul, combinado para modo noche).
PALETAS["Azul Noche 🌙"] = generar_paleta_desde_acento("#0A84FF", True)


def buscar_binario(nombre):
    """Busca un ejecutable en la carpeta del programa o en el PATH del sistema."""
    ruta_local = os.path.join(CARPETA_BASE, nombre)
    if os.path.isfile(ruta_local):
        return ruta_local
    return shutil.which(nombre)


NVIDIA_SMI_PATH = buscar_binario("nvidia-smi.exe") or shutil.which("nvidia-smi")


def obtener_stats_gpu():
    """Lee uso de GPU/VRAM/temperatura via nvidia-smi. None si no hay GPU NVIDIA."""
    if not NVIDIA_SMI_PATH:
        return None
    try:
        salida = subprocess.check_output(
            [NVIDIA_SMI_PATH, "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name",
             "--format=csv,noheader,nounits"],
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=3, text=True,
        )
        partes = [p.strip() for p in salida.strip().splitlines()[0].split(",")]
        return {
            "uso_pct": float(partes[0]),
            "vram_usada_mb": float(partes[1]),
            "vram_total_mb": float(partes[2]),
            "temperatura_c": float(partes[3]),
            "nombre": partes[4],
        }
    except Exception:
        return None


def obtener_stats_sistema():
    """RAM y CPU del sistema, via psutil si esta disponible."""
    if psutil is None:
        return None
    try:
        ram = psutil.virtual_memory()
        return {
            "cpu_pct": psutil.cpu_percent(interval=None),
            "ram_usada_gb": ram.used / (1024**3),
            "ram_total_gb": ram.total / (1024**3),
            "ram_pct": ram.percent,
        }
    except Exception:
        return None


def comando_mcp_web_search():
    """Comando para relanzar este mismo programa en modo servidor MCP de
    busqueda web (ver el bloque al inicio del archivo). Funciona tanto
    compilado (interfaz_agentes.exe --mcp-web-search) como en desarrollo
    (python.exe interfaz_agentes.py --mcp-web-search)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mcp-web-search"]
    return [sys.executable, os.path.abspath(__file__), "--mcp-web-search"]


def escribir_config_mcp_web_search():
    """Genera el JSON (formato compatible con Cursor/llama-server) que le
    dice a llama-server como lanzar el servidor MCP de busqueda web, y
    devuelve la ruta del archivo."""
    config = {"mcpServers": {"busqueda_web": {"command": comando_mcp_web_search()[0], "args": comando_mcp_web_search()[1:]}}}
    ruta = os.path.join(CARPETA_BASE, "mcp_busqueda_web.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return ruta


def buscar_en_duckduckgo(consulta, max_resultados=5):
    """Busca en DuckDuckGo (sin API key) para la herramienta de búsqueda web
    del Chat/Playground. Import perezoso: solo carga requests/bs4 si de
    verdad se usa la herramienta."""
    import requests
    from bs4 import BeautifulSoup
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": consulta},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        sopa = BeautifulSoup(resp.text, "html.parser")
        resultados = []
        for bloque in sopa.select(".result")[:max(1, min(max_resultados, 10))]:
            titulo_tag = bloque.select_one(".result__title a")
            snippet_tag = bloque.select_one(".result__snippet")
            if not titulo_tag:
                continue
            titulo = titulo_tag.get_text(strip=True)
            url = titulo_tag.get("href", "")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            resultados.append(f"- {titulo}\n  {url}\n  {snippet}")
        return "\n\n".join(resultados) if resultados else "No se encontraron resultados."
    except Exception as e:
        return f"Error al buscar en la web: {e}"


def obtener_info_hardware():
    """Nombre del CPU, RAM total y GPU(s) detectadas sin depender de que sea
    NVIDIA (a diferencia de obtener_stats_gpu, que solo lee nvidia-smi).
    Sirve para que cualquiera que use el programa -con GPU de otra marca,
    o sin GPU dedicada- sepa que hardware se detecto, inspirado en el panel
    de hardware de Jan AI."""
    cpu_nombre = None
    try:
        import winreg
        clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu_nombre = winreg.QueryValueEx(clave, "ProcessorNameString")[0].strip()
    except Exception:
        cpu_nombre = platform.processor() or None

    gpus = []
    try:
        salida = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, text=True,
        )
        gpus = [linea.strip() for linea in salida.splitlines() if linea.strip()]
    except Exception:
        pass

    ram_total_gb = None
    if psutil is not None:
        try:
            ram_total_gb = psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            pass

    return {
        "cpu_nombre": cpu_nombre or "Desconocido",
        "cpu_nucleos": NUCLEOS_FISICOS_CPU,
        "ram_total_gb": ram_total_gb,
        "gpus": gpus,
    }


class AppAgentesia:
    def __init__(self, root):
        self.root = root
        self.root.title("Panel de Control - Agentes IA (llama.cpp + TurboQuant)")
        self.root.geometry("1160x720")
        self.root.minsize(980, 620)

        self.tema = cargar_tema_guardado()
        self._widgets_panel = []
        self._widgets_texto = []
        self._tarjetas = []
        self._repintado_tarjetas_job = None
        self._paginas = {}
        self._botones_sidebar = {}

        self.style = ttk.Style()
        self.style.theme_use("clam")

        # ---------- Estado: servidor / modelos ----------
        self.carpetas_modelos = cargar_carpetas_modelos()
        self.var_ruta_llama_server = tk.StringVar(value=cargar_ruta_llama_server())
        self.modelo_seleccionado = tk.StringVar()
        self.filtro_busqueda = tk.StringVar()
        self.var_contexto = tk.StringVar(value="8192")
        self.var_turboquant = tk.BooleanVar(value=True)
        self.var_kv_k = tk.StringVar(value="q8_0")
        self.var_kv_v = tk.StringVar(value="q8_0")
        self.var_ngl = tk.StringVar(value="auto")
        self.var_threads = tk.StringVar(value="")
        self.var_threads_batch = tk.StringVar(value="")
        self.var_batch_size = tk.StringVar(value="")
        self.var_ubatch_size = tk.StringVar(value="")
        self.var_no_mmap = tk.BooleanVar(value=False)
        self.var_load_mode = tk.StringVar(value="auto")
        self.var_lora = tk.StringVar(value="")
        self.var_lora_scale = tk.StringVar(value="")
        self.var_auto_fit = tk.BooleanVar(value=False)
        self.var_fit_margen = tk.StringVar(value="512")
        self.var_busqueda_web_tool = tk.BooleanVar(value=False)
        self.var_modo_fx = tk.BooleanVar(value=CPU_ES_AMD_FAMILIA15)
        self._hilos_fue_auto_fx = False

        # ---------- Estado: perfiles de configuracion ----------
        self.perfiles_guardados = cargar_perfiles()
        self.var_perfil_actual = tk.StringVar(value="")

        # ---------- Estado: proveedores en la nube (OpenAI/Claude/otros) ----------
        self.proveedores_nube = cargar_proveedores_nube()
        self.var_proveedor_chat = tk.StringVar(value="Local (llama.cpp)")
        self.var_prov_nombre = tk.StringVar(value="")
        self.var_prov_tipo = tk.StringVar(value="OpenAI / compatible")
        self.var_prov_base_url = tk.StringVar(value="")
        self.var_prov_api_key = tk.StringVar(value="")
        self.var_prov_modelo = tk.StringVar(value="")
        self.var_numa = tk.StringVar(value="ninguno")
        self.var_modelo_draft = tk.StringVar(value="")
        self.var_tipo_spec = tk.StringVar(value="Ninguna")
        self.var_spec_n_max = tk.StringVar(value="")
        self.var_spec_p_min = tk.StringVar(value="")
        self.var_spec_draft_ngl = tk.StringVar(value="")
        self.var_spec_draft_kv_k = tk.StringVar(value="")
        self.var_spec_draft_kv_v = tk.StringVar(value="")
        self.var_moe_modo = tk.StringVar(value="Ninguno")
        self.var_moe_n_capas = tk.StringVar(value="")
        self.var_mmproj = tk.StringVar(value="")

        # ---------- Estado: modo Router (varios modelos a la vez) ----------
        self.var_modo_router = tk.BooleanVar(value=False)
        self.var_models_max = tk.StringVar(value="")
        self.var_models_autoload = tk.BooleanVar(value=True)
        self.var_modelo_router_activo = tk.StringVar(value="")
        self.modelos_router_disponibles = []
        self.var_host = tk.StringVar(value="127.0.0.1")
        self.var_port = tk.StringVar(value="8080")
        self.endpoint_actual = tk.StringVar(value="")

        self.proceso_servidor = None
        self.servidor_listo = False
        self._anim_job = None
        self._anim_dots = 0
        self._pulso_job = None
        self._pulso_t = 0.0
        self._pulso_dir = 1

        # ---------- Estado: agentes (Crew) editable ----------
        self.var_rol_dev = tk.StringVar(value="Ingeniero de Software Senior")
        self.var_objetivo_dev = tk.StringVar(value="Escribir codigo en Python eficiente.")
        self.var_tarea_dev = tk.StringVar(value="Crea una cache LRU en Python.")
        self.var_rol_qa = tk.StringVar(value="Ingeniero de QA")
        self.var_objetivo_qa = tk.StringVar(value="Analizar bugs.")
        self.var_tarea_qa = tk.StringVar(value="Revisa el codigo anterior.")

        # ---------- Estado: chat / playground ----------
        self.var_chat_entrada = tk.StringVar()

        # ---------- Estado: tunel remoto ----------
        self.cloudflared_path = buscar_binario("cloudflared.exe")
        self.proceso_tunel = None
        self.var_url_tunel = tk.StringVar(value="")

        # ---------- Estado: seguridad del servidor (API key) ----------
        self.var_api_key = tk.StringVar(value="")
        self.var_cors_origins = tk.StringVar(value="*")

        # ---------- Estado: muestreo / anti-bucles, razonamiento, YaRN, dispositivos ----------
        self.var_temp = tk.StringVar(value="")
        self.var_top_p = tk.StringVar(value="")
        self.var_top_k = tk.StringVar(value="")
        self.var_min_p = tk.StringVar(value="")
        self.var_repeat_penalty = tk.StringVar(value="1.1")
        self.var_presence_penalty = tk.StringVar(value="")
        self.var_dry = tk.StringVar(value="")
        self.var_reasoning_budget = tk.StringVar(value="")
        self.var_rope_modo = tk.StringVar(value="Ninguno")
        self.var_yarn_orig = tk.StringVar(value="")
        self.var_dispositivos = tk.StringVar(value="")
        self.var_tensor_split = tk.StringVar(value="")
        self.var_split_mode = tk.StringVar(value="")
        self.var_main_gpu = tk.StringVar(value="")
        self.var_timeout = tk.StringVar(value="")

        # ---------- Estado: monitor en vivo ----------
        self._monitor_job = None
        self._barras_monitor = {}

        # ---------- Estado: descargar modelos (Hugging Face) ----------
        self.var_busqueda_hf = tk.StringVar()
        self.resultados_hf = []
        self.archivo_hf_seleccionado = None

        self._construir_ventana()
        self.aplicar_tema()
        self.cargar_modelos()
        self._iniciar_pulso_boton()
        self.mostrar_pagina("modelos")

        self.root.protocol("WM_DELETE_WINDOW", self.al_cerrar)

    # ==================================================================
    # VENTANA PRINCIPAL: header + sidebar + area de contenido
    # ==================================================================
    def _construir_ventana(self):
        self.header_canvas = tk.Canvas(self.root, height=76, highlightthickness=0, bd=0)
        self.header_canvas.pack(fill=tk.X, side=tk.TOP)
        self.header_canvas.bind("<Configure>", lambda e: self._redibujar_header())

        cuerpo = tk.Frame(self.root)
        cuerpo.pack(fill=tk.BOTH, expand=True)
        self._widgets_panel.append(("bg", cuerpo))

        # ---------------- Sidebar de navegacion ----------------
        self.sidebar = tk.Frame(cuerpo, width=224)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self._widgets_panel.append(("sidebar", self.sidebar))
        tk.Frame(self.sidebar, height=10).pack()  # aire arriba, como en macOS
        self._widgets_panel.append(("sidebar", self.sidebar.winfo_children()[-1]))

        # Linea fina que separa la barra lateral del contenido.
        self.separador_sidebar = tk.Frame(cuerpo, width=1)
        self.separador_sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._widgets_panel.append(("borde", self.separador_sidebar))

        modulos = [
            ("modelos", "🧩", "Modelos"),
            ("descargar", "🔍", "Descargar (Hugging Face)"),
            ("turboquant", "🧠", "TurboQuant"),
            ("monitor", "📊", "Monitor en vivo"),
            ("chat", "💬", "Chat / Playground"),
            ("proveedores", "☁️", "Proveedores en la nube"),
            ("agentes", "🤖", "Agentes (Crew)"),
            ("conexion", "🔌", "Conexión"),
            ("tunel", "🌐", "Túnel remoto"),
            ("apariencia", "🎨", "Apariencia"),
            ("acerca", "ℹ️", "Acerca de"),
        ]
        for clave, icono, etiqueta in modulos:
            self._crear_boton_sidebar(clave, icono, etiqueta)

        self.lbl_estado_sidebar = tk.Label(self.sidebar, text="Estado: Listo", font=("Segoe UI", 9), wraplength=196, justify="left", anchor="w")
        self.lbl_estado_sidebar.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=14)
        self._registrar_texto(self.lbl_estado_sidebar, "sidebar", dim=True)

        # ---------------- Area de contenido (paginas apiladas) ----------------
        self.area_contenido = tk.Frame(cuerpo)
        self.area_contenido.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._widgets_panel.append(("bg", self.area_contenido))

        self._paginas["modelos"] = self._pagina_modelos(self.area_contenido)
        self._paginas["descargar"] = self._pagina_descargar_hf(self.area_contenido)
        self._paginas["turboquant"] = self._pagina_turboquant(self.area_contenido)
        self._paginas["monitor"] = self._pagina_monitor(self.area_contenido)
        self._paginas["chat"] = self._pagina_chat(self.area_contenido)
        self._paginas["proveedores"] = self._pagina_proveedores(self.area_contenido)
        self._paginas["agentes"] = self._pagina_agentes(self.area_contenido)
        self._paginas["conexion"] = self._pagina_conexion(self.area_contenido)
        self._paginas["tunel"] = self._pagina_tunel(self.area_contenido)
        self._paginas["apariencia"] = self._pagina_apariencia(self.area_contenido)
        self._paginas["acerca"] = self._pagina_acerca(self.area_contenido)

        for pagina in self._paginas.values():
            pagina.place(in_=self.area_contenido, x=0, y=0, relwidth=1, relheight=1)

    def _color_sidebar(self):
        """Color de la barra lateral: un tono apenas distinto al del fondo."""
        t = self.tema
        return mezclar(t["bg"], t["borde"], 0.55)

    def _crear_boton_sidebar(self, clave, icono, etiqueta):
        b = BotonRedondo(
            self.sidebar, text=etiqueta, icono=icono, font=("Segoe UI", 10), anchor="w",
            padx=12, pady=9, radio=9, command=lambda: self.mostrar_pagina(clave),
        )
        b.pack(fill=tk.X, padx=10, pady=1)
        self._botones_sidebar[clave] = b

    def _estilo_sidebar(self, clave_activa=None):
        """Item activo en acento (redondeado); el resto transparente con hover suave."""
        t = self.tema
        fondo = self._color_sidebar()
        if clave_activa is None:
            clave_activa = getattr(self, "_pagina_actual", None)
        for k, b in self._botones_sidebar.items():
            if k == clave_activa:
                b.configure(bg=t["acento"], fg=t["acento_texto"],
                            activebackground=t["acento_hover"], activeforeground=t["acento_texto"])
            else:
                b.configure(bg=fondo, fg=t["texto"],
                            activebackground=mezclar(fondo, t["borde"], 0.7), activeforeground=t["texto"])

    def mostrar_pagina(self, clave):
        self._paginas[clave].tkraise()
        self._pagina_actual = clave
        self._estilo_sidebar(clave)

        if clave == "monitor":
            self._iniciar_monitor()
        else:
            self._detener_monitor()

    # ==================================================================
    # HEADER CON DEGRADADO
    # ==================================================================
    def _cargar_logo(self):
        if hasattr(self, "_logo_img"):
            return self._logo_img
        self._logo_img = None
        if os.path.isfile(RUTA_LOGO_JAGUAR):
            try:
                # Se reduce con Pillow (suavizado) a un tamano comodo para el encabezado.
                import base64
                import io
                from PIL import Image
                im = Image.open(RUTA_LOGO_JAGUAR).convert("RGBA").resize((46, 46), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "PNG")
                self._logo_img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
            except Exception:
                try:
                    self._logo_img = tk.PhotoImage(file=RUTA_LOGO_JAGUAR)
                except Exception:
                    self._logo_img = None
        return self._logo_img

    def _redibujar_header(self):
        """Encabezado plano estilo Apple: logo, titulo, subtitulo y una
        pastilla dia/noche a la derecha, con una linea fina abajo."""
        c = self.header_canvas
        t = self.tema
        c.delete("all")
        c.configure(bg=t["bg"])
        ancho = max(c.winfo_width(), 1)
        alto = max(c.winfo_height(), 1)
        c.create_line(0, alto - 1, ancho, alto - 1, fill=t["borde"])

        logo = self._cargar_logo()
        cy = alto // 2
        if logo is not None:
            c.create_image(24 + logo.width() // 2, cy, image=logo, anchor="center")
            texto_x = 24 + logo.width() + 14
        else:
            # Sin el logo (no se encontro el archivo): circulo con emoji de respaldo.
            cx, r = 46, 23
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=t["acento"], outline="")
            c.create_text(cx, cy, text="🐆", font=("Segoe UI Emoji", 18))
            texto_x = cx + r + 14

        c.create_text(texto_x, cy - 11, anchor="w", text="GMN AI", fill=t["texto"], font=("Segoe UI", 17, "bold"))
        c.create_text(texto_x, cy + 13, anchor="w", text="Panel de control · llama.cpp + TurboQuant · Creado por G.M.N TechLab",
                      fill=t["texto_dim"], font=("Segoe UI", 9))

        # Pastilla dia/noche (clic en cualquier lado la alterna).
        noche = self._modo_noche_actual()
        pw, ph, seg_w, seg_h = 80, 32, 36, 26
        x1, y1 = ancho - 24 - pw, cy - ph // 2
        pastilla = imagen_redondeada(pw, ph, ph // 2, t["panel"], t["borde"])
        activa = imagen_redondeada(seg_w, seg_h, seg_h // 2, t["acento"])
        self._imgs_header = [pastilla, activa]
        c.create_image(x1, y1, anchor="nw", image=pastilla, tags="toggle")
        sx = x1 + pw - 3 - seg_w if noche else x1 + 3
        c.create_image(sx, y1 + 3, anchor="nw", image=activa, tags="toggle")
        c.create_text(x1 + 3 + seg_w // 2, cy, text="☀️", font=("Segoe UI Emoji", 11), tags="toggle")
        c.create_text(x1 + pw - 3 - seg_w // 2, cy, text="🌙", font=("Segoe UI Emoji", 11), tags="toggle")
        c.tag_bind("toggle", "<Button-1>", lambda e: self.cambiar_modo_color(not self._modo_noche_actual()))
        c.tag_bind("toggle", "<Enter>", lambda e: c.configure(cursor="hand2"))
        c.tag_bind("toggle", "<Leave>", lambda e: c.configure(cursor=""))

    # ==================================================================
    # UTILIDADES DE CONSTRUCCION DE PAGINAS
    # ==================================================================
    def _nueva_pagina(self, padre, titulo, scrollable=True):
        pagina = tk.Frame(padre)
        self._widgets_panel.append(("bg", pagina))

        if scrollable:
            # Envuelve el contenido en un Canvas con barra de scroll vertical,
            # para que si el contenido crece hacia abajo y no cabe en la
            # ventana, se pueda desplazar en vez de quedar cortado.
            canvas_pag = tk.Canvas(pagina, highlightthickness=0)
            scrollbar_pag = ttk.Scrollbar(pagina, orient="vertical", command=canvas_pag.yview)
            canvas_pag.configure(yscrollcommand=scrollbar_pag.set)
            canvas_pag.pack(side="left", fill="both", expand=True)
            scrollbar_pag.pack(side="right", fill="y")
            self._widgets_panel.append(("bg", canvas_pag))

            interior = tk.Frame(canvas_pag)
            self._widgets_panel.append(("bg", interior))
            ventana_id = canvas_pag.create_window((0, 0), window=interior, anchor="nw")
            canvas_pag.bind("<Configure>", lambda e: canvas_pag.itemconfig(ventana_id, width=e.width))
            interior.bind("<Configure>", lambda e: canvas_pag.configure(scrollregion=canvas_pag.bbox("all")))

            def _rueda(ev, c=canvas_pag):
                c.yview_scroll(int(-1 * (ev.delta / 120)), "units")

            canvas_pag.bind("<Enter>", lambda e, c=canvas_pag, f=_rueda: c.bind_all("<MouseWheel>", f))
            canvas_pag.bind("<Leave>", lambda e, c=canvas_pag: c.unbind_all("<MouseWheel>"))

            contenido = tk.Frame(interior)
            contenido.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)
        else:
            contenido = tk.Frame(pagina)
            contenido.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

        self._widgets_panel.append(("bg", contenido))
        lbl = tk.Label(contenido, text=titulo, font=("Segoe UI", 20, "bold"))
        lbl.pack(anchor="w", pady=(0, 16))
        self._registrar_texto(lbl, "bg", subtitulo=True)
        return pagina, contenido

    def _crear_panel(self, padre, titulo=None):
        """Tarjeta redondeada (estilo Apple). Devuelve el contenedor interior
        donde van los widgets; el fondo redondeado se repinta solo."""
        exterior, interior, _fondo = crear_tarjeta(padre, radio=14)
        exterior.pack(fill=tk.X, pady=(0, 14))
        self._tarjetas.append(exterior)
        self._widgets_panel.append(("panel", interior))
        exterior.bind("<Configure>", lambda e: self._programar_repintado_tarjetas())
        if titulo:
            self._crear_subtitulo(interior, titulo).pack(anchor="w", padx=14, pady=(10, 4))
        return interior

    def _programar_repintado_tarjetas(self):
        """Repinta todas las tarjetas tras un instante (evita recalcular en
        cada pixel mientras se redimensiona la ventana)."""
        if self._repintado_tarjetas_job is not None:
            try:
                self.root.after_cancel(self._repintado_tarjetas_job)
            except Exception:
                pass
        self._repintado_tarjetas_job = self.root.after(70, self._repintar_tarjetas)

    def _repintar_tarjetas(self):
        self._repintado_tarjetas_job = None
        t = self.tema
        for exterior in self._tarjetas:
            try:
                if exterior.winfo_ismapped():
                    pintar_tarjeta(exterior, t["panel"], t["borde"], t["bg"])
            except tk.TclError:
                pass

    def _crear_subtitulo(self, padre, texto):
        lbl = tk.Label(padre, text=texto, font=("Segoe UI", 11, "bold"))
        self._registrar_texto(lbl, "panel", subtitulo=True)
        return lbl

    def _crear_label_card(self, padre, texto):
        lbl = tk.Label(padre, text=texto, font=("Segoe UI", 10))
        self._registrar_texto(lbl, "panel")
        return lbl

    def _crear_label_dim(self, padre, texto, fondo="panel", **kw):
        lbl = tk.Label(padre, text=texto, font=("Segoe UI", 9), justify="left", **kw)
        self._registrar_texto(lbl, fondo, dim=True)
        return lbl

    def _crear_boton(self, padre, texto, comando, primario=False, **kw):
        # Boton redondeado; el color real (primario/secundario) lo asigna aplicar_tema.
        b = BotonRedondo(padre, text=texto, command=comando,
                         font=("Segoe UI", 10, "bold" if primario else "normal"),
                         padx=16, pady=7, radio=10, **kw)
        b._primario = primario
        return b

    # Estilos de boton reutilizables (los usa aplicar_tema para colorear todo igual).
    def _est_primario(self):
        t = self.tema
        return dict(bg=t["acento"], fg=t["acento_texto"], activebackground=t["acento_hover"], activeforeground=t["acento_texto"])

    def _est_secundario(self):
        t = self.tema
        return dict(bg=t["borde"], fg=t["texto"], activebackground=mezclar(t["borde"], t["texto"], 0.12), activeforeground=t["texto"])

    def _est_peligro(self):
        t = self.tema
        base = mezclar(t["panel"], t["peligro"], 0.12)
        return dict(bg=base, fg=t["peligro"], activebackground=mezclar(t["panel"], t["peligro"], 0.24), activeforeground=t["peligro"])

    def _crear_entry_config(self, padre, etiqueta, variable, fila, ancho=18):
        self._crear_label_card(padre, etiqueta).grid(row=fila, column=0, sticky="w", padx=12, pady=6)
        e = ttk.Entry(padre, textvariable=variable, width=ancho)
        e.grid(row=fila, column=1, sticky="w", padx=12, pady=6)
        return e

    def _registrar_texto(self, widget, fondo_clave, dim=False, subtitulo=False):
        self._widgets_texto.append((widget, fondo_clave, dim, subtitulo))

    # ==================================================================
    # PAGINA: MODELOS
    # ==================================================================
    def _pagina_modelos(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🧩 Selector de modelos GGUF", scrollable=False)

        # ---- Zona inferior fija: se empaqueta PRIMERO con side=BOTTOM para
        # que su espacio quede siempre reservado y el boton de cargar nunca
        # quede empujado fuera de la ventana, sin importar cuanto contenido
        # haya arriba (carpetas, lista de modelos, etc.). ----
        self.lbl_estado = tk.Label(contenido, text="Estado: Listo para iniciar.", font=("Segoe UI", 10, "italic"), wraplength=700, justify="left")
        self.lbl_estado.pack(side=tk.BOTTOM, anchor=tk.W, fill=tk.X, pady=(6, 0))
        self._registrar_texto(self.lbl_estado, "bg", dim=True)

        fila_botones = tk.Frame(contenido)
        fila_botones.pack(side=tk.BOTTOM, fill=tk.X)
        self._widgets_panel.append(("bg", fila_botones))

        self.btn_detener = self._crear_boton(fila_botones, "⏹ Detener servidor", self.detener_servidor, state=tk.DISABLED)
        self.btn_detener.pack(fill=tk.X, pady=(0, 8))

        self.btn_iniciar = self._crear_boton(fila_botones, "🚀 Cargar modelo (1 clic)", self.iniciar_todo_hilo, primario=True)
        self.btn_iniciar.configure(font=("Segoe UI", 12, "bold"), pady=12)
        self.btn_iniciar.pack(fill=tk.X, pady=(0, 8))
        self.btn_iniciar.bind("<Enter>", self.on_enter_btn)
        self.btn_iniciar.bind("<Leave>", self.on_leave_btn)

        self.lbl_leyenda = tk.Label(contenido, text="🟢 Cabe cómodo en 11GB   🟡 Ajustado (baja el contexto)   🔴 Puede no caber en VRAM", font=("Segoe UI", 9, "italic"))
        self.lbl_leyenda.pack(side=tk.BOTTOM, anchor=tk.W, pady=(6, 10))
        self._registrar_texto(self.lbl_leyenda, "bg", dim=True)

        # ---- Zona superior: se estira/encoge segun el espacio que quede ----
        # Panel compacto de carpetas (una sola fila: lista + botones al lado,
        # en vez de apilados, para dejarle todo el espacio posible a la lista
        # de modelos de abajo, que es lo importante en esta pagina). La ruta
        # de llama-server.exe se configura en la pagina "TurboQuant".
        panel_carpetas = self._crear_panel(contenido, "📁 Carpetas donde buscar modelos (.gguf)")
        fila_carpetas = tk.Frame(panel_carpetas)
        fila_carpetas.pack(fill=tk.X, padx=12, pady=(0, 10))
        self._widgets_panel.append(("panel", fila_carpetas))

        self.lista_carpetas = tk.Listbox(fila_carpetas, height=2, font=("Segoe UI", 9), bd=1, relief="solid",
                                          selectmode=tk.SINGLE, exportselection=False, highlightthickness=0)
        self.lista_carpetas.pack(side=tk.LEFT, fill=tk.X, expand=True)

        fila_btns_carpetas = tk.Frame(fila_carpetas)
        fila_btns_carpetas.pack(side=tk.LEFT, padx=(8, 0))
        self._widgets_panel.append(("panel", fila_btns_carpetas))
        self.btn_agregar_carpeta = self._crear_boton(fila_btns_carpetas, "➕ Agregar", self.agregar_carpeta_modelos)
        self.btn_agregar_carpeta.pack(fill=tk.X, pady=(0, 4))
        self.btn_quitar_carpeta = self._crear_boton(fila_btns_carpetas, "🗑 Quitar", self.quitar_carpeta_modelos)
        self.btn_quitar_carpeta.pack(fill=tk.X)

        self._refrescar_lista_carpetas()

        fila_router = tk.Frame(contenido)
        fila_router.pack(fill=tk.X, pady=(0, 8))
        self._widgets_panel.append(("bg", fila_router))
        self.chk_modo_router = tk.Checkbutton(
            fila_router, text="🔀 Modo Router: servir varios modelos a la vez (cambia sin reiniciar)",
            variable=self.var_modo_router, font=("Segoe UI", 9, "bold"), bd=0, highlightthickness=0,
            command=self._al_cambiar_modo_router,
        )
        self.chk_modo_router.pack(anchor="w")
        self._widgets_panel.append(("check_bg", self.chk_modo_router))

        self.fila_opciones_router = tk.Frame(contenido)
        self._widgets_panel.append(("bg", self.fila_opciones_router))
        lbl_mmax = tk.Label(self.fila_opciones_router, text="Máx. modelos a la vez:")
        lbl_mmax.pack(side=tk.LEFT, padx=(20, 4))
        self._registrar_texto(lbl_mmax, "bg", dim=True)
        ttk.Combobox(self.fila_opciones_router, textvariable=self.var_models_max, values=["", "1", "2", "3", "4", "6", "8"], width=6).pack(side=tk.LEFT, padx=(0, 12))
        self.chk_models_autoload = tk.Checkbutton(
            self.fila_opciones_router, text="Auto-cargar el modelo que pida cada request",
            variable=self.var_models_autoload, font=("Segoe UI", 9), bd=0, highlightthickness=0,
        )
        self.chk_models_autoload.pack(side=tk.LEFT)
        self._widgets_panel.append(("check_bg", self.chk_models_autoload))
        # Solo tiene sentido con el Router activo; se muestra/oculta junto con el.

        buscador = tk.Frame(contenido)
        buscador.pack(fill=tk.X, pady=(0, 8))
        self._widgets_panel.append(("bg", buscador))
        lbl_lupa = tk.Label(buscador, text="🔎")
        lbl_lupa.pack(side=tk.LEFT, padx=(0, 6))
        self._registrar_texto(lbl_lupa, "bg")
        entrada_busq = ttk.Entry(buscador, textvariable=self.filtro_busqueda)
        entrada_busq.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entrada_busq.bind("<KeyRelease>", lambda e: self.filtrar_modelos())
        self._crear_boton(buscador, "↻ Refrescar", self.cargar_modelos).pack(side=tk.LEFT, padx=(8, 0))

        self.canvas_frame = tk.Frame(contenido, bd=1, relief="solid")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self._widgets_panel.append(("panel_borde", self.canvas_frame))

        self.canvas = tk.Canvas(self.canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.frame_modelos = tk.Frame(self.canvas)
        self._widgets_panel.append(("panel", self.canvas))
        self._widgets_panel.append(("panel", self.frame_modelos))

        self.frame_modelos.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._ventana_canvas = self.canvas.create_window((0, 0), window=self.frame_modelos, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._ventana_canvas, width=e.width))
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return pagina

    # ==================================================================
    # PAGINA: TURBOQUANT + CONFIG SERVIDOR
    # ==================================================================
    def _pagina_turboquant(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🧠 TurboQuant y configuración del servidor")

        panel_perfiles = self._crear_panel(contenido, "💾 Perfiles de configuración")
        # Botones de un clic para los perfiles incluidos (los mismos de la lista).
        fila_rapidos = tk.Frame(panel_perfiles)
        fila_rapidos.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._widgets_panel.append(("panel", fila_rapidos))
        for nombre_perfil in PERFILES_INCLUIDOS:
            corto = nombre_perfil.replace("★ ", "").split(" (")[0]
            self._crear_boton(
                fila_rapidos, corto, lambda n=nombre_perfil: (self.var_perfil_actual.set(n), self._al_elegir_perfil()),
            ).pack(side=tk.LEFT, padx=(0, 6))
        fila_perfiles = tk.Frame(panel_perfiles)
        fila_perfiles.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel", fila_perfiles))
        self.combo_perfiles = ttk.Combobox(
            fila_perfiles, textvariable=self.var_perfil_actual,
            values=self._nombres_perfiles(), width=44,
        )
        self.combo_perfiles.pack(side=tk.LEFT, padx=(0, 8))
        self.combo_perfiles.bind("<<ComboboxSelected>>", lambda e: self._al_elegir_perfil())
        self._crear_boton(fila_perfiles, "📥 Cargar", self.cargar_perfil_seleccionado).pack(side=tk.LEFT, padx=(0, 6))
        self._crear_boton(fila_perfiles, "💾 Guardar", self.guardar_perfil_actual, primario=True).pack(side=tk.LEFT, padx=(0, 6))
        self._crear_boton(fila_perfiles, "🗑 Eliminar", self.eliminar_perfil_seleccionado).pack(side=tk.LEFT)
        self.lbl_desc_perfil = self._crear_label_dim(panel_perfiles, "Elige un perfil con ★ para aplicarlo al instante (⚡ rápido, 📚 gran contexto, 🐘 modelo grande, 🧩 MoE, 🛡️ seguro).")
        self.lbl_desc_perfil.pack(anchor="w", padx=12, pady=(0, 6))
        self._crear_label_dim(
            panel_perfiles,
            "Escribe un nombre nuevo (o elige uno existente) y presiona 'Guardar' para\n"
            "recordar TODA la configuración de esta página (modelo, -ngl, hilos, caché KV,\n"
            "LoRA, modo FX, etc.) — 'Cargar' la vuelve a aplicar con un clic. Útil para\n"
            "alternar, por ejemplo, entre un perfil 'máxima velocidad' y otro 'máximo\n"
            "contexto' sin tener que volver a tocar cada campo.",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        panel_llama = self._crear_panel(contenido, "🦙 Ubicación de llama-server.exe")
        fila_llama = tk.Frame(panel_llama)
        fila_llama.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_llama))
        self.entrada_ruta_llama = ttk.Entry(fila_llama, textvariable=self.var_ruta_llama_server, state="readonly")
        self.entrada_ruta_llama.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self._crear_boton(fila_llama, "📂 Cambiar...", self.cambiar_ruta_llama_server).pack(side=tk.LEFT, padx=(8, 0))

        panel_cfg = self._crear_panel(contenido, "⚙️ Configuración del servidor")
        grid_cfg = tk.Frame(panel_cfg)
        grid_cfg.pack(fill=tk.X, pady=(0, 10))
        self._widgets_panel.append(("panel", grid_cfg))
        self._crear_entry_config(grid_cfg, "Host:", self.var_host, 0)
        self._crear_entry_config(grid_cfg, "Puerto:", self.var_port, 1)
        self._crear_label_card(grid_cfg, "Contexto (tokens):").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(grid_cfg, textvariable=self.var_contexto, values=CONTEXTOS, width=15).grid(row=2, column=1, sticky="w", padx=12, pady=6)
        self._crear_label_card(grid_cfg, "Capas en GPU (-ngl):").grid(row=3, column=0, sticky="w", padx=12, pady=6)
        combo_ngl = ttk.Combobox(grid_cfg, textvariable=self.var_ngl, values=["auto", "all", "20", "28", "36", "40", "48", "60"], width=15)
        combo_ngl.grid(row=3, column=1, sticky="w", padx=12, pady=6)
        self._crear_label_card(grid_cfg, "Hilos de CPU (-t):").grid(row=4, column=0, sticky="w", padx=12, pady=(6, 12))
        ttk.Entry(grid_cfg, textvariable=self.var_threads, width=17).grid(row=4, column=1, sticky="w", padx=12, pady=(6, 12))

        self._crear_label_dim(
            panel_cfg,
            f"💡 '-ngl' acepta un número exacto (no solo auto/all): empieza bajo (ej. 20) y\n"
            f"sube de a poco mientras miras la pestaña 'Monitor en vivo' — cuando la VRAM\n"
            f"llegue a 90–95%, ya no subas más. Deja 'Hilos de CPU' vacío para que decida\n"
            f"solo, o pon el número de núcleos físicos de tu CPU (detectados: {NUCLEOS_FISICOS_CPU}).",
        ).pack(anchor="w", padx=12, pady=(0, 6))

        self.chk_auto_fit = tk.Checkbutton(
            panel_cfg, text="--fit: dejar que llama.cpp ajuste el contexto solo para que quepa en la VRAM",
            variable=self.var_auto_fit, font=("Segoe UI", 9), bd=0, highlightthickness=0,
        )
        self.chk_auto_fit.pack(anchor="w", padx=12, pady=(0, 4))
        self._widgets_panel.append(("check", self.chk_auto_fit))
        self._crear_label_dim(
            panel_cfg,
            "Si lo activas, se ignora el 'Contexto (tokens)' de arriba y el propio motor de\n"
            "llama.cpp calcula el contexto máximo que entra en tu VRAM libre (función nueva\n"
            "del motor, disponible desde versiones recientes de llama-server.exe).",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        fila_fit_margen = tk.Frame(panel_cfg)
        fila_fit_margen.pack(fill=tk.X, padx=12, pady=(0, 4))
        self._widgets_panel.append(("panel", fila_fit_margen))
        self._crear_label_card(fila_fit_margen, "Margen de VRAM libre a reservar (MB):").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(fila_fit_margen, textvariable=self.var_fit_margen, values=["256", "512", "1024", "2048"], width=10).pack(side=tk.LEFT)
        self._crear_label_dim(
            panel_cfg,
            "Se usa junto con el modo automático de arriba: le dice al motor que deje esa\n"
            "cantidad de VRAM sin usar (además del modelo y el contexto), para que Windows y\n"
            "el resto del sistema no se queden sin memoria de video — si la VRAM se satura\n"
            "por completo, puede colgar o hacer pantallazo el sistema. 512 MB (0.5 GB) es un\n"
            "margen razonable para la mayoría de PCs; súbelo si igual ves problemas.",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        panel_perf = self._crear_panel(contenido, "⚡ Rendimiento avanzado (opcional)")
        grid_perf = tk.Frame(panel_perf)
        grid_perf.pack(fill=tk.X, pady=(0, 6))
        self._widgets_panel.append(("panel", grid_perf))
        self._crear_label_card(grid_perf, "Hilos para batch (-tb):").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(grid_perf, textvariable=self.var_threads_batch, width=17).grid(row=0, column=1, sticky="w", padx=12, pady=6)
        self._crear_label_card(grid_perf, "Batch size (-b):").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(grid_perf, textvariable=self.var_batch_size, values=["", "256", "512", "1024", "2048"], width=15).grid(row=1, column=1, sticky="w", padx=12, pady=6)
        self._crear_label_card(grid_perf, "Ubatch size (-ub):").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(grid_perf, textvariable=self.var_ubatch_size, values=["", "128", "256", "512", "1024", "2048"], width=15).grid(row=2, column=1, sticky="w", padx=12, pady=6)
        self._crear_label_card(grid_perf, "Tip: en modelos MoE grandes, un ubatch de 1024 o más acelera mucho la lectura del prompt\n"
                                          "(ej. un prompt de 32k). Usa algo más de VRAM; con el auto-ajuste queda margen. Con MoE, la RAM manda más que la VRAM.").grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))
        self._crear_label_card(grid_perf, "NUMA (--numa):").grid(row=3, column=0, sticky="w", padx=12, pady=(6, 12))
        ttk.Combobox(grid_perf, textvariable=self.var_numa, values=["ninguno", "distribute", "isolate", "numactl"], state="readonly", width=15).grid(row=3, column=1, sticky="w", padx=12, pady=(6, 12))

        fila_load_mode = tk.Frame(panel_perf)
        fila_load_mode.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel", fila_load_mode))
        self._crear_label_card(fila_load_mode, "Modo de carga (--load-mode):").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(
            fila_load_mode, textvariable=self.var_load_mode, state="readonly", width=12,
            values=["auto", "none", "mmap", "mlock"],
        ).pack(side=tk.LEFT)

        fila_fx = tk.Frame(panel_perf)
        fila_fx.pack(fill=tk.X, padx=12, pady=(10, 0))
        self._widgets_panel.append(("panel", fila_fx))
        self.chk_modo_fx = tk.Checkbutton(
            fila_fx, text="🧬 Modo FX-8320E: usar rutinas nativas AVX + FMA4 (sin AVX2/FMA3)",
            variable=self.var_modo_fx, font=("Segoe UI", 9, "bold"), bd=0, highlightthickness=0,
            command=self._al_cambiar_modo_fx,
        )
        self.chk_modo_fx.pack(anchor="w")
        self._widgets_panel.append(("check", self.chk_modo_fx))
        self.lbl_estado_fx = self._crear_label_dim(panel_perf, "")
        self.lbl_estado_fx.pack(anchor="w", padx=12, pady=(2, 6))
        self._al_cambiar_modo_fx()

        self._crear_label_dim(
            panel_perf,
            "Deja los campos vacíos para usar los valores por defecto de llama.cpp — solo\n"
            "tócalos si sabes lo que buscas (bajar 'batch size' reduce picos de VRAM;\n"
            "'--numa' ayuda en CPUs con varios chiplets, ej. Ryzen/EPYC). 'mlock' fuerza a\n"
            "mantener el modelo en RAM sin comprimir/swap; 'none' desactiva mmap (úsalo si\n"
            "el modelo no cabe en RAM+VRAM juntas).",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        panel_lora = self._crear_panel(contenido, "🎛️ Adaptador LoRA (opcional)")
        self._crear_label_dim(
            panel_lora,
            "Aplica un fine-tune ligero (LoRA) sobre el modelo base sin necesitar el modelo\n"
            "completo ya fusionado. Deja vacío si no vas a usar uno.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        fila_lora = tk.Frame(panel_lora)
        fila_lora.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel", fila_lora))
        self.entrada_lora = ttk.Entry(fila_lora, textvariable=self.var_lora, state="readonly")
        self.entrada_lora.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self._crear_boton(fila_lora, "📂 Elegir...", self.elegir_lora).pack(side=tk.LEFT, padx=(8, 0))
        self._crear_boton(fila_lora, "🗑 Quitar", self.quitar_lora).pack(side=tk.LEFT, padx=(6, 0))
        fila_lora_escala = tk.Frame(panel_lora)
        fila_lora_escala.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_lora_escala))
        self._crear_label_card(fila_lora_escala, "Escala (opcional, ej. 0.8):").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(fila_lora_escala, textvariable=self.var_lora_scale, width=10).pack(side=tk.LEFT)

        panel_moe = self._crear_panel(contenido, "🧩 Modelos MoE grandes en poca VRAM (opcional)")
        self._crear_label_dim(
            panel_moe,
            "Para modelos 'Mixture of Experts' (ej. Qwen3.6-35B-A3B, Mixtral, GLM): deja los\n"
            "'expertos' en RAM y solo lo compartido en GPU — permite cargar modelos mucho\n"
            "más grandes que tu VRAM, a cambio de algo de velocidad. Si el modelo no es MoE,\n"
            "esto no hace nada.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        fila_moe = tk.Frame(panel_moe)
        fila_moe.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_moe))
        self._crear_label_card(fila_moe, "Modo:").grid(row=0, column=0, sticky="w", pady=4)
        combo_moe = ttk.Combobox(
            fila_moe, textvariable=self.var_moe_modo, state="readonly", width=28,
            values=["Ninguno", "Todos los expertos en CPU (-cmoe)", "Primeras N capas en CPU (-ncmoe)"],
        )
        combo_moe.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)
        combo_moe.bind("<<ComboboxSelected>>", lambda e: self._actualizar_estado_moe())
        self._crear_label_card(fila_moe, "N capas:").grid(row=1, column=0, sticky="w", pady=4)
        self.entrada_moe_n = ttk.Entry(fila_moe, textvariable=self.var_moe_n_capas, width=8)
        self.entrada_moe_n.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)
        self._actualizar_estado_moe()

        self._crear_label_dim(
            panel_moe,
            "Atajo para modelos grandes y rápidos (ej. NVIDIA Nemotron 3 Nano 30B, Qwen 35B-A3B):\n"
            "activa el ajuste automático de contexto a la VRAM (con margen de seguridad), la caché\n"
            "KV cuantizada y el reparto automático de capas, para que el motor decida qué entra en\n"
            "la GPU y qué va a la RAM. Solo toca esas opciones; luego puedes afinarlas a mano.",
        ).pack(anchor="w", padx=12, pady=(0, 6))
        self._crear_boton(panel_moe, "⚡ Preset: modelo grande rápido", self.aplicar_preset_modelo_grande).pack(
            anchor="w", padx=12, pady=(0, 12))

        panel_vision = self._crear_panel(contenido, "👁️ Modelo de visión (opcional)")
        self._crear_label_dim(
            panel_vision,
            "Si el modelo que cargas es multimodal (ej. Liquid LFM2.5-VL), elige aquí su\n"
            "archivo 'mmproj' — normalmente viene junto al modelo, con 'mmproj' en el nombre.",
        ).pack(anchor="w", padx=12, pady=(0, 6))
        fila_mmproj = tk.Frame(panel_vision)
        fila_mmproj.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_mmproj))
        self.entrada_mmproj = ttk.Entry(fila_mmproj, textvariable=self.var_mmproj, state="readonly")
        self.entrada_mmproj.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self._crear_boton(fila_mmproj, "📂 Elegir...", self.elegir_mmproj).pack(side=tk.LEFT, padx=(8, 0))
        self._crear_boton(fila_mmproj, "🗑 Quitar", lambda: self.var_mmproj.set("")).pack(side=tk.LEFT, padx=(6, 0))

        panel_spec = self._crear_panel(contenido, "🚀 Decodificación especulativa (opcional)")
        self._crear_label_dim(
            panel_spec,
            "Acelera la generación adivinando varios tokens de una vez y dejando que el\n"
            "modelo grande solo los valide. 'N-gram' no necesita un modelo extra (usa el\n"
            "propio contexto) — ideal para código/JSON repetitivo. 'Con modelo draft'\n"
            "suele ser más rápido pero necesita un modelo chiquito (0.5B–1.5B) compatible.",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        fila_tipo_spec = tk.Frame(panel_spec)
        fila_tipo_spec.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._widgets_panel.append(("panel", fila_tipo_spec))
        self._crear_label_card(fila_tipo_spec, "Tipo:").pack(side=tk.LEFT)
        combo_spec = ttk.Combobox(
            fila_tipo_spec, textvariable=self.var_tipo_spec, state="readonly", width=32,
            values=["Ninguna", "N-gram simple (sin modelo extra)", "N-gram caché (sin modelo extra)", "MTP (sin modelo extra)", "Con modelo draft"],
        )
        combo_spec.pack(side=tk.LEFT, padx=(8, 0))
        combo_spec.bind("<<ComboboxSelected>>", lambda e: self._actualizar_estado_draft())

        fila_draft = tk.Frame(panel_spec)
        fila_draft.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_draft))
        self.entrada_modelo_draft = ttk.Entry(fila_draft, textvariable=self.var_modelo_draft, state="readonly")
        self.entrada_modelo_draft.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.btn_elegir_draft = self._crear_boton(fila_draft, "📂 Elegir...", self.elegir_modelo_draft)
        self.btn_elegir_draft.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_quitar_draft = self._crear_boton(fila_draft, "🗑 Quitar", self.quitar_modelo_draft)
        self.btn_quitar_draft.pack(side=tk.LEFT, padx=(6, 0))
        self._actualizar_estado_draft()

        fila_spec_fino = tk.Frame(panel_spec)
        fila_spec_fino.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel", fila_spec_fino))
        self._crear_label_card(fila_spec_fino, "Tokens a adivinar por pasada:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(fila_spec_fino, textvariable=self.var_spec_n_max, values=["", "1", "2", "3", "4", "6", "8", "12", "16"], width=10).grid(row=0, column=1, sticky="w", pady=4)
        self._crear_label_card(fila_spec_fino, "Umbral mínimo de aceptación:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(fila_spec_fino, textvariable=self.var_spec_p_min, values=["", "0.0", "0.1", "0.3", "0.5", "0.7", "0.9"], width=10).grid(row=1, column=1, sticky="w", pady=4)
        self._crear_label_dim(
            panel_spec,
            "Ajuste fino (opcional, deja vacío para usar los valores por defecto del motor):\n"
            "más tokens por pasada = más rápido SI acierta seguido, pero desperdicia más\n"
            "trabajo si falla. Un umbral de aceptación más alto exige que el modelo grande\n"
            "esté más seguro para aceptar lo adivinado (menos errores, menos velocidad).",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        # --- GPU layers + KV caché del modelo draft ---
        fila_draft_gpu = tk.Frame(panel_spec)
        fila_draft_gpu.pack(fill=tk.X, padx=12, pady=(0, 4))
        self._widgets_panel.append(("panel", fila_draft_gpu))
        self._crear_label_card(fila_draft_gpu, "GPU layers del modelo draft (--spec-draft-ngl):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(fila_draft_gpu, textvariable=self.var_spec_draft_ngl,
                     values=["", "all", "0", "1", "4", "8", "16", "24", "32"], width=10).grid(row=0, column=1, sticky="w", pady=4)
        self._crear_label_card(fila_draft_gpu, "KV caché del draft — K (--spec-draft-type-k):").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(fila_draft_gpu, textvariable=self.var_spec_draft_kv_k,
                     values=["", "f16", "q8_0", "q4_0"], width=10, state="readonly").grid(row=1, column=1, sticky="w", pady=4)
        self._crear_label_card(fila_draft_gpu, "KV caché del draft — V (--spec-draft-type-v):").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(fila_draft_gpu, textvariable=self.var_spec_draft_kv_v,
                     values=["", "f16", "q8_0", "q4_0"], width=10, state="readonly").grid(row=2, column=1, sticky="w", pady=4)
        self._crear_label_dim(
            panel_spec,
            "GPU layers del draft: cuántas capas del modelo chiquito van a la GPU. 'all' = todo\n"
            "en la GPU (más rápido). Si lo dejas vacío el motor decide solo.\n"
            "KV caché del draft: tipo de memoria para el historial del modelo chiquito. 'f16'\n"
            "= máxima precisión (recomendado para drafts), 'q8_0'/'q4_0' = menos VRAM pero\n"
            "puede reducir la tasa de aceptación. Si lo dejas vacío usa q8_0 por defecto.",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        # ---------- Muestreo y anti-bucles (+ presupuesto de razonamiento) ----------
        panel_muestreo = self._crear_panel(contenido, "🎚️ Muestreo y anti-bucles (opcional)")
        self._crear_label_dim(
            panel_muestreo,
            "Controla qué tan creativo o repetitivo es el modelo. Si se queda en bucles\n"
            "(repite la misma frase sin parar), prueba el preset 'Anti-bucles'. Los clientes\n"
            "(Cline, Continue...) pueden mandar sus propios valores y ganarle a estos.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        fila_presets_m = tk.Frame(panel_muestreo)
        fila_presets_m.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._widgets_panel.append(("panel", fila_presets_m))
        for nombre_preset in PRESETS_MUESTREO:
            self._crear_boton(
                fila_presets_m, nombre_preset, lambda n=nombre_preset: self.aplicar_preset_muestreo(n),
            ).pack(side=tk.LEFT, padx=(0, 6))
        grid_m = tk.Frame(panel_muestreo)
        grid_m.pack(fill=tk.X, padx=6, pady=(0, 6))
        self._widgets_panel.append(("panel", grid_m))
        campos_m = [
            ("Temperatura:", self.var_temp, ["", "0.2", "0.4", "0.6", "0.8", "1.0"]),
            ("Top-p:", self.var_top_p, ["", "0.8", "0.9", "0.95", "1.0"]),
            ("Top-k:", self.var_top_k, ["", "20", "40", "64"]),
            ("Min-p:", self.var_min_p, ["", "0.0", "0.05", "0.1"]),
            ("Penaliz. repetición:", self.var_repeat_penalty, ["", "1.0", "1.05", "1.1", "1.15", "1.2"]),
            ("Penaliz. presencia:", self.var_presence_penalty, ["", "0.0", "0.5", "1.0", "1.5"]),
            ("DRY (anti-bucles):", self.var_dry, ["", "0.4", "0.8", "1.2"]),
            ("Razonamiento (tokens):", self.var_reasoning_budget, ["", "0", "512", "1024", "2048", "4096"]),
        ]
        for i, (etiqueta, variable, valores) in enumerate(campos_m):
            fila, col = divmod(i, 2)
            self._crear_label_card(grid_m, etiqueta).grid(row=fila, column=col * 2, sticky="w", padx=(12, 6), pady=5)
            ttk.Combobox(grid_m, textvariable=variable, values=valores, width=9).grid(
                row=fila, column=col * 2 + 1, sticky="w", padx=(0, 18), pady=5)
        self._crear_label_dim(
            panel_muestreo,
            "Vacío = valor por defecto del motor. 'DRY' castiga las frases que se repiten\n"
            "(0.8 es lo habitual). 'Razonamiento' limita cuántos tokens puede 'pensar' un\n"
            "modelo con razonamiento antes de responder (0 = no pensar; vacío = sin límite),\n"
            "útil cuando un modelo se agota pensando y deja la respuesta vacía.",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        # ---------- Extender contexto (YaRN) ----------
        panel_yarn = self._crear_panel(contenido, "📏 Extender el contexto más allá del entrenamiento (YaRN)")
        self._crear_label_dim(
            panel_yarn,
            "Cada modelo se entrena con un contexto máximo (ej. 32k). YaRN le permite usar el\n"
            "doble o el cuádruple con poca pérdida de calidad. Actívalo solo si necesitas más\n"
            "contexto del nativo (y sube 'Contexto' arriba); en textos cortos puede bajar un poco\n"
            "la precisión. Va junto con TurboQuant para que la caché no consuma toda la VRAM.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        fila_yarn = tk.Frame(panel_yarn)
        fila_yarn.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_yarn))
        self._crear_label_card(fila_yarn, "Modo:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(fila_yarn, textvariable=self.var_rope_modo, state="readonly", width=12,
                     values=["Ninguno", "YaRN ×2", "YaRN ×4"]).pack(side=tk.LEFT, padx=(0, 18))
        self._crear_label_card(fila_yarn, "Contexto original del modelo (opcional):").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(fila_yarn, textvariable=self.var_yarn_orig, width=10).pack(side=tk.LEFT)

        # ---------- Dispositivos de calculo ----------
        panel_disp = self._crear_panel(contenido, "🖥️ Dispositivos de cálculo (GPU dedicada, integrada o varias GPU)")
        self._crear_label_dim(
            panel_disp,
            "Por defecto llama.cpp elige solo. Aquí puedes forzar cuáles usar (ej. CUDA0, o\n"
            "Vulkan1 para una GPU integrada) y cómo repartir el modelo entre varias GPU\n"
            "(ej. 3,1). Usa 'Ver dispositivos' para ver los nombres exactos en tu PC.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        grid_disp = tk.Frame(panel_disp)
        grid_disp.pack(fill=tk.X, pady=(0, 4))
        self._widgets_panel.append(("panel", grid_disp))
        self._crear_entry_config(grid_disp, "Dispositivos (-dev):", self.var_dispositivos, 0, ancho=24)
        self._crear_entry_config(grid_disp, "Reparto entre GPU (-ts):", self.var_tensor_split, 1, ancho=24)
        self._crear_label_card(grid_disp, "Modo de reparto (-sm):").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(grid_disp, textvariable=self.var_split_mode, state="readonly", width=21,
                     values=["", "layer", "row", "tensor", "none"]).grid(row=2, column=1, sticky="w", padx=12, pady=6)
        self._crear_entry_config(grid_disp, "GPU principal (-mg):", self.var_main_gpu, 3, ancho=24)
        self._crear_label_dim(
            panel_disp,
            "Con dos o más GPU: 'layer' (por defecto) reparte capas en secuencia; 'row' reparte\n"
            "cada capa por filas; 'tensor' reparte pesos y caché entre las GPU y trabajan en\n"
            "paralelo (EXPERIMENTAL, suele dar más velocidad con modelos grandes/MoE). 'none'\n"
            "usa una sola GPU. Vacío = el motor decide. Con una sola GPU no hace falta tocarlo.",
        ).pack(anchor="w", padx=12, pady=(0, 6))
        self._crear_boton(panel_disp, "🔍 Ver dispositivos disponibles", self.listar_dispositivos).pack(
            anchor="w", padx=12, pady=(4, 12))

        panel_tools = self._crear_panel(contenido, "🔎 Herramientas para el modelo")
        self.chk_busqueda_web = tk.Checkbutton(
            panel_tools, text="Búsqueda web (el modelo puede buscar en internet cuando lo necesite)",
            variable=self.var_busqueda_web_tool, font=("Segoe UI", 9, "bold"), bd=0, highlightthickness=0,
        )
        self.chk_busqueda_web.pack(anchor="w", padx=12, pady=(0, 4))
        self._widgets_panel.append(("check", self.chk_busqueda_web))
        self._crear_label_dim(
            panel_tools,
            "Usa DuckDuckGo por su cuenta — no necesita ninguna API key ni registro.\n"
            "Requiere un modelo que soporte 'tool calling' y --jinja (activado por defecto).",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        panel_seg = self._crear_panel(contenido, "🔑 Seguridad del servidor")
        self._crear_label_dim(
            panel_seg,
            "Opcional: protege el servidor con una clave de acceso.\n"
            "Si la dejas vacía, cualquier programa en tu red local puede usar el servidor.",
        ).pack(anchor="w", padx=12, pady=(0, 6))
        grid_seg = tk.Frame(panel_seg)
        grid_seg.pack(fill=tk.X, pady=(0, 6))
        self._widgets_panel.append(("panel", grid_seg))
        self._crear_entry_config(grid_seg, "API Key / contraseña:", self.var_api_key, 0, ancho=28)
        self._crear_entry_config(grid_seg, "Orígenes permitidos (CORS):", self.var_cors_origins, 1, ancho=28)
        self._crear_entry_config(grid_seg, "Timeout del servidor (segundos):", self.var_timeout, 2, ancho=28)
        self._crear_label_dim(
            panel_seg,
            "CORS: '*' permite que cualquier página web use tu servidor. Pon 'localhost'\n"
            "para restringirlo solo a páginas abiertas en esta misma PC, o una lista de\n"
            "dominios separados por coma. Timeout: vacío = 3600s (1 hora) por defecto,\n"
            "el tiempo máximo que el servidor espera antes de cortar una respuesta larga.",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        panel_tq = self._crear_panel(contenido, "🧠 TurboQuant (cuantización caché KV)")
        self.chk_turboquant = tk.Checkbutton(
            panel_tq, text="Activar TurboQuant al iniciar el servidor", variable=self.var_turboquant,
            font=("Segoe UI", 9, "bold"), bd=0, highlightthickness=0, command=self._al_cambiar_turboquant,
        )
        self.chk_turboquant.pack(anchor="w", padx=12)
        self._widgets_panel.append(("check", self.chk_turboquant))

        self._crear_label_dim(
            panel_tq,
            "Cuantiza la caché K/V (técnica de Google Research) para reducir el uso de\nVRAM y poder usar más contexto. Requiere Flash Attention.",
        ).pack(anchor="w", padx=12, pady=(2, 8))

        fila_kv = tk.Frame(panel_tq)
        fila_kv.pack(anchor="w", padx=6, pady=(0, 6))
        self._widgets_panel.append(("panel", fila_kv))
        self._crear_label_card(fila_kv, "Cache K:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.combo_kv_k = ttk.Combobox(fila_kv, textvariable=self.var_kv_k, values=TIPOS_CACHE_KV, state="readonly", width=12)
        self.combo_kv_k.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        self._crear_label_card(fila_kv, "Cache V:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.combo_kv_v = ttk.Combobox(fila_kv, textvariable=self.var_kv_v, values=TIPOS_CACHE_KV, state="readonly", width=12)
        self.combo_kv_v.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        fila_presets = tk.Frame(panel_tq)
        fila_presets.pack(fill=tk.X, padx=12, pady=(4, 14))
        self._widgets_panel.append(("panel", fila_presets))
        self._botones_preset = []
        for nombre_preset in PRESETS_TURBOQUANT:
            b = BotonRedondo(
                fila_presets, text=nombre_preset, font=("Segoe UI", 9), padx=12, pady=5, radio=9,
                command=lambda p=nombre_preset: self.aplicar_preset_turboquant(p),
            )
            b.pack(side=tk.LEFT, padx=(0, 6))
            self._botones_preset.append(b)

        self._al_cambiar_turboquant()
        return pagina

    # ==================================================================
    # PAGINA: CHAT / PLAYGROUND
    # ==================================================================
    def _pagina_chat(self, padre):
        # Sin scroll exterior: el cuadro de chat debe estirarse para llenar
        # todo el alto disponible, no quedar con tamano minimo dentro de un canvas.
        pagina, contenido = self._nueva_pagina(padre, "💬 Chat / Playground", scrollable=False)

        self._crear_label_dim(
            contenido, "Prueba el modelo cargado directamente, sin pasar por VS Code ni por los agentes.", fondo="bg",
        ).pack(anchor="w", pady=(0, 6))

        self.fila_modelo_router = tk.Frame(contenido)
        self._widgets_panel.append(("bg", self.fila_modelo_router))
        lbl_mr = tk.Label(self.fila_modelo_router, text="🔀 Modelo (Router):")
        lbl_mr.pack(side=tk.LEFT, padx=(0, 6))
        self._registrar_texto(lbl_mr, "bg")
        self.combo_modelo_router = ttk.Combobox(
            self.fila_modelo_router, textvariable=self.var_modelo_router_activo, state="readonly", width=40,
            values=self.modelos_router_disponibles,
        )
        self.combo_modelo_router.pack(side=tk.LEFT)
        # Se muestra solo cuando el modo Router esta activo; se activa/oculta
        # desde _al_cambiar_modo_router y al conectar el servidor.

        fila_proveedor = tk.Frame(contenido)
        fila_proveedor.pack(anchor="w", pady=(0, 8), fill=tk.X)
        self._widgets_panel.append(("bg", fila_proveedor))
        lbl_prov = tk.Label(fila_proveedor, text="☁️ Responder con:")
        lbl_prov.pack(side=tk.LEFT, padx=(0, 6))
        self._registrar_texto(lbl_prov, "bg")
        self.combo_proveedor_chat = ttk.Combobox(
            fila_proveedor, textvariable=self.var_proveedor_chat, state="readonly", width=28,
            values=["Local (llama.cpp)"],
        )
        self.combo_proveedor_chat.pack(side=tk.LEFT)

        panel_chat = self.panel_chat_borde = tk.Frame(contenido, bd=1, relief="solid")
        panel_chat.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._widgets_panel.append(("panel_borde", panel_chat))

        self.txt_chat = scrolledtext.ScrolledText(panel_chat, wrap=tk.WORD, font=("Segoe UI", 10), bd=0, state=tk.DISABLED)
        self.txt_chat.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        fila_entrada = tk.Frame(contenido)
        fila_entrada.pack(fill=tk.X)
        self._widgets_panel.append(("bg", fila_entrada))
        entrada = ttk.Entry(fila_entrada, textvariable=self.var_chat_entrada)
        entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        entrada.bind("<Return>", lambda e: self.enviar_chat_hilo())
        self.btn_enviar_chat = self._crear_boton(fila_entrada, "➤ Enviar", self.enviar_chat_hilo, primario=True)
        self.btn_enviar_chat.pack(side=tk.LEFT, padx=(8, 0))

        self.lbl_estado_chat = tk.Label(contenido, text="", font=("Segoe UI", 9, "italic"))
        self.lbl_estado_chat.pack(anchor="w", pady=(6, 0))
        self._registrar_texto(self.lbl_estado_chat, "bg", dim=True)

        return pagina

    # ==================================================================
    # PAGINA: PROVEEDORES EN LA NUBE (OpenAI, Claude, u otro compatible)
    # ==================================================================
    def _pagina_proveedores(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "☁️ Proveedores en la nube")

        self._crear_label_dim(
            contenido,
            "Conecta modelos en la nube (OpenAI, Claude/Anthropic, o cualquier otro con\n"
            "API compatible con OpenAI) con tu propia API key, para usarlos desde el Chat/\n"
            "Playground además de tus modelos locales. Cada clave se guarda solo en esta PC.",
            fondo="bg",
        ).pack(anchor="w", pady=(0, 10))

        panel_lista = self._crear_panel(contenido, "Proveedores guardados")
        self.lista_proveedores = tk.Listbox(panel_lista, height=5, font=("Segoe UI", 9), relief="flat", bd=0)
        self.lista_proveedores.pack(fill=tk.X, padx=12, pady=(0, 8))
        fila_btn_prov = tk.Frame(panel_lista)
        fila_btn_prov.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_btn_prov))
        self._crear_boton(fila_btn_prov, "🗑 Quitar seleccionado", self.quitar_proveedor_nube).pack(side=tk.LEFT)

        panel_add = self._crear_panel(contenido, "➕ Agregar proveedor")
        grid_add = tk.Frame(panel_add)
        grid_add.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel", grid_add))
        self._crear_entry_config(grid_add, "Nombre (ej. 'Mi OpenAI'):", self.var_prov_nombre, 0, ancho=30)
        self._crear_label_card(grid_add, "Tipo:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        combo_tipo = ttk.Combobox(
            grid_add, textvariable=self.var_prov_tipo, state="readonly", width=27,
            values=["OpenAI / compatible", "Anthropic (Claude)"],
        )
        combo_tipo.grid(row=1, column=1, sticky="w", padx=12, pady=6)
        combo_tipo.bind("<<ComboboxSelected>>", lambda e: self._al_cambiar_tipo_proveedor())
        self._crear_entry_config(grid_add, "URL base:", self.var_prov_base_url, 2, ancho=30)
        self._crear_entry_config(grid_add, "API Key:", self.var_prov_api_key, 3, ancho=30)
        self._crear_entry_config(grid_add, "Modelo (ej. gpt-4o / claude-opus-5):", self.var_prov_modelo, 4, ancho=30)
        self._crear_label_dim(
            panel_add,
            "'OpenAI / compatible' sirve para OpenAI, Groq, Mistral, OpenRouter, Azure, etc.\n"
            "— revisa la documentación de cada uno para su URL base exacta. 'Anthropic' usa\n"
            "el formato propio de la API de Claude (distinto a OpenAI), ya configurado solo.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        self._crear_boton(panel_add, "💾 Guardar proveedor", self.agregar_proveedor_nube, primario=True).pack(anchor="w", padx=12, pady=(0, 12))

        self._refrescar_lista_proveedores()
        return pagina

    def _al_cambiar_tipo_proveedor(self):
        if self.var_prov_tipo.get() == "Anthropic (Claude)":
            self.var_prov_base_url.set("https://api.anthropic.com/v1")
            if not self.var_prov_modelo.get().strip():
                self.var_prov_modelo.set("claude-opus-5")
        elif self.var_prov_base_url.get().strip() == "https://api.anthropic.com/v1":
            self.var_prov_base_url.set("")

    def _refrescar_lista_proveedores(self):
        self.lista_proveedores.delete(0, tk.END)
        for p in self.proveedores_nube:
            self.lista_proveedores.insert(tk.END, f"{p.get('nombre')}  ·  {p.get('tipo')}  ·  {p.get('modelo')}")
        t = self.tema
        self.lista_proveedores.configure(bg=mezclar(t["panel"], t["bg"], 0.65), fg=t["texto"], selectbackground=t["acento"],
                                         selectforeground=t["acento_texto"], highlightbackground=t["borde"],
                                         highlightcolor=t["acento"], highlightthickness=1, relief="flat", bd=0)
        self._refrescar_combo_proveedor_chat()

    def _refrescar_combo_proveedor_chat(self):
        if hasattr(self, "combo_proveedor_chat"):
            nombres = ["Local (llama.cpp)"] + [p.get("nombre") for p in self.proveedores_nube]
            self.combo_proveedor_chat["values"] = nombres
            if self.var_proveedor_chat.get() not in nombres:
                self.var_proveedor_chat.set("Local (llama.cpp)")

    def agregar_proveedor_nube(self):
        nombre = self.var_prov_nombre.get().strip()
        base_url = self.var_prov_base_url.get().strip().rstrip("/")
        api_key = self.var_prov_api_key.get().strip()
        modelo = self.var_prov_modelo.get().strip()
        if not nombre or not base_url or not api_key or not modelo:
            messagebox.showwarning("Faltan datos", "Completa nombre, URL base, API key y modelo.")
            return
        tipo = "anthropic" if self.var_prov_tipo.get() == "Anthropic (Claude)" else "openai"
        self.proveedores_nube = [p for p in self.proveedores_nube if p.get("nombre") != nombre]
        self.proveedores_nube.append({"nombre": nombre, "tipo": tipo, "base_url": base_url, "api_key": api_key, "modelo": modelo})
        guardar_proveedores_nube(self.proveedores_nube)
        self.var_prov_nombre.set("")
        self.var_prov_base_url.set("")
        self.var_prov_api_key.set("")
        self.var_prov_modelo.set("")
        self._refrescar_lista_proveedores()

    def quitar_proveedor_nube(self):
        seleccion = self.lista_proveedores.curselection()
        if not seleccion:
            return
        del self.proveedores_nube[seleccion[0]]
        guardar_proveedores_nube(self.proveedores_nube)
        self._refrescar_lista_proveedores()

    def _buscar_proveedor(self, nombre):
        for p in self.proveedores_nube:
            if p.get("nombre") == nombre:
                return p
        return None

    def _enviar_a_proveedor_nube(self, proveedor, mensaje):
        """Manda un mensaje a un proveedor en la nube y devuelve el texto de
        respuesta. Anthropic usa /v1/messages con su propio formato (distinto
        a OpenAI); cualquier otro tipo usa /chat/completions estilo OpenAI."""
        base_url = proveedor.get("base_url", "").rstrip("/")
        api_key = proveedor.get("api_key", "")
        modelo = proveedor.get("modelo", "")
        if proveedor.get("tipo") == "anthropic":
            datos = json.dumps({
                "model": modelo,
                "max_tokens": 1536,
                "messages": [{"role": "user", "content": mensaje}],
            }).encode("utf-8")
            encabezados = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            peticion = urllib.request.Request(f"{base_url}/messages", data=datos, headers=encabezados)
            with urllib.request.urlopen(peticion, timeout=180) as resp:
                cuerpo = json.loads(resp.read().decode("utf-8"))
            bloques = cuerpo.get("content", [])
            return "".join(b.get("text", "") for b in bloques if b.get("type") == "text").strip()
        else:
            datos = json.dumps({
                "model": modelo,
                "messages": [{"role": "user", "content": mensaje}],
                "max_tokens": 1536,
                "temperature": 0.3,
            }).encode("utf-8")
            encabezados = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            peticion = urllib.request.Request(f"{base_url}/chat/completions", data=datos, headers=encabezados)
            with urllib.request.urlopen(peticion, timeout=180) as resp:
                cuerpo = json.loads(resp.read().decode("utf-8"))
            return (cuerpo["choices"][0]["message"].get("content") or "").strip()

    def _chat_append(self, remitente, texto, color_clave):
        self.txt_chat.configure(state=tk.NORMAL)
        tag = f"tag_{color_clave}_{remitente}"
        self.txt_chat.tag_config(tag, foreground=self.tema[color_clave], font=("Segoe UI", 10, "bold"))
        self.txt_chat.insert(tk.END, f"{remitente}: ", tag)
        self.txt_chat.tag_config("normal", foreground=self.tema["texto"], font=("Segoe UI", 10))
        self._insertar_texto_markdown(texto)
        self.txt_chat.insert(tk.END, "\n\n")
        self.txt_chat.configure(state=tk.DISABLED)
        self.txt_chat.see(tk.END)

    def _insertar_texto_markdown(self, texto):
        """Renderizado ligero de Markdown para el Text del chat (sin libreria
        externa): encabezados, **negrita**, *cursiva*, `codigo`, y separadores
        ---. No es un parser completo, solo evita que se vean los simbolos
        crudos en las respuestas de modelos que contestan en Markdown."""
        t = self.tema
        self.txt_chat.tag_config("md_h", font=("Segoe UI", 12, "bold"), foreground=t["acento_hover"])
        self.txt_chat.tag_config("md_bold", font=("Segoe UI", 10, "bold"), foreground=t["texto"])
        self.txt_chat.tag_config("md_italic", font=("Segoe UI", 10, "italic"), foreground=t["texto"])
        self.txt_chat.tag_config("md_code", font=("Consolas", 9), background=t["borde"], foreground=t["texto"])

        lineas = texto.split("\n")
        for i, linea in enumerate(lineas):
            despojada = linea.strip()
            if re.match(r"^#{1,6}\s+", despojada):
                contenido = re.sub(r"^#{1,6}\s+", "", despojada)
                self.txt_chat.insert(tk.END, contenido + "\n", "md_h")
                continue
            if re.match(r"^([-_*]\s*){3,}$", despojada):
                continue  # linea separadora "---" / "___": no aporta nada en texto plano

            # trocear la linea por **negrita**, *cursiva* y `codigo`, en ese orden
            partes = re.split(r"(\*\*[^*]+\*\*|`[^`]+`|(?<!\*)\*[^*]+\*(?!\*))", linea)
            for parte in partes:
                if not parte:
                    continue
                m_bold = re.match(r"^\*\*([^*]+)\*\*$", parte)
                m_code = re.match(r"^`([^`]+)`$", parte)
                m_ital = re.match(r"^\*([^*]+)\*$", parte)
                if m_bold:
                    self.txt_chat.insert(tk.END, m_bold.group(1), "md_bold")
                elif m_code:
                    self.txt_chat.insert(tk.END, m_code.group(1), "md_code")
                elif m_ital:
                    self.txt_chat.insert(tk.END, m_ital.group(1), "md_italic")
                else:
                    self.txt_chat.insert(tk.END, parte, "normal")
            if i < len(lineas) - 1:
                self.txt_chat.insert(tk.END, "\n")

    def enviar_chat_hilo(self):
        mensaje = self.var_chat_entrada.get().strip()
        if not mensaje:
            return
        if not self.servidor_listo:
            messagebox.showwarning("Advertencia", "Primero carga un modelo y espera a que quede conectado.")
            return
        self.var_chat_entrada.set("")
        self._chat_append("Tú", mensaje, "acento")
        self.btn_enviar_chat.config(state=tk.DISABLED)
        self._chat_esperando = True
        self._tick_espera_chat(0)
        hilo = threading.Thread(target=self._enviar_chat, args=(mensaje,), daemon=True)
        hilo.start()

    def _tick_espera_chat(self, segundos):
        if not getattr(self, "_chat_esperando", False):
            return
        puntos = "." * ((segundos % 3) + 1)
        self.lbl_estado_chat.config(text=f"⏳ Esperando respuesta del modelo{puntos}  ({segundos}s — los modelos 'thinking' pueden tardar varios minutos)")
        self.root.after(1000, lambda: self._tick_espera_chat(segundos + 1))

    def _temperatura_chat(self):
        """Temperatura del Chat/Playground local: la del panel de muestreo si
        se puso una valida, o 0.3 (respuestas estables) por defecto."""
        try:
            texto = self.var_temp.get().strip()
            return float(texto) if texto else 0.3
        except ValueError:
            return 0.3

    def _enviar_chat(self, mensaje):
        proveedor_elegido = self.var_proveedor_chat.get()
        if proveedor_elegido and proveedor_elegido != "Local (llama.cpp)":
            proveedor = self._buscar_proveedor(proveedor_elegido)
            try:
                if not proveedor:
                    raise ValueError("Ese proveedor ya no está guardado.")
                respuesta = self._enviar_a_proveedor_nube(proveedor, mensaje) or "(respuesta vacía)"
                self.root.after(0, lambda: self._chat_append(proveedor_elegido, respuesta, "ok"))
            except Exception as e:
                mensaje_error = str(e)
                self.root.after(0, lambda: self._chat_append("Error", mensaje_error, "peligro"))
            finally:
                self._chat_esperando = False
                self.root.after(0, lambda: self.btn_enviar_chat.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.lbl_estado_chat.config(text=""))
            return

        endpoint = self.endpoint_actual.get()
        if self.var_modo_router.get():
            modelo_pedido = self.var_modelo_router_activo.get()
        else:
            modelo_pedido = os.path.basename(self.modelo_seleccionado.get())
        try:
            mensajes = [{"role": "user", "content": mensaje}]
            herramientas = None
            if self.var_busqueda_web_tool.get():
                herramientas = [{
                    "type": "function",
                    "function": {
                        "name": "buscar_web",
                        "description": "Busca en internet (DuckDuckGo) y devuelve resultados relevantes: título, enlace y resumen.",
                        "parameters": {
                            "type": "object",
                            "properties": {"consulta": {"type": "string", "description": "Texto a buscar"}},
                            "required": ["consulta"],
                        },
                    },
                }]
            encabezados = {"Content-Type": "application/json"}
            clave_api = self.var_api_key.get().strip()
            if clave_api:
                encabezados["Authorization"] = f"Bearer {clave_api}"

            def _pedir(msgs):
                cuerpo_peticion = {
                    "model": modelo_pedido,
                    "messages": msgs,
                    # 1536 en vez de un limite corto: los modelos "thinking" (razonan
                    # antes de responder, ej. Agents-A1-4B) pueden agotar el limite de
                    # tokens mientras todavia estan pensando y dejar la respuesta vacia.
                    "max_tokens": 1536,
                    "temperature": self._temperatura_chat(),
                }
                if herramientas:
                    cuerpo_peticion["tools"] = herramientas
                    cuerpo_peticion["tool_choice"] = "auto"
                datos = json.dumps(cuerpo_peticion).encode("utf-8")
                peticion = urllib.request.Request(f"{endpoint}/chat/completions", data=datos, headers=encabezados)
                with urllib.request.urlopen(peticion, timeout=180) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            cuerpo = _pedir(mensajes)
            mensaje_resp = cuerpo["choices"][0]["message"]

            tool_calls = mensaje_resp.get("tool_calls")
            if tool_calls:
                # El modelo pidio usar una herramienta: la ejecutamos aca mismo
                # (no depende de que Cline/Continue/etc. la soporten) y le
                # devolvemos el resultado para que arme la respuesta final.
                mensajes.append(mensaje_resp)
                for tc in tool_calls:
                    nombre_fn = (tc.get("function") or {}).get("name")
                    args_raw = (tc.get("function") or {}).get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                    except Exception:
                        args = {}
                    if nombre_fn == "buscar_web":
                        resultado_tool = buscar_en_duckduckgo(args.get("consulta", mensaje))
                    else:
                        resultado_tool = f"Herramienta desconocida: {nombre_fn}"
                    mensajes.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": resultado_tool})
                cuerpo = _pedir(mensajes)
                mensaje_resp = cuerpo["choices"][0]["message"]

            respuesta = (mensaje_resp.get("content") or "").strip()
            razonamiento = (mensaje_resp.get("reasoning_content") or "").strip()
            motivo_corte = cuerpo["choices"][0].get("finish_reason")
            if not respuesta and razonamiento:
                # Modelo "thinking" que se quedo sin tokens antes de terminar de
                # razonar: mostramos el razonamiento en vez de dejar vacio, y
                # avisamos que no llego a dar la respuesta final.
                respuesta = f"[Razonamiento incompleto, no llegó a responder — sube 'max_tokens' o prueba otro modelo]\n\n{razonamiento}"
            elif not respuesta:
                respuesta = f"(respuesta vacía — finish_reason: {motivo_corte})"
            self.root.after(0, lambda: self._chat_append("Modelo", respuesta, "ok"))
        except Exception as e:
            # OJO: "except X as e" borra 'e' al salir del bloque, asi que hay
            # que capturar el mensaje en una variable normal ANTES de armar el
            # lambda diferido con root.after — si no, cuando el callback se
            # ejecuta mas tarde revienta con NameError y el error queda mudo.
            mensaje_error = str(e)
            self.root.after(0, lambda: self._chat_append("Error", mensaje_error, "peligro"))
        finally:
            self._chat_esperando = False
            self.root.after(0, lambda: self.btn_enviar_chat.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.lbl_estado_chat.config(text=""))

    # ==================================================================
    # PAGINA: AGENTES (CREW)
    # ==================================================================
    def _pagina_agentes(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🤖 Equipo de Agentes (CrewAI)")

        panel_dev = self._crear_panel(contenido, "👨‍💻 Agente 1 — Desarrollador")
        grid_dev = tk.Frame(panel_dev)
        grid_dev.pack(fill=tk.X, pady=(0, 12))
        self._widgets_panel.append(("panel", grid_dev))
        self._crear_entry_config(grid_dev, "Rol:", self.var_rol_dev, 0, ancho=40)
        self._crear_entry_config(grid_dev, "Objetivo:", self.var_objetivo_dev, 1, ancho=40)
        self._crear_entry_config(grid_dev, "Tarea:", self.var_tarea_dev, 2, ancho=40)

        panel_qa = self._crear_panel(contenido, "🔍 Agente 2 — QA / Revisor")
        grid_qa = tk.Frame(panel_qa)
        grid_qa.pack(fill=tk.X, pady=(0, 12))
        self._widgets_panel.append(("panel", grid_qa))
        self._crear_entry_config(grid_qa, "Rol:", self.var_rol_qa, 0, ancho=40)
        self._crear_entry_config(grid_qa, "Objetivo:", self.var_objetivo_qa, 1, ancho=40)
        self._crear_entry_config(grid_qa, "Tarea:", self.var_tarea_qa, 2, ancho=40)

        self.btn_agentes = self._crear_boton(contenido, "🤖 Ejecutar equipo de Agentes (Crew)", self.ejecutar_agentes_hilo, primario=True, state=tk.DISABLED)
        self.btn_agentes.pack(fill=tk.X, pady=(4, 6))

        self._crear_label_dim(contenido, "El resultado se guarda en 'resultado_agentes.md' junto al programa.", fondo="bg").pack(anchor="w")

        return pagina

    # ==================================================================
    # PAGINA: CONEXION (endpoint + generadores de config para clientes)
    # ==================================================================
    def _pagina_conexion(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🔌 Conexión del agente")

        panel_conn = self._crear_panel(contenido, "Endpoint activo")
        fila_endpoint = tk.Frame(panel_conn)
        fila_endpoint.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._widgets_panel.append(("panel", fila_endpoint))
        self.entrada_endpoint = ttk.Entry(fila_endpoint, textvariable=self.endpoint_actual, state="readonly")
        self.entrada_endpoint.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.btn_copiar = self._crear_boton(fila_endpoint, "📋 Copiar", self.copiar_endpoint)
        self.btn_copiar.pack(side=tk.LEFT, padx=(6, 0))

        panel_clientes = self._crear_panel(contenido, "Configuración lista para copiar")
        self._crear_label_dim(
            panel_clientes, "Genera y copia al portapapeles la configuración para tu editor, con el endpoint ya rellenado.",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        fila_btns = tk.Frame(panel_clientes)
        fila_btns.pack(fill=tk.X, padx=12, pady=(0, 14))
        self._widgets_panel.append(("panel", fila_btns))
        self._crear_boton(fila_btns, "🧩 Copiar config Continue (YAML)", self.copiar_config_continue).pack(side=tk.LEFT, padx=(0, 8))
        self._crear_boton(fila_btns, "🖇️ Copiar config Cline / OpenAI-Compatible", self.copiar_config_cline).pack(side=tk.LEFT, padx=(0, 8))
        self._crear_boton(fila_btns, "💻 Copiar config OpenCode (JSON)", self.copiar_config_opencode).pack(side=tk.LEFT)

        return pagina

    def _config_continue_texto(self):
        endpoint = self.endpoint_actual.get() or "http://127.0.0.1:8080/v1"
        clave = self.var_api_key.get().strip() or "local-placeholder"
        return (
            "  - name: TurboQuant Local (llama.cpp)\n"
            "    provider: openai\n"
            "    model: local-model\n"
            f"    apiBase: {endpoint}\n"
            f"    apiKey: {clave}\n"
            "    roles:\n"
            "      - chat\n"
            "      - edit\n"
            "      - apply\n"
        )

    def _config_cline_texto(self):
        endpoint = self.endpoint_actual.get() or "http://127.0.0.1:8080/v1"
        clave = self.var_api_key.get().strip() or "local-placeholder"
        return (
            "API Provider: OpenAI Compatible\n"
            f"Base URL: {endpoint}\n"
            f"API Key: {clave}\n"
            "Model ID: local-model\n"
        )

    def copiar_config_continue(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._config_continue_texto())
        self._set_estado("📋 Config de Continue copiada al portapapeles.", "ok")

    def copiar_config_cline(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._config_cline_texto())
        self._set_estado("📋 Config de Cline copiada al portapapeles.", "ok")

    def _config_opencode_texto(self):
        endpoint = self.endpoint_actual.get() or "http://127.0.0.1:8080/v1"
        clave = self.var_api_key.get().strip() or "local-placeholder"
        modelo = os.path.basename(self.modelo_seleccionado.get()) if self.modelo_seleccionado.get() else "local-model"
        return json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "provider": {
                    "llama.cpp": {
                        "npm": "@ai-sdk/openai-compatible",
                        "name": "llama-server (local)",
                        "options": {"baseURL": endpoint, "apiKey": clave},
                        "models": {modelo: {"name": f"{modelo} (local)"}},
                    }
                },
            },
            indent=2, ensure_ascii=False,
        )

    def copiar_config_opencode(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._config_opencode_texto())
        self._set_estado("📋 Config de OpenCode copiada al portapapeles. Guárdala como opencode.json en tu proyecto o en ~/.config/opencode/", "ok")

    # ==================================================================
    # PAGINA: TUNEL REMOTO (cloudflared quick tunnel)
    # ==================================================================
    def _pagina_tunel(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🌐 Túnel remoto")

        panel = self._crear_panel(contenido, "Exponer el servidor a internet")

        if self.cloudflared_path:
            self._crear_label_dim(
                panel, f"cloudflared encontrado en:\n{self.cloudflared_path}\n\nCrea un túnel temporal (*.trycloudflare.com) para que un agente remoto\npueda conectarse a tu modelo local, sin abrir puertos en tu router.",
            ).pack(anchor="w", padx=12, pady=(0, 10))

            fila = tk.Frame(panel)
            fila.pack(fill=tk.X, padx=12, pady=(0, 10))
            self._widgets_panel.append(("panel", fila))
            self.btn_tunel = self._crear_boton(fila, "🌐 Iniciar túnel", self.iniciar_tunel_hilo, primario=True)
            self.btn_tunel.pack(side=tk.LEFT)
            self.btn_tunel_detener = self._crear_boton(fila, "⏹ Detener túnel", self.detener_tunel, state=tk.DISABLED)
            self.btn_tunel_detener.pack(side=tk.LEFT, padx=(8, 0))

            fila_url = tk.Frame(panel)
            fila_url.pack(fill=tk.X, padx=12, pady=(0, 14))
            self._widgets_panel.append(("panel", fila_url))
            entrada_url = ttk.Entry(fila_url, textvariable=self.var_url_tunel, state="readonly")
            entrada_url.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            self._crear_boton(fila_url, "📋 Copiar URL", self.copiar_url_tunel).pack(side=tk.LEFT, padx=(6, 0))
        else:
            self._crear_label_dim(
                panel,
                "No se encontró 'cloudflared.exe' (ni en esta carpeta ni en el PATH del sistema),\n"
                "así que esta función todavía no está disponible.\n\n"
                "cloudflared es gratuito y no requiere cuenta para túneles temporales.\n"
                "Descárgalo tú mismo desde:\ngithub.com/cloudflare/cloudflared/releases\n"
                "y coloca 'cloudflared.exe' en esta misma carpeta, o en el PATH.\n"
                "(No lo descargo automáticamente — es tu decisión instalar software nuevo.)",
            ).pack(anchor="w", padx=12, pady=(0, 14))

        return pagina

    def iniciar_tunel_hilo(self):
        if not self.servidor_listo:
            messagebox.showwarning("Advertencia", "Primero carga un modelo y espera a que quede conectado.")
            return
        self.btn_tunel.config(state=tk.DISABLED)
        self.var_url_tunel.set("Creando túnel...")
        hilo = threading.Thread(target=self._iniciar_tunel, daemon=True)
        hilo.start()

    def _iniciar_tunel(self):
        endpoint = self.endpoint_actual.get()
        base = endpoint.rsplit("/v1", 1)[0] if endpoint.endswith("/v1") else endpoint
        try:
            self.proceso_tunel = subprocess.Popen(
                [self.cloudflared_path, "tunnel", "--url", base],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            mensaje_error = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo iniciar cloudflared:\n{mensaje_error}"))
            self.root.after(0, lambda: self.btn_tunel.config(state=tk.NORMAL))
            return

        patron = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
        for linea in self.proceso_tunel.stdout:
            m = patron.search(linea)
            if m:
                url = m.group(0)
                self.root.after(0, lambda u=url: self._tunel_listo(u))
                break

    def _tunel_listo(self, url):
        self.var_url_tunel.set(f"{url}/v1")
        self.btn_tunel_detener.config(state=tk.NORMAL)
        self._set_estado(f"🌐 Túnel activo: {url}", "ok")

    def detener_tunel(self):
        if self.proceso_tunel:
            try:
                self.proceso_tunel.terminate()
            except Exception:
                pass
            self.proceso_tunel = None
        self.var_url_tunel.set("")
        self.btn_tunel.config(state=tk.NORMAL)
        self.btn_tunel_detener.config(state=tk.DISABLED)
        self._set_estado("Túnel detenido.")

    def copiar_url_tunel(self):
        url = self.var_url_tunel.get()
        if not url:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self._set_estado("📋 URL del túnel copiada.", "ok")

    # ==================================================================
    # PAGINA: MONITOR EN VIVO (GPU / VRAM / RAM / CPU)
    # ==================================================================
    def _pagina_monitor(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "📊 Monitor en vivo")

        # Panel de hardware detectado: no depende de que la GPU sea NVIDIA,
        # asi que sirve para cualquiera que instale el programa (AMD, Intel,
        # o solo CPU), no solo para el hardware con el que se probo.
        info_hw = obtener_info_hardware()
        panel_hw = self._crear_panel(contenido, "🔧 Hardware detectado en esta PC")
        texto_gpus = ", ".join(info_hw["gpus"]) if info_hw["gpus"] else "No se detectó ninguna GPU"
        ram_txt = f"{info_hw['ram_total_gb']:.0f} GB" if info_hw["ram_total_gb"] else "desconocida"
        self._crear_label_dim(
            panel_hw,
            f"CPU: {info_hw['cpu_nombre']}  ·  {info_hw['cpu_nucleos']} núcleos físicos\n"
            f"RAM total: {ram_txt}\n"
            f"GPU(s): {texto_gpus}",
            fondo="panel",
        ).pack(anchor="w", padx=12, pady=(0, 12))
        if not NVIDIA_SMI_PATH and info_hw["gpus"]:
            self._crear_label_dim(
                panel_hw,
                "⚠ Tu GPU no es NVIDIA (o no tiene nvidia-smi): el uso/VRAM en vivo de abajo\n"
                "no se puede leer, pero el programa igual funciona — solo asegúrate de usar\n"
                "un llama-server.exe compilado para tu hardware (build Vulkan o CPU-only,\n"
                "descargable desde github.com/ggml-org/llama.cpp/releases).",
                fondo="panel",
            ).pack(anchor="w", padx=12, pady=(0, 12))

        if not NVIDIA_SMI_PATH:
            self._crear_label_dim(contenido, "⚠ No se encontró nvidia-smi.exe — el uso de GPU/VRAM no se puede leer.", fondo="bg").pack(anchor="w", pady=(0, 8))
        if psutil is None:
            self._crear_label_dim(contenido, "⚠ El módulo 'psutil' no está disponible — el uso de RAM/CPU no se puede leer.", fondo="bg").pack(anchor="w", pady=(0, 8))

        panel_gpu = self._crear_panel(contenido, "🎮 GPU")
        self.lbl_gpu_nombre = self._crear_label_card(panel_gpu, "Detectando GPU...")
        self.lbl_gpu_nombre.pack(anchor="w", padx=12, pady=(0, 8))
        self._crear_barra_stat(panel_gpu, "gpu_uso", "Uso de GPU")
        self._crear_barra_stat(panel_gpu, "gpu_vram", "VRAM")
        self._crear_barra_stat(panel_gpu, "gpu_temp", "Temperatura", es_temp=True)
        tk.Frame(panel_gpu, height=8).pack()

        panel_sistema = self._crear_panel(contenido, "🖥️ Sistema")
        self._crear_barra_stat(panel_sistema, "cpu", "CPU")
        self._crear_barra_stat(panel_sistema, "ram", "RAM")
        tk.Frame(panel_sistema, height=8).pack()

        panel_proc = self._crear_panel(contenido, "🦙 Proceso llama-server.exe")
        self.lbl_proceso_servidor = self._crear_label_card(panel_proc, "El servidor no está corriendo.")
        self.lbl_proceso_servidor.pack(anchor="w", padx=12, pady=(0, 12))

        return pagina

    def _crear_barra_stat(self, padre, clave, etiqueta, es_temp=False):
        fila = tk.Frame(padre)
        fila.pack(fill=tk.X, padx=12, pady=4)
        self._widgets_panel.append(("panel", fila))

        lbl = self._crear_label_card(fila, etiqueta)
        lbl.pack(side=tk.LEFT, anchor="w")

        lbl_valor = tk.Label(fila, text="--", font=("Segoe UI", 9, "bold"))
        lbl_valor.pack(side=tk.RIGHT)
        self._registrar_texto(lbl_valor, "panel")

        contenedor_barra = tk.Frame(padre, height=14, bd=1, relief="solid")
        contenedor_barra.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._widgets_panel.append(("panel_borde", contenedor_barra))
        contenedor_barra.pack_propagate(False)

        relleno = tk.Frame(contenedor_barra, width=0)
        relleno.place(x=0, y=0, relheight=1)

        self._barras_monitor[clave] = {"contenedor": contenedor_barra, "relleno": relleno, "valor": lbl_valor, "es_temp": es_temp}

    def _actualizar_barra(self, clave, pct, texto):
        info = self._barras_monitor.get(clave)
        if not info:
            return
        pct = max(0.0, min(100.0, pct))
        info["valor"].config(text=texto)
        ancho_total = info["contenedor"].winfo_width() or 1
        t = self.tema
        if info["es_temp"]:
            color = t["ok"] if pct < 60 else (t["warn"] if pct < 85 else t["peligro"])
        else:
            color = t["ok"] if pct < 70 else (t["warn"] if pct < 90 else t["peligro"])
        info["relleno"].configure(bg=color, width=int(ancho_total * pct / 100))

    def _iniciar_monitor(self):
        if self._monitor_job is None:
            self._tick_monitor()

    def _detener_monitor(self):
        if self._monitor_job:
            self.root.after_cancel(self._monitor_job)
            self._monitor_job = None

    def _tick_monitor(self):
        stats_gpu = obtener_stats_gpu()
        if stats_gpu:
            self.lbl_gpu_nombre.config(text=stats_gpu["nombre"])
            self._actualizar_barra("gpu_uso", stats_gpu["uso_pct"], f"{stats_gpu['uso_pct']:.0f}%")
            vram_pct = (stats_gpu["vram_usada_mb"] / stats_gpu["vram_total_mb"] * 100) if stats_gpu["vram_total_mb"] else 0
            self._actualizar_barra("gpu_vram", vram_pct, f"{stats_gpu['vram_usada_mb']/1024:.1f} / {stats_gpu['vram_total_mb']/1024:.1f} GB")
            temp_pct = min(100.0, stats_gpu["temperatura_c"] / 100 * 100)
            self._actualizar_barra("gpu_temp", temp_pct, f"{stats_gpu['temperatura_c']:.0f}°C")
        else:
            self.lbl_gpu_nombre.config(text="Sin datos de GPU NVIDIA disponibles.")

        stats_sys = obtener_stats_sistema()
        if stats_sys:
            self._actualizar_barra("cpu", stats_sys["cpu_pct"], f"{stats_sys['cpu_pct']:.0f}%")
            self._actualizar_barra("ram", stats_sys["ram_pct"], f"{stats_sys['ram_usada_gb']:.1f} / {stats_sys['ram_total_gb']:.1f} GB")

        if self.proceso_servidor and self.proceso_servidor.poll() is None and psutil is not None:
            try:
                p = psutil.Process(self.proceso_servidor.pid)
                mem_mb = p.memory_info().rss / (1024**2)
                self.lbl_proceso_servidor.config(text=f"PID {p.pid}  ·  RAM del proceso: {mem_mb:.0f} MB  ·  CPU: {p.cpu_percent(interval=None):.0f}%")
            except Exception:
                self.lbl_proceso_servidor.config(text="El servidor no está corriendo.")
        else:
            self.lbl_proceso_servidor.config(text="El servidor no está corriendo.")

        self._monitor_job = self.root.after(1500, self._tick_monitor)

    # ==================================================================
    # PAGINA: DESCARGAR MODELOS (busqueda en Hugging Face)
    # ==================================================================
    def _pagina_descargar_hf(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🔍 Descargar modelos desde Hugging Face")

        self._crear_label_dim(
            contenido, "Busca modelos .gguf gratuitos publicados en Hugging Face y descárgalos\ndirecto a una de tus carpetas de modelos.", fondo="bg",
        ).pack(anchor="w", pady=(0, 10))

        fila_busq = tk.Frame(contenido)
        fila_busq.pack(fill=tk.X, pady=(0, 10))
        self._widgets_panel.append(("bg", fila_busq))
        entrada = ttk.Entry(fila_busq, textvariable=self.var_busqueda_hf)
        entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        entrada.bind("<Return>", lambda e: self.buscar_modelos_hf_hilo())
        self.btn_buscar_hf = self._crear_boton(fila_busq, "🔎 Buscar", self.buscar_modelos_hf_hilo, primario=True)
        self.btn_buscar_hf.pack(side=tk.LEFT, padx=(8, 0))

        panel_resultados = tk.Frame(contenido, bd=1, relief="solid")
        panel_resultados.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._widgets_panel.append(("panel_borde", panel_resultados))

        self.lista_resultados_hf = tk.Listbox(panel_resultados, font=("Segoe UI", 9), bd=0, highlightthickness=0,
                                               selectmode=tk.SINGLE, exportselection=False)
        self.lista_resultados_hf.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.lista_resultados_hf.bind("<<ListboxSelect>>", self._al_seleccionar_resultado_hf)

        fila_descarga = tk.Frame(contenido)
        fila_descarga.pack(fill=tk.X)
        self._widgets_panel.append(("bg", fila_descarga))
        self.btn_descargar_hf = self._crear_boton(fila_descarga, "⬇ Descargar seleccionado", self.confirmar_descarga_hf, primario=True, state=tk.DISABLED)
        self.btn_descargar_hf.pack(side=tk.LEFT)

        self.lbl_estado_hf = tk.Label(contenido, text="", font=("Segoe UI", 9, "italic"), wraplength=700, justify="left")
        self.lbl_estado_hf.pack(anchor="w", pady=(8, 0))
        self._registrar_texto(self.lbl_estado_hf, "bg", dim=True)

        return pagina

    def buscar_modelos_hf_hilo(self):
        consulta = self.var_busqueda_hf.get().strip()
        if not consulta:
            messagebox.showwarning("Advertencia", "Escribe algo para buscar (ej: 'qwen2.5 coder gguf').")
            return
        self.btn_buscar_hf.config(state=tk.DISABLED)
        self.lista_resultados_hf.delete(0, tk.END)
        self.resultados_hf = []
        self.lbl_estado_hf.config(text="Buscando en Hugging Face...")
        hilo = threading.Thread(target=self._buscar_modelos_hf, args=(consulta,), daemon=True)
        hilo.start()

    def _buscar_modelos_hf(self, consulta):
        try:
            url = "https://huggingface.co/api/models?" + urllib.parse.urlencode(
                {"search": consulta, "filter": "gguf", "limit": 15, "sort": "downloads", "direction": -1}
            )
            with urllib.request.urlopen(url, timeout=15) as resp:
                modelos = json.loads(resp.read().decode("utf-8"))

            resultados = []
            for m in modelos[:15]:
                repo_id = m.get("id") or m.get("modelId")
                if not repo_id:
                    continue
                try:
                    url_detalle = f"https://huggingface.co/api/models/{urllib.parse.quote(repo_id)}"
                    with urllib.request.urlopen(url_detalle, timeout=15) as resp2:
                        detalle = json.loads(resp2.read().decode("utf-8"))
                    for sib in detalle.get("siblings", []):
                        nombre_archivo = sib.get("rfilename", "")
                        if nombre_archivo.lower().endswith(".gguf"):
                            resultados.append({"repo_id": repo_id, "archivo": nombre_archivo, "size": sib.get("size")})
                except Exception:
                    continue

            self.root.after(0, lambda: self._mostrar_resultados_hf(resultados))
        except Exception as e:
            mensaje_error = str(e)
            self.root.after(0, lambda: self._error_busqueda_hf(mensaje_error))

    def _mostrar_resultados_hf(self, resultados):
        self.resultados_hf = resultados
        self.lista_resultados_hf.delete(0, tk.END)
        if not resultados:
            self.lbl_estado_hf.config(text="No se encontraron archivos .gguf para esa búsqueda.")
        else:
            for r in resultados:
                tam = f"{r['size']/(1024**3):.2f} GB" if r.get("size") else "tamaño desconocido"
                self.lista_resultados_hf.insert(tk.END, f"{r['repo_id']}  →  {r['archivo']}   ({tam})")
            self.lbl_estado_hf.config(text=f"{len(resultados)} archivo(s) .gguf encontrados.")
        self.btn_buscar_hf.config(state=tk.NORMAL)

    def _error_busqueda_hf(self, mensaje):
        self.lbl_estado_hf.config(text=f"Error al buscar: {mensaje}")
        self.btn_buscar_hf.config(state=tk.NORMAL)

    def _al_seleccionar_resultado_hf(self, evento):
        seleccion = self.lista_resultados_hf.curselection()
        if not seleccion:
            self.archivo_hf_seleccionado = None
            self.btn_descargar_hf.config(state=tk.DISABLED)
            return
        self.archivo_hf_seleccionado = self.resultados_hf[seleccion[0]]
        self.btn_descargar_hf.config(state=tk.NORMAL)

    def confirmar_descarga_hf(self):
        if not self.archivo_hf_seleccionado:
            return
        info = self.archivo_hf_seleccionado
        tam = f"{info['size']/(1024**3):.2f} GB" if info.get("size") else "tamaño desconocido"
        carpeta_destino = filedialog.askdirectory(title="Elige la carpeta donde guardar el modelo descargado")
        if not carpeta_destino:
            return
        confirmar = messagebox.askyesno(
            "Confirmar descarga",
            f"¿Descargar este archivo?\n\nRepositorio: {info['repo_id']}\nArchivo: {info['archivo']}\nTamaño: {tam}\nDestino: {carpeta_destino}",
        )
        if not confirmar:
            return
        self.btn_descargar_hf.config(state=tk.DISABLED)
        hilo = threading.Thread(target=self._descargar_archivo_hf, args=(info, carpeta_destino), daemon=True)
        hilo.start()

    def _descargar_archivo_hf(self, info, carpeta_destino):
        url = f"https://huggingface.co/{info['repo_id']}/resolve/main/{info['archivo']}"
        destino = os.path.join(carpeta_destino, info["archivo"])
        try:
            def _reportar(bloques, tam_bloque, total):
                if total > 0:
                    pct = min(100, bloques * tam_bloque * 100 // total)
                    self.root.after(0, lambda: self.lbl_estado_hf.config(text=f"Descargando... {pct}%"))

            urllib.request.urlretrieve(url, destino, reporthook=_reportar)

            if carpeta_destino not in self.carpetas_modelos:
                self.carpetas_modelos.append(carpeta_destino)
                guardar_carpetas_modelos(self.carpetas_modelos)
                if hasattr(self, "lista_carpetas"):
                    self.root.after(0, self._refrescar_lista_carpetas)

            self.root.after(0, lambda: self.lbl_estado_hf.config(text=f"✅ Descargado en: {destino}"))
            self.root.after(0, self.cargar_modelos)
        except Exception as e:
            mensaje_error = str(e)
            self.root.after(0, lambda: self.lbl_estado_hf.config(text=f"Error al descargar: {mensaje_error}"))
        finally:
            self.root.after(0, lambda: self.btn_descargar_hf.config(state=tk.NORMAL))

    # ==================================================================
    # PAGINA: APARIENCIA (personalizar colores)
    # ==================================================================
    def _pagina_apariencia(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "🎨 Apariencia")

        panel_modo = self._crear_panel(contenido, "Modo de color")
        self._crear_label_dim(
            panel_modo,
            "Cambia entre día y noche: combina automáticamente el color elegido\n"
            "para que las letras siempre se vean bien, sin importar el color.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
        fila_modo = tk.Frame(panel_modo)
        fila_modo.pack(fill=tk.X, padx=12, pady=(0, 14))
        self._widgets_panel.append(("panel", fila_modo))
        self.btn_modo_dia = self._crear_boton(fila_modo, "☀️ Día", lambda: self.cambiar_modo_color(False))
        self.btn_modo_dia.pack(side=tk.LEFT)
        self.btn_modo_noche = self._crear_boton(fila_modo, "🌙 Noche", lambda: self.cambiar_modo_color(True))
        self.btn_modo_noche.pack(side=tk.LEFT, padx=(8, 0))

        panel = self._crear_panel(contenido, "Paletas rápidas")
        fila_paletas = tk.Frame(panel)
        fila_paletas.pack(fill=tk.X, padx=12, pady=(0, 14))
        self._widgets_panel.append(("panel", fila_paletas))
        for nombre in PALETAS:
            col = tk.Frame(fila_paletas)
            col.pack(side=tk.LEFT, padx=(0, 16))
            self._widgets_panel.append(("panel", col))
            sw = tk.Canvas(col, width=40, height=40, highlightthickness=2, cursor="hand2")
            sw.configure(bg=PALETAS[nombre]["acento"], highlightbackground=PALETAS[nombre]["bg"])
            sw.pack()
            sw.bind("<Button-1>", lambda e, n=nombre: self.aplicar_paleta(n))
            lbl = tk.Label(col, text=nombre, font=("Segoe UI", 8))
            lbl.pack(pady=(4, 0))
            self._registrar_texto(lbl, "panel", dim=True)

        panel2 = self._crear_panel(contenido, "Colores personalizados")
        fila_custom = tk.Frame(panel2)
        fila_custom.pack(fill=tk.X, padx=12, pady=(0, 14))
        self._widgets_panel.append(("panel", fila_custom))
        self._swatches_custom = {}
        for etiqueta, clave in [("Acento", "acento"), ("Fondo", "bg"), ("Panel", "panel"), ("Texto", "texto")]:
            col = tk.Frame(fila_custom)
            col.pack(side=tk.LEFT, padx=(0, 16))
            self._widgets_panel.append(("panel", col))
            lbl = tk.Label(col, text=etiqueta, font=("Segoe UI", 8))
            lbl.pack()
            self._registrar_texto(lbl, "panel", dim=True)
            sw = tk.Canvas(col, width=44, height=26, highlightthickness=1, cursor="hand2")
            sw.pack(pady=(4, 0))
            sw.bind("<Button-1>", lambda e, k=clave: self._elegir_color_custom(k))
            self._swatches_custom[clave] = sw

        self._boton_reset_tema = self._crear_boton(contenido, "↺ Restablecer tema por defecto", self.restablecer_tema)
        self._boton_reset_tema.pack(anchor="w")

        return pagina

    def _elegir_color_custom(self, clave):
        color_actual = self.tema.get(clave, "#000000")
        resultado = colorchooser.askcolor(color=color_actual, title=f"Elegir color: {clave}")
        if resultado and resultado[1]:
            if clave == "acento":
                # Recombina toda la paleta a partir del nuevo acento, respetando
                # el modo dia/noche actual, para que el contraste de las letras
                # siempre quede correcto sea cual sea el color elegido.
                self.tema = generar_paleta_desde_acento(resultado[1], self._modo_noche_actual())
            else:
                self.tema[clave] = resultado[1]
            self.aplicar_tema()
            guardar_tema(self.tema)

    def aplicar_paleta(self, nombre):
        self.tema = dict(PALETAS[nombre])
        self.aplicar_tema()
        guardar_tema(self.tema)

    def _modo_noche_actual(self):
        return _luminancia_relativa(self.tema.get("bg", "#FFFFFF")) < 0.5

    def cambiar_modo_color(self, noche):
        """Recombina la paleta actual (a partir de su color de acento) para
        modo dia o modo noche, sin perder el color elegido y garantizando
        que el texto siga siendo legible en ambos casos."""
        acento_base = self.tema.get("acento", PALETAS[TEMA_POR_DEFECTO]["acento"])
        self.tema = generar_paleta_desde_acento(acento_base, noche)
        self.aplicar_tema()
        guardar_tema(self.tema)

    def restablecer_tema(self):
        self.aplicar_paleta(TEMA_POR_DEFECTO)

    # ==================================================================
    # PAGINA: ACERCA DE
    # ==================================================================
    def _cargar_logo_gmn(self):
        if hasattr(self, "_logo_gmn_img"):
            return self._logo_gmn_img
        self._logo_gmn_img = None
        if os.path.isfile(RUTA_LOGO_GMN):
            try:
                img = tk.PhotoImage(file=RUTA_LOGO_GMN)
                # La imagen fuente es grande (logo cuadrado en alta resolucion);
                # se reduce a un tamano razonable para un panel "Acerca de".
                factor = max(1, img.width() // 220)
                if factor > 1:
                    img = img.subsample(factor, factor)
                self._logo_gmn_img = img
            except Exception:
                self._logo_gmn_img = None
        return self._logo_gmn_img

    def _pagina_acerca(self, padre):
        pagina, contenido = self._nueva_pagina(padre, "ℹ️ Acerca de este programa")

        logo = self._cargar_logo_gmn()
        if logo is not None:
            lbl_logo = tk.Label(contenido, image=logo)
            lbl_logo.image = logo
            lbl_logo.pack(anchor="w", pady=(0, 12))
            self._registrar_texto(lbl_logo, "bg", dim=False)

        texto = "© 2026 G.M.N TechLab\nCreado por G.M.N TechLab · construido sobre llama.cpp\nCódigo abierto: github.com/jediknightgeorge-ship-it/gmn-ai"
        lbl = tk.Label(contenido, text=texto, font=("Segoe UI", 10), justify="left")
        lbl.pack(anchor="w")
        self._registrar_texto(lbl, "bg", dim=True)
        return pagina

    def _set_estado(self, texto, tipo=None):
        self.lbl_estado.config(text=texto)
        self._actualizar_color_estado(tipo)
        self.lbl_estado_sidebar.config(text=texto[:60])

    # ==================================================================
    # APLICAR TEMA A TODOS LOS WIDGETS
    # ==================================================================
    def aplicar_tema(self):
        t = self.tema

        self.root.configure(bg=t["bg"])
        self.header_canvas.configure(bg=t["bg"])
        self._redibujar_header()

        # ttk (campos, listas desplegables, barras de scroll): planos y finos,
        # con borde de una linea del color de la tarjeta, como en macOS.
        campo = mezclar(t["panel"], t["bg"], 0.65)
        self.style.configure(".", background=t["bg"], foreground=t["texto"])
        self.style.configure("TEntry", fieldbackground=campo, foreground=t["texto"], insertcolor=t["texto"],
                             bordercolor=t["borde"], lightcolor=t["borde"], darkcolor=t["borde"], padding=6, relief="flat")
        self.style.map("TEntry", fieldbackground=[("readonly", campo)], foreground=[("readonly", t["texto_dim"])],
                       bordercolor=[("focus", t["acento"])], lightcolor=[("focus", t["acento"])], darkcolor=[("focus", t["acento"])])
        self.style.configure("TCombobox", fieldbackground=campo, background=campo, foreground=t["texto"],
                             arrowcolor=t["texto_dim"], bordercolor=t["borde"], lightcolor=t["borde"],
                             darkcolor=t["borde"], padding=6, relief="flat", arrowsize=14)
        self.style.map("TCombobox", fieldbackground=[("readonly", campo)], foreground=[("readonly", t["texto"])],
                       bordercolor=[("focus", t["acento"])], lightcolor=[("focus", t["acento"])],
                       darkcolor=[("focus", t["acento"])], background=[("active", campo)])
        self.root.option_add("*TCombobox*Listbox.background", t["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["texto"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["acento"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["acento_texto"])
        # Scrollbar fina sin flechas (como las barras overlay de macOS).
        self.style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        self.style.configure("Vertical.TScrollbar", background=mezclar(t["borde"], t["texto_dim"], 0.35),
                             troughcolor=t["bg"], bordercolor=t["bg"], lightcolor=t["bg"], darkcolor=t["bg"],
                             gripcount=0, arrowsize=0, width=10)
        self.style.map("Vertical.TScrollbar", background=[("active", t["texto_dim"])])

        color_sidebar = self._color_sidebar()
        for tipo, w in self._widgets_panel:
            try:
                if tipo == "bg":
                    w.configure(bg=t["bg"])
                elif tipo == "panel":
                    w.configure(bg=t["panel"])
                elif tipo == "sidebar":
                    w.configure(bg=color_sidebar)
                elif tipo == "borde":
                    w.configure(bg=t["borde"])
                elif tipo == "panel_borde":
                    w.configure(bg=t["panel"], highlightbackground=t["borde"], highlightcolor=t["borde"],
                                highlightthickness=1, bd=0, relief="flat")
                elif tipo == "check":
                    w.configure(bg=t["panel"], fg=t["texto"], activebackground=t["panel"], activeforeground=t["texto"],
                                selectcolor=t["panel"], highlightthickness=0)
                elif tipo == "check_bg":  # checkbox que vive sobre el fondo de la pagina, no en una tarjeta
                    w.configure(bg=t["bg"], fg=t["texto"], activebackground=t["bg"], activeforeground=t["texto"],
                                selectcolor=t["panel"], highlightthickness=0)
            except tk.TclError:
                pass

        for widget, fondo_clave, dim, subtitulo in self._widgets_texto:
            try:
                bg = {"panel": t["panel"], "sidebar": color_sidebar}.get(fondo_clave, t["bg"])
                if subtitulo:
                    fg = t["texto"]
                elif dim:
                    fg = t["texto_dim"]
                else:
                    fg = t["texto"]
                widget.configure(bg=bg, fg=fg)
            except tk.TclError:
                pass

        try:
            self.txt_chat.configure(bg=t["panel"], fg=t["texto"], insertbackground=t["texto"])
        except (AttributeError, tk.TclError):
            pass

        # Botones principales (primario = acento, secundario = gris suave, peligro = rojo suave)
        self.btn_iniciar.configure(**self._est_primario())
        self.btn_detener.configure(**self._est_peligro())
        self.btn_agentes.configure(**self._est_primario())
        self.btn_copiar.configure(**self._est_secundario())
        self._boton_reset_tema.configure(**self._est_secundario())
        self.btn_enviar_chat.configure(**self._est_primario())

        if hasattr(self, "btn_tunel"):
            self.btn_tunel.configure(**self._est_primario())
            self.btn_tunel_detener.configure(**self._est_peligro())

        if hasattr(self, "lista_carpetas"):
            self._refrescar_lista_carpetas()

        if hasattr(self, "lista_resultados_hf"):
            self.lista_resultados_hf.configure(bg=t["panel"], fg=t["texto"], selectbackground=t["acento"],
                                               selectforeground=t["acento_texto"], highlightthickness=0, bd=0)
            self.btn_buscar_hf.configure(**self._est_primario())
            self.btn_descargar_hf.configure(**self._est_primario())

        for b in getattr(self, "_botones_preset", []):
            b.configure(**self._est_secundario())

        for clave, sw in getattr(self, "_swatches_custom", {}).items():
            sw.configure(bg=t.get(clave, "#000000"), highlightbackground=t["borde"])

        if hasattr(self, "btn_modo_dia"):
            noche = self._modo_noche_actual()
            self.btn_modo_dia.configure(**(self._est_secundario() if noche else self._est_primario()))
            self.btn_modo_noche.configure(**(self._est_primario() if noche else self._est_secundario()))

        # Botones "copiar config" y sidebar (buscados por texto no es practico; recorremos todo)
        self._recolorear_botones_genericos(self.area_contenido)
        self._recolorear_botones_genericos(self.sidebar, es_sidebar=True)

        if hasattr(self, "modelos_info"):
            self._dibujar_modelos(getattr(self, "_modelos_filtrados_actual", self.modelos_info))

        if hasattr(self, "lbl_estado"):
            self._actualizar_color_estado()

        if hasattr(self, "_botones_sidebar"):
            self._estilo_sidebar()

        # Repinta las tarjetas redondeadas con los colores nuevos.
        self._repintar_tarjetas()

    def _recolorear_botones_genericos(self, contenedor, es_sidebar=False):
        botones_ya_manejados = {
            id(getattr(self, n, None)) for n in
            ["btn_iniciar", "btn_detener", "btn_agentes", "btn_copiar", "_boton_reset_tema",
             "btn_enviar_chat", "btn_tunel", "btn_tunel_detener", "btn_modo_dia", "btn_modo_noche"]
        }
        for w in contenedor.winfo_children():
            if (isinstance(w, (tk.Button, BotonRedondo)) and id(w) not in botones_ya_manejados
                    and w not in self._botones_sidebar.values()):
                try:
                    if not es_sidebar:
                        estilo = self._est_primario() if getattr(w, "_primario", False) else self._est_secundario()
                        w.configure(**estilo)
                except tk.TclError:
                    pass
            self._recolorear_botones_genericos(w, es_sidebar=es_sidebar)

    # ==================================================================
    # BOTON PRINCIPAL: hover + pulso de brillo
    # ==================================================================
    def on_enter_btn(self, event):
        if self.btn_iniciar["state"] == tk.NORMAL:
            self.btn_iniciar.config(bg=self.tema["acento_hover"])

    def on_leave_btn(self, event):
        if self.btn_iniciar["state"] == tk.NORMAL:
            self.btn_iniciar.config(bg=self.tema["acento"])

    def _iniciar_pulso_boton(self):
        self._tick_pulso()

    def _tick_pulso(self):
        if self.btn_iniciar["state"] == tk.NORMAL and not self.servidor_listo:
            self._pulso_t += 0.06 * self._pulso_dir
            if self._pulso_t >= 1.0:
                self._pulso_t = 1.0
                self._pulso_dir = -1
            elif self._pulso_t <= 0.0:
                self._pulso_t = 0.0
                self._pulso_dir = 1
            color = interpolar_hex(self.tema["acento"], self.tema["acento_hover"], self._pulso_t)
            try:
                self.btn_iniciar.config(bg=color)
            except tk.TclError:
                pass
        self._pulso_job = self.root.after(60, self._tick_pulso)

    # ------------------------------------------------------------------
    # TURBOQUANT
    # ------------------------------------------------------------------
    def _al_cambiar_turboquant(self):
        estado = "readonly" if self.var_turboquant.get() else "disabled"
        self.combo_kv_k.config(state=estado)
        self.combo_kv_v.config(state=estado)
        if not self.var_turboquant.get():
            self.var_kv_k.set("f16")
            self.var_kv_v.set("f16")

    def aplicar_preset_muestreo(self, nombre_preset):
        p = PRESETS_MUESTREO[nombre_preset]
        self.var_temp.set(p["temp"])
        self.var_top_p.set(p["top_p"])
        self.var_top_k.set(p["top_k"])
        self.var_min_p.set(p["min_p"])
        self.var_repeat_penalty.set(p["repeat"])
        self.var_presence_penalty.set(p["presence"])
        self.var_dry.set(p["dry"])
        self.var_reasoning_budget.set(p["reasoning"])
        self._set_estado(f"🎚️ Muestreo '{nombre_preset}' aplicado (se usa al cargar el modelo).", "ok")

    def aplicar_preset_modelo_grande(self):
        """Config para modelos grandes (tipicamente MoE con pocos parametros
        activos, como Nemotron 3 Nano 30B): contexto automatico dentro de la
        VRAM libre + cache KV q8_0 + Flash Attention + capas en GPU 'auto'."""
        self.var_auto_fit.set(True)
        self.var_fit_margen.set("512")
        self.var_ngl.set("auto")
        self.var_turboquant.set(True)
        self.var_kv_k.set("q8_0")
        self.var_kv_v.set("q8_0")
        self._al_cambiar_turboquant()
        self._set_estado("⚡ Preset 'modelo grande rápido' aplicado: contexto auto + margen 512 MB + caché KV q8_0.", "ok")

    def listar_dispositivos(self):
        """Muestra los dispositivos que ve llama.cpp (CUDA, Vulkan, CPU...)
        ejecutando 'llama-server.exe --list-devices' sin bloquear la ventana."""
        ruta = self.var_ruta_llama_server.get()
        if not os.path.isfile(ruta):
            messagebox.showwarning("Dispositivos", "Primero indica dónde está llama-server.exe (arriba).")
            return

        def _trabajo():
            try:
                r = subprocess.run([ruta, "--list-devices"], capture_output=True, text=True, timeout=60,
                                   creationflags=subprocess.CREATE_NO_WINDOW, cwd=os.path.dirname(ruta))
                texto = (r.stdout + "\n" + r.stderr).strip() or "(sin salida)"
            except Exception as e:
                texto = f"No se pudo ejecutar: {e}"
            self.root.after(0, lambda: messagebox.showinfo("Dispositivos disponibles", texto[-1800:]))

        threading.Thread(target=_trabajo, daemon=True).start()

    def aplicar_preset_turboquant(self, nombre_preset):
        preset = PRESETS_TURBOQUANT[nombre_preset]
        self.var_turboquant.set(preset["activar"])
        self.var_kv_k.set(preset["k"])
        self.var_kv_v.set(preset["v"])
        self._al_cambiar_turboquant()

    # ------------------------------------------------------------------
    # LISTADO DE MODELOS
    # ------------------------------------------------------------------
    def _clasificar_tamano(self, gb):
        t = self.tema
        if gb <= 7:
            return "🟢", t["ok"]
        if gb <= 9.5:
            return "🟡", t["warn"]
        return "🔴", t["peligro"]

    def _refrescar_lista_carpetas(self):
        self.lista_carpetas.delete(0, tk.END)
        for carpeta in self.carpetas_modelos:
            existe = "" if os.path.isdir(carpeta) else "  ⚠ no encontrada"
            self.lista_carpetas.insert(tk.END, f"{carpeta}{existe}")
        t = self.tema
        self.lista_carpetas.configure(bg=mezclar(t["panel"], t["bg"], 0.65), fg=t["texto"], selectbackground=t["acento"],
                                       selectforeground=t["acento_texto"], highlightbackground=t["borde"],
                                       highlightcolor=t["acento"], highlightthickness=1, relief="flat", bd=0,
                                       font=("Segoe UI", 9))

    def cambiar_ruta_llama_server(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona llama-server.exe", filetypes=[("llama-server.exe", "llama-server.exe"), ("Ejecutables", "*.exe")],
        )
        if not ruta:
            return
        self.var_ruta_llama_server.set(ruta)
        guardar_ruta_llama_server(ruta)
        self._set_estado(f"🦙 Ruta de llama-server.exe actualizada: {ruta}", "ok")
        self._al_cambiar_modo_fx()

    # ==================================================================
    # PERFILES DE CONFIGURACION
    # ==================================================================
    def _campos_perfil(self):
        """Mapa clave->Variable de todas las opciones que guarda un perfil.

        Centralizado aqui: para que una opcion nueva del programa quede
        incluida en guardar/cargar perfiles solo hay que agregarla a este
        diccionario, no hay que tocar guardar_perfil_actual/cargar_perfil.
        """
        return {
            "ruta_llama_server": self.var_ruta_llama_server,
            "modelo": self.modelo_seleccionado,
            "host": self.var_host,
            "puerto": self.var_port,
            "contexto": self.var_contexto,
            "turboquant": self.var_turboquant,
            "kv_k": self.var_kv_k,
            "kv_v": self.var_kv_v,
            "ngl": self.var_ngl,
            "threads": self.var_threads,
            "threads_batch": self.var_threads_batch,
            "batch_size": self.var_batch_size,
            "ubatch_size": self.var_ubatch_size,
            "no_mmap": self.var_no_mmap,
            "load_mode": self.var_load_mode,
            "lora": self.var_lora,
            "lora_scale": self.var_lora_scale,
            "auto_fit": self.var_auto_fit,
            "fit_margen": self.var_fit_margen,
            "busqueda_web_tool": self.var_busqueda_web_tool,
            "numa": self.var_numa,
            "modelo_draft": self.var_modelo_draft,
            "tipo_spec": self.var_tipo_spec,
            "spec_n_max": self.var_spec_n_max,
            "spec_p_min": self.var_spec_p_min,
            "spec_draft_ngl": self.var_spec_draft_ngl,
            "spec_draft_kv_k": self.var_spec_draft_kv_k,
            "spec_draft_kv_v": self.var_spec_draft_kv_v,
            "moe_modo": self.var_moe_modo,
            "moe_n_capas": self.var_moe_n_capas,
            "mmproj": self.var_mmproj,
            "modo_router": self.var_modo_router,
            "models_max": self.var_models_max,
            "models_autoload": self.var_models_autoload,
            "api_key": self.var_api_key,
            "cors_origins": self.var_cors_origins,
            "temperatura": self.var_temp,
            "top_p": self.var_top_p,
            "top_k": self.var_top_k,
            "min_p": self.var_min_p,
            "repeat_penalty": self.var_repeat_penalty,
            "presence_penalty": self.var_presence_penalty,
            "dry": self.var_dry,
            "reasoning_budget": self.var_reasoning_budget,
            "rope_modo": self.var_rope_modo,
            "yarn_orig": self.var_yarn_orig,
            "dispositivos": self.var_dispositivos,
            "tensor_split": self.var_tensor_split,
            "split_mode": self.var_split_mode,
            "main_gpu": self.var_main_gpu,
            "timeout": self.var_timeout,
            "modo_fx": self.var_modo_fx,
        }

    def guardar_perfil_actual(self):
        nombre = (self.var_perfil_actual.get() or "").strip()
        if not nombre:
            nombre = simpledialog.askstring("Guardar perfil", "Nombre del perfil nuevo:", parent=self.root)
            if not nombre:
                return
            nombre = nombre.strip()
        if not nombre:
            return
        if nombre in PERFILES_INCLUIDOS:
            messagebox.showinfo("Perfiles", "Ese nombre es de un perfil incluido (★). Escribe otro nombre\n"
                                            "para guardar tu propia versión.")
            return
        datos = {clave: var.get() for clave, var in self._campos_perfil().items()}
        self.perfiles_guardados[nombre] = datos
        guardar_perfiles(self.perfiles_guardados)
        self.var_perfil_actual.set(nombre)
        self._refrescar_combo_perfiles()
        self._set_estado(f"💾 Perfil '{nombre}' guardado con toda la configuración actual.", "ok")

    def cargar_perfil_seleccionado(self):
        nombre = self.var_perfil_actual.get()
        if nombre in PERFILES_INCLUIDOS:
            datos = PERFILES_INCLUIDOS[nombre]["valores"]
        else:
            datos = self.perfiles_guardados.get(nombre)
        if not datos:
            messagebox.showwarning("Perfiles", "Elige un perfil guardado de la lista.")
            return
        campos = self._campos_perfil()
        for clave, valor in datos.items():
            var = campos.get(clave)
            if var is None:
                continue
            try:
                var.set(valor)
            except Exception:
                pass
        self._hilos_fue_auto_fx = False
        self._actualizar_estado_moe()
        self._actualizar_estado_draft()
        self._al_cambiar_turboquant()
        self._al_cambiar_modo_fx()
        self._set_estado(f"📂 Perfil '{nombre}' cargado.", "ok")

    def eliminar_perfil_seleccionado(self):
        nombre = self.var_perfil_actual.get()
        if nombre in PERFILES_INCLUIDOS:
            messagebox.showinfo("Perfiles", "Los perfiles con ★ vienen incluidos y no se pueden eliminar.\n"
                                            "Puedes guardar una copia con otro nombre y borrar esa.")
            return
        if not nombre or nombre not in self.perfiles_guardados:
            messagebox.showwarning("Perfiles", "Elige un perfil guardado de la lista.")
            return
        if not messagebox.askyesno("Eliminar perfil", f"¿Eliminar el perfil '{nombre}'?"):
            return
        del self.perfiles_guardados[nombre]
        guardar_perfiles(self.perfiles_guardados)
        self.var_perfil_actual.set("")
        self._refrescar_combo_perfiles()
        self._set_estado(f"🗑 Perfil eliminado.", "ok")

    def _nombres_perfiles(self):
        """Primero los incluidos (con ★), despues los que guardo el usuario."""
        return list(PERFILES_INCLUIDOS.keys()) + list(self.perfiles_guardados.keys())

    def _refrescar_combo_perfiles(self):
        if hasattr(self, "combo_perfiles"):
            self.combo_perfiles["values"] = self._nombres_perfiles()

    def _al_elegir_perfil(self):
        """Los perfiles incluidos se aplican al elegirlos (un solo clic) y
        muestran para que sirven; los del usuario se cargan con 'Cargar'."""
        nombre = self.var_perfil_actual.get()
        if nombre in PERFILES_INCLUIDOS:
            self.lbl_desc_perfil.config(text=PERFILES_INCLUIDOS[nombre]["descripcion"])
            self.cargar_perfil_seleccionado()
        else:
            self.lbl_desc_perfil.config(text="")

    # ==================================================================
    # MODO FX: rutinas nativas AVX + FMA4 (AMD Family 15h, ej. FX-8320E)
    # ==================================================================
    def _al_cambiar_modo_fx(self):
        activo = self.var_modo_fx.get()
        if activo:
            hilos_actuales = self.var_threads.get().strip()
            if not hilos_actuales or self._hilos_fue_auto_fx:
                self.var_threads.set("4")
                self._hilos_fue_auto_fx = True
        elif self._hilos_fue_auto_fx:
            self.var_threads.set("")
            self._hilos_fue_auto_fx = False

        if not hasattr(self, "lbl_estado_fx"):
            return
        if not activo:
            self.lbl_estado_fx.config(text="")
            return

        ruta_llama = self.var_ruta_llama_server.get()
        carpeta = os.path.dirname(ruta_llama) if ruta_llama else ""
        dll_ok = os.path.isfile(os.path.join(carpeta, "ggml-cpu-piledriver.dll"))
        if dll_ok:
            self.lbl_estado_fx.config(
                text=(
                    "✅ 'ggml-cpu-piledriver.dll' encontrado junto a llama-server.exe: el motor\n"
                    "detecta tu CPU (AMD Family 15h) solo por CPUID y usa sus rutinas nativas de\n"
                    "AVX + FMA4, sin tocar AVX2/FMA3 (que tu FX no tiene — forzarlas lo haría\n"
                    "crashear). Hilos de CPU puestos en 4: los 4 módulos físicos del FX-8320E\n"
                    "comparten una sola FPU por módulo, así que más hilos no rinden más aquí —\n"
                    "lo que de verdad acelera la parte pesada sigue siendo '-ngl' alto (GPU)."
                ),
            )
        else:
            self.lbl_estado_fx.config(
                text=(
                    "⚠️ No se encontró 'ggml-cpu-piledriver.dll' junto al llama-server.exe\n"
                    "configurado arriba — esa build de llama.cpp puede ser muy vieja o no traer\n"
                    "despacho automático por CPU. Cambia a una build reciente (b10948 o más\n"
                    "nueva) para que detecte tu FX y use sus instrucciones nativas."
                ),
            )

    def elegir_modelo_draft(self):
        ruta = filedialog.askopenfilename(title="Selecciona el modelo draft (.gguf)", filetypes=[("Modelos GGUF", "*.gguf")])
        if not ruta:
            return
        self.var_modelo_draft.set(ruta)
        self._set_estado(f"🚀 Modelo draft seleccionado: {os.path.basename(ruta)}", "ok")

    def quitar_modelo_draft(self):
        self.var_modelo_draft.set("")

    def elegir_lora(self):
        ruta = filedialog.askopenfilename(title="Selecciona el adaptador LoRA (.gguf)", filetypes=[("LoRA GGUF", "*.gguf")])
        if not ruta:
            return
        self.var_lora.set(ruta)
        self._set_estado(f"🎛️ LoRA seleccionado: {os.path.basename(ruta)}", "ok")

    def quitar_lora(self):
        self.var_lora.set("")
        self.var_lora_scale.set("")

    def _actualizar_estado_draft(self):
        necesita_draft = self.var_tipo_spec.get() == "Con modelo draft"
        estado = tk.NORMAL if necesita_draft else tk.DISABLED
        self.btn_elegir_draft.config(state=estado)
        self.btn_quitar_draft.config(state=estado)
        if not necesita_draft:
            self.var_modelo_draft.set("")

    def _actualizar_estado_moe(self):
        necesita_n = self.var_moe_modo.get() == "Primeras N capas en CPU (-ncmoe)"
        self.entrada_moe_n.config(state=tk.NORMAL if necesita_n else tk.DISABLED)
        if not necesita_n:
            self.var_moe_n_capas.set("")

    def elegir_mmproj(self):
        ruta = filedialog.askopenfilename(title="Selecciona el archivo mmproj (.gguf)", filetypes=[("Proyector mmproj", "*.gguf")])
        if not ruta:
            return
        self.var_mmproj.set(ruta)
        self._set_estado(f"👁️ mmproj seleccionado: {os.path.basename(ruta)}", "ok")

    def agregar_carpeta_modelos(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta donde tienes modelos .gguf")
        if not carpeta:
            return
        carpeta = os.path.normpath(carpeta)
        if carpeta in self.carpetas_modelos:
            self._set_estado("Esa carpeta ya estaba en la lista.")
            return
        self.carpetas_modelos.append(carpeta)
        guardar_carpetas_modelos(self.carpetas_modelos)
        self._refrescar_lista_carpetas()
        self.cargar_modelos()
        self._set_estado(f"📁 Carpeta agregada: {carpeta}", "ok")

    def quitar_carpeta_modelos(self):
        seleccion = self.lista_carpetas.curselection()
        if not seleccion:
            messagebox.showinfo("Quitar carpeta", "Selecciona primero una carpeta de la lista.")
            return
        indice = seleccion[0]
        if len(self.carpetas_modelos) <= 1:
            messagebox.showwarning("Advertencia", "Debe quedar al menos una carpeta configurada.")
            return
        carpeta = self.carpetas_modelos.pop(indice)
        guardar_carpetas_modelos(self.carpetas_modelos)
        self._refrescar_lista_carpetas()
        self.cargar_modelos()
        self._set_estado(f"🗑 Carpeta quitada: {carpeta}")

    def cargar_modelos(self):
        self.modelos_info = []
        rutas_vistas = set()
        carpetas_con_error = []
        for carpeta in self.carpetas_modelos:
            if not os.path.isdir(carpeta):
                continue
            try:
                with os.scandir(carpeta) as entradas:
                    for entrada in entradas:
                        nombre = entrada.name
                        if not entrada.is_file() or not nombre.lower().endswith(".gguf"):
                            continue
                        if "mmproj" in nombre.lower():
                            continue
                        ruta_completa = os.path.normpath(entrada.path)
                        if ruta_completa in rutas_vistas:
                            continue
                        rutas_vistas.add(ruta_completa)
                        gb = entrada.stat().st_size / (1024**3)
                        self.modelos_info.append((nombre, ruta_completa, gb))
            except Exception as e:
                carpetas_con_error.append(f"{carpeta}: {e}")

        if carpetas_con_error:
            messagebox.showwarning("Aviso", "No se pudieron leer algunas carpetas:\n" + "\n".join(carpetas_con_error))

        self.modelos_info.sort(key=lambda x: x[0].lower())
        self._dibujar_modelos(self.modelos_info)

    def _mostrar_ruta_en_lista(self):
        # Solo mostramos la carpeta de origen junto al nombre si hay mas de una
        # carpeta configurada, para no ensuciar la vista en el caso normal.
        return len([c for c in self.carpetas_modelos if os.path.isdir(c)]) > 1

    def _dibujar_modelos(self, modelos):
        self._modelos_filtrados_actual = modelos
        t = self.tema
        for widget in self.frame_modelos.winfo_children():
            widget.destroy()

        if not modelos:
            tk.Label(
                self.frame_modelos, text="❌ No se encontraron archivos .gguf en las carpetas configuradas.",
                bg=t["panel"], fg=t["peligro"], font=("Segoe UI", 10, "bold"),
            ).pack(anchor=tk.W, pady=10, padx=10)
            return

        mostrar_ruta = self._mostrar_ruta_en_lista()
        seleccion_previa = self.modelo_seleccionado.get()
        rutas_disponibles = [m[1] for m in modelos]
        if seleccion_previa not in rutas_disponibles:
            self.modelo_seleccionado.set(rutas_disponibles[0])

        for nombre, ruta_completa, gb in modelos:
            icono, color = self._clasificar_tamano(gb)
            fila = tk.Frame(self.frame_modelos, bg=t["panel"])
            fila.pack(fill=tk.X, padx=6, pady=3)

            texto_rb = nombre
            if mostrar_ruta:
                texto_rb = f"{nombre}   ({os.path.dirname(ruta_completa)})"

            rb = tk.Radiobutton(
                fila, text=texto_rb, value=ruta_completa, variable=self.modelo_seleccionado,
                bg=t["panel"], fg=t["texto"], selectcolor=t["bg"], activebackground=t["panel"],
                activeforeground=t["acento"], font=("Segoe UI", 9), anchor="w",
            )
            rb.pack(side=tk.LEFT, anchor=tk.W)

            tk.Label(fila, text=f"{icono} {gb:.1f} GB", bg=t["panel"], fg=color, font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=8)

    def filtrar_modelos(self):
        texto = self.filtro_busqueda.get().lower().strip()
        if not texto:
            self._dibujar_modelos(self.modelos_info)
            return
        filtrados = [m for m in self.modelos_info if texto in m[0].lower()]
        self._dibujar_modelos(filtrados)

    # ------------------------------------------------------------------
    # PUERTO LIBRE
    # ------------------------------------------------------------------
    def _puerto_libre(self, host, puerto_inicial):
        puerto = int(puerto_inicial)
        for intento in range(20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((host, puerto)) != 0:
                    return puerto
            puerto += 1
        return puerto

    # ------------------------------------------------------------------
    # CARGA DEL SERVIDOR
    # ------------------------------------------------------------------
    def _al_cambiar_modo_router(self):
        if self.var_modo_router.get():
            self.btn_iniciar.config(text="🚀🔀 Iniciar Router (varios modelos)")
            self.fila_modelo_router.pack(anchor="w", pady=(0, 8), before=self.panel_chat_borde)
            self.fila_opciones_router.pack(anchor="w", pady=(0, 8), after=self.chk_modo_router)
        else:
            self.btn_iniciar.config(text="🚀 Cargar modelo (1 clic)")
            self.fila_modelo_router.pack_forget()
            self.fila_opciones_router.pack_forget()

    def iniciar_todo_hilo(self):
        if not self.var_modo_router.get() and not self.modelo_seleccionado.get():
            messagebox.showwarning("Advertencia", "Selecciona un modelo.")
            return
        if self.var_modo_router.get() and not any(os.path.isdir(c) for c in self.carpetas_modelos):
            messagebox.showwarning("Advertencia", "Agrega al menos una carpeta con modelos .gguf.")
            return
        ruta_llama = self.var_ruta_llama_server.get()
        if not ruta_llama or not os.path.isfile(ruta_llama):
            messagebox.showerror(
                "Error",
                f"No se encontró llama-server.exe en:\n{ruta_llama}\n\n"
                "Ve a la página 'Modelos' y usa '📂 Cambiar ruta de llama-server.exe' para indicar dónde está.",
            )
            return
        if self.var_tipo_spec.get() == "Con modelo draft" and not self.var_modelo_draft.get().strip():
            messagebox.showwarning("Advertencia", "Elige un modelo draft (.gguf) en 'TurboQuant', o cambia el tipo a N-gram / Ninguna.")
            return

        self.btn_iniciar.config(state=tk.DISABLED, bg=self.tema["borde"], fg=self.tema["texto_dim"])
        self.btn_agentes.config(state=tk.DISABLED)
        self.endpoint_actual.set("")
        self.servidor_listo = False
        self._animar_estado("Preparando servidor")
        hilo = threading.Thread(target=self._lanzar_servidor, daemon=True)
        hilo.start()

    def _lanzar_servidor(self):
        modo_router = self.var_modo_router.get()
        ruta_modelo = self.modelo_seleccionado.get()
        modelo = os.path.basename(ruta_modelo) if ruta_modelo else ""
        host = self.var_host.get().strip() or "127.0.0.1"
        puerto = self._puerto_libre(host, self.var_port.get().strip() or "8080")

        turboquant_activo = self.var_turboquant.get()
        comando = [self.var_ruta_llama_server.get()]
        if modo_router:
            carpeta_router = os.path.dirname(ruta_modelo) if ruta_modelo else None
            if not carpeta_router or not os.path.isdir(carpeta_router):
                carpeta_router = next((c for c in self.carpetas_modelos if os.path.isdir(c)), CARPETA_RECURSOS)
            comando += ["--models-dir", carpeta_router]
            models_max = self.var_models_max.get().strip()
            if models_max:
                comando += ["--models-max", models_max]
            if not self.var_models_autoload.get():
                comando += ["--no-models-autoload"]
        else:
            comando += ["-m", ruta_modelo]
        auto_fit = self.var_auto_fit.get()
        comando += [
            "-ngl", self.var_ngl.get(),
            "-fa", "on" if turboquant_activo else "auto",
            "--cache-type-k", self.var_kv_k.get(),
            "--cache-type-v", self.var_kv_v.get(),
            # Sin esto, llama.cpp reparte "-c" en 4 slots por defecto: cada
            # conversacion real (Cline, etc.) solo veria 1/4 del contexto
            # elegido arriba, y al llenarse hace "context shift" a mitad de
            # la respuesta -> el modelo pierde el hilo y repite texto en bucle.
            "-np", "1",
            # Ventana de la penalizacion de repeticion (la penalizacion en si
            # se agrega mas abajo desde el panel "Muestreo y anti-bucles": el
            # servidor trae repeat_penalty=1 = desactivada, y Cline no la manda).
            "--repeat-last-n", "256",
            "--host", host,
            "--port", str(puerto),
        ]
        if auto_fit:
            # No se manda "-c": se deja sin fijar para que --fit (activado por
            # defecto en el motor) calcule el contexto maximo que entra en la
            # VRAM libre en ese momento.
            comando += ["--fit", "on"]
            margen = self.var_fit_margen.get().strip()
            if margen:
                comando += ["--fit-target", margen]
        else:
            comando += ["-c", self.var_contexto.get()]

        # Muestreo y anti-bucles (solo se manda lo que tenga valor).
        for bandera, variable in [
            ("--temp", self.var_temp), ("--top-p", self.var_top_p), ("--top-k", self.var_top_k),
            ("--min-p", self.var_min_p), ("--repeat-penalty", self.var_repeat_penalty),
            ("--presence-penalty", self.var_presence_penalty), ("--dry-multiplier", self.var_dry),
            ("--reasoning-budget", self.var_reasoning_budget),
        ]:
            valor = variable.get().strip()
            if valor:
                comando += [bandera, valor]

        # Extender contexto con YaRN (RoPE).
        modo_rope = self.var_rope_modo.get()
        if modo_rope.startswith("YaRN"):
            factor = "4" if "4" in modo_rope else "2"
            comando += ["--rope-scaling", "yarn", "--rope-scale", factor]
            yarn_orig = self.var_yarn_orig.get().strip()
            if yarn_orig:
                comando += ["--yarn-orig-ctx", yarn_orig]

        # Dispositivos de calculo / reparto entre GPU.
        dispositivos = self.var_dispositivos.get().strip()
        if dispositivos:
            comando += ["--device", dispositivos]
        reparto = self.var_tensor_split.get().strip()
        if reparto:
            comando += ["--tensor-split", reparto]
        modo_reparto = self.var_split_mode.get().strip()
        if modo_reparto:
            comando += ["--split-mode", modo_reparto]
        gpu_principal = self.var_main_gpu.get().strip()
        if gpu_principal:
            comando += ["--main-gpu", gpu_principal]

        hilos = self.var_threads.get().strip()
        if hilos:
            comando += ["-t", hilos]
        hilos_batch = self.var_threads_batch.get().strip()
        if hilos_batch:
            comando += ["-tb", hilos_batch]
        batch_size = self.var_batch_size.get().strip()
        if batch_size:
            comando += ["-b", batch_size]
        ubatch_size = self.var_ubatch_size.get().strip()
        if ubatch_size:
            comando += ["-ub", ubatch_size]
        modo_carga = self.var_load_mode.get().strip()
        if modo_carga and modo_carga != "auto":
            comando += ["--load-mode", modo_carga]
        lora_path = self.var_lora.get().strip()
        if lora_path:
            escala = self.var_lora_scale.get().strip()
            if escala:
                comando += ["--lora-scaled", f"{lora_path}:{escala}"]
            else:
                comando += ["--lora", lora_path]
        numa = self.var_numa.get().strip()
        if numa and numa != "ninguno":
            comando += ["--numa", numa]
        tipo_spec = self.var_tipo_spec.get()
        if tipo_spec == "N-gram simple (sin modelo extra)":
            comando += ["--spec-type", "ngram-simple"]
        elif tipo_spec == "N-gram caché (sin modelo extra)":
            comando += ["--spec-type", "ngram-cache"]
        elif tipo_spec == "MTP (sin modelo extra)":
            comando += ["--spec-type", "draft-mtp"]
        elif tipo_spec == "Con modelo draft":
            modelo_draft = self.var_modelo_draft.get().strip()
            if modelo_draft:
                comando += ["--spec-type", "draft-simple", "--model-draft", modelo_draft]
        if tipo_spec != "Ninguna":
            spec_n_max = self.var_spec_n_max.get().strip()
            if spec_n_max:
                comando += ["--spec-draft-n-max", spec_n_max]
            spec_p_min = self.var_spec_p_min.get().strip()
            if spec_p_min:
                comando += ["--spec-draft-p-min", spec_p_min]
            spec_draft_ngl = self.var_spec_draft_ngl.get().strip()
            if spec_draft_ngl:
                comando += ["--spec-draft-ngl", spec_draft_ngl]
            spec_draft_kv_k = self.var_spec_draft_kv_k.get().strip()
            if spec_draft_kv_k:
                comando += ["--spec-draft-type-k", spec_draft_kv_k]
            spec_draft_kv_v = self.var_spec_draft_kv_v.get().strip()
            if spec_draft_kv_v:
                comando += ["--spec-draft-type-v", spec_draft_kv_v]
        moe_modo = self.var_moe_modo.get()
        if moe_modo == "Todos los expertos en CPU (-cmoe)":
            comando += ["--cpu-moe"]
        elif moe_modo == "Primeras N capas en CPU (-ncmoe)":
            n_capas = self.var_moe_n_capas.get().strip()
            if n_capas:
                comando += ["--n-cpu-moe", n_capas]
        mmproj = self.var_mmproj.get().strip()
        if mmproj:
            comando += ["--mmproj", mmproj]
        clave_api = self.var_api_key.get().strip()
        if clave_api:
            comando += ["--api-key", clave_api]
        cors_origins = self.var_cors_origins.get().strip()
        if cors_origins and cors_origins != "*":
            comando += ["--cors-origins", cors_origins]
        timeout_srv = self.var_timeout.get().strip()
        if timeout_srv:
            comando += ["--timeout", timeout_srv]
        if self.var_busqueda_web_tool.get():
            try:
                ruta_config_mcp = escribir_config_mcp_web_search()
                comando += ["--mcp-servers-config", ruta_config_mcp]
            except Exception:
                pass

        try:
            entorno = os.environ.copy()
            entorno["no_proxy"] = "localhost,127.0.0.1"
            self.proceso_servidor = subprocess.Popen(
                comando, cwd=CARPETA_RECURSOS, creationflags=subprocess.CREATE_NEW_CONSOLE, env=entorno,
            )
        except Exception as e:
            mensaje_error = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo al iniciar llama-server.exe:\n{mensaje_error}"))
            self.root.after(0, self.restaurar_boton)
            return

        texto_carga = "Iniciando servidor Router" if modo_router else f"Cargando {modelo}"
        self.root.after(0, lambda: self._animar_estado(texto_carga))
        self._esperar_salud(host, puerto)

    def _esperar_salud(self, host, puerto, timeout=600):
        url = f"http://{host}:{puerto}/health"
        inicio = time.time()
        while time.time() - inicio < timeout:
            if self.proceso_servidor is not None and self.proceso_servidor.poll() is not None:
                self.root.after(0, lambda: self._fallo_carga("El proceso de llama-server.exe terminó antes de cargar."))
                return
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        self.root.after(0, lambda: self._servidor_listo(host, puerto))
                        return
            except Exception:
                pass
            time.sleep(1)
        self.root.after(0, lambda: self._fallo_carga("Tiempo de espera agotado esperando a que el modelo cargue."))

    def _servidor_listo(self, host, puerto):
        self._detener_animacion()
        self.servidor_listo = True
        endpoint = f"http://{host}:{puerto}/v1"
        self.endpoint_actual.set(endpoint)
        if self.var_modo_router.get():
            self._set_estado(f"✅ Router activo. Enlaza tu agente a:\n{endpoint}\n(el modelo se elige por nombre en cada request)", "ok")
            threading.Thread(target=self._refrescar_modelos_router, args=(endpoint,), daemon=True).start()
        else:
            self._set_estado(f"✅ Modelo conectado. Enlaza tu agente a:\n{endpoint}", "ok")
        self.btn_iniciar.config(state=tk.NORMAL, bg=self.tema["acento"], fg=self.tema["acento_texto"])
        self.btn_detener.config(state=tk.NORMAL)
        self.btn_agentes.config(state=tk.NORMAL)

    def _refrescar_modelos_router(self, endpoint):
        try:
            with urllib.request.urlopen(f"{endpoint}/models", timeout=10) as resp:
                cuerpo = json.loads(resp.read().decode("utf-8"))
            ids = [m.get("id") for m in cuerpo.get("data", []) if m.get("id")]
        except Exception:
            ids = []
        self.root.after(0, lambda: self._aplicar_modelos_router(ids))

    def _aplicar_modelos_router(self, ids):
        self.modelos_router_disponibles = ids
        if hasattr(self, "combo_modelo_router"):
            self.combo_modelo_router.configure(values=ids)
        if ids and self.var_modelo_router_activo.get() not in ids:
            self.var_modelo_router_activo.set(ids[0])

    def _fallo_carga(self, mensaje):
        self._detener_animacion()
        messagebox.showerror("Error al cargar el modelo", mensaje)
        self._set_estado(f"Estado: {mensaje}", "peligro")
        self.restaurar_boton()
        if self.proceso_servidor:
            try:
                self.proceso_servidor.terminate()
            except Exception:
                pass
            self.proceso_servidor = None

    def detener_servidor(self):
        if self.proceso_servidor:
            try:
                self.proceso_servidor.terminate()
                self.proceso_servidor.wait(timeout=10)
            except Exception:
                pass
            self.proceso_servidor = None
        self.servidor_listo = False
        self.endpoint_actual.set("")
        self.btn_detener.config(state=tk.DISABLED)
        self.btn_agentes.config(state=tk.DISABLED)
        self._set_estado("Estado: Servidor detenido.")
        self.restaurar_boton()

    def copiar_endpoint(self):
        endpoint = self.endpoint_actual.get()
        if not endpoint:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(endpoint)
        self._set_estado(f"📋 Copiado al portapapeles: {endpoint}", "ok")

    def restaurar_boton(self):
        self.btn_iniciar.config(state=tk.NORMAL, bg=self.tema["acento"], fg=self.tema["acento_texto"])

    def _actualizar_color_estado(self, tipo=None):
        color = {"ok": self.tema["ok"], "peligro": self.tema["peligro"]}.get(tipo, self.tema["texto_dim"])
        try:
            self.lbl_estado.config(fg=color, bg=self.tema["bg"])
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # ANIMACION DE ESTADO
    # ------------------------------------------------------------------
    def _animar_estado(self, base_texto):
        self._anim_base = base_texto
        self._anim_dots = 0
        self._tick_animacion()

    def _tick_animacion(self):
        if self.servidor_listo:
            return
        self._anim_dots = (self._anim_dots + 1) % 4
        self._set_estado(f"⏳ {self._anim_base}{'.' * self._anim_dots}")
        self._anim_job = self.root.after(500, self._tick_animacion)

    def _detener_animacion(self):
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None

    # ------------------------------------------------------------------
    # EJECUCION DE AGENTES (CREW)
    # ------------------------------------------------------------------
    def ejecutar_agentes_hilo(self):
        if not self.servidor_listo:
            messagebox.showwarning("Advertencia", "Primero carga un modelo y espera a que quede conectado.")
            return
        self.btn_agentes.config(state=tk.DISABLED)
        hilo = threading.Thread(target=self._ejecutar_agentes, daemon=True)
        hilo.start()

    def _ejecutar_agentes(self):
        modelo = self.var_modelo_router_activo.get() if self.var_modo_router.get() else os.path.basename(self.modelo_seleccionado.get())
        endpoint = self.endpoint_actual.get()
        self.root.after(0, lambda: self._set_estado("🤖 Agentes trabajando...", "ok"))

        try:
            clave_api = self.var_api_key.get().strip() or "local-placeholder"
            llm_local = ChatOpenAI(
                model=modelo, openai_api_key=clave_api, openai_api_base=endpoint, temperature=0.2,
            )

            desarrollador = Agent(
                role=self.var_rol_dev.get(), goal=self.var_objetivo_dev.get(),
                backstory="Experto programador.", verbose=True, llm=llm_local,
            )
            revisor_qa = Agent(
                role=self.var_rol_qa.get(), goal=self.var_objetivo_qa.get(),
                backstory="Auditor meticuloso.", verbose=True, llm=llm_local,
            )
            tarea_desarrollo = Task(description=self.var_tarea_dev.get(), expected_output="Resultado del desarrollo.", agent=desarrollador)
            tarea_revision = Task(description=self.var_tarea_qa.get(), expected_output="Reporte en Markdown.", agent=revisor_qa)
            equipo = Crew(agents=[desarrollador, revisor_qa], tasks=[tarea_desarrollo, tarea_revision], process=Process.sequential, verbose=True)

            resultado = equipo.kickoff()

            with open(os.path.join(CARPETA_RECURSOS, "resultado_agentes.md"), "w", encoding="utf-8") as f:
                f.write(str(resultado))

            self.root.after(0, lambda: messagebox.showinfo("Éxito", "¡Guardado en 'resultado_agentes.md'!"))
            self.root.after(0, lambda: self._set_estado("✅ Agentes completados con éxito.", "ok"))
        except Exception as e:
            mensaje = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error en ejecución", mensaje))
            self.root.after(0, lambda: self._set_estado("Estado: Error en agentes.", "peligro"))
        finally:
            self.root.after(0, lambda: self.btn_agentes.config(state=tk.NORMAL))

    # ------------------------------------------------------------------
    def al_cerrar(self):
        if self._pulso_job:
            self.root.after_cancel(self._pulso_job)
        if self.proceso_tunel:
            try:
                self.proceso_tunel.terminate()
            except Exception:
                pass
        if self.proceso_servidor:
            try:
                self.proceso_servidor.terminate()
                self.proceso_servidor.wait(timeout=10)
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AppAgentesia(root)
    root.mainloop()
