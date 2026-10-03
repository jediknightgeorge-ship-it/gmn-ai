# GMN AI — a point-and-click control panel for local LLMs (llama.cpp)

**Created by G.M.N TechLab.** GMN AI is a Windows desktop app that loads and runs GGUF language models with
[llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server.exe`) **without typing a single command**.
Pick a model, press one button, and any OpenAI-compatible client (VS Code, Roo Code, Continue, Cline, OpenCode…)
can talk to it. Everything runs on your own PC; nothing leaves it unless you turn on a feature that needs the internet.

> The app's interface is in **Spanish**. This README explains every screen in English, with the Spanish
> name of each page in parentheses so you can find it.

![Models page (day)](docs/modelos_dia.png)
![Models page (night)](docs/modelos_noche.png)

## Download

Get **`GMN_AI_v1.1.0.zip`** from the [Releases page](https://github.com/jediknightgeorge-ship-it/gmn-ai/releases/latest),
unzip it anywhere and run `interfaz_agentes.exe`. No installer, no Python needed.

You also need **your own `llama-server.exe`** (the app does not bundle llama.cpp). Download the build that matches
your hardware from <https://github.com/ggml-org/llama.cpp/releases> — *CUDA* for NVIDIA GPUs, *Vulkan* for AMD/Intel
GPUs, or the *CPU* build if you have no GPU — and point the app to it once (TurboQuant page → "Ubicación de llama-server.exe").

**Requirements:** Windows 10/11 64-bit · GGUF models (the app can download them from Hugging Face) · a GPU is recommended but not required.

> Windows SmartScreen / antivirus may warn about the `.exe` because it is not code-signed. That is a false positive
> for a freshly built unsigned app; the full source code is in this repository.

## Quick start

1. **Models** page (*Modelos*): add the folder(s) where your `.gguf` files are (➕ *Agregar*). You can add several folders.
2. **TurboQuant** page: select `llama-server.exe` once, then click one of the **profile buttons** at the top (see below).
3. Back on **Models**, select a model and press **🚀 Cargar modelo (1 clic)** ("Load model, 1 click").
4. Try it in **Chat / Playground**, or copy the endpoint from the **Connection** page (*Conexión*) into your coding tool.

## One-click profiles (TurboQuant page → *Perfiles de configuración*)

Built-in profiles only change performance/memory options (not your model, port, API key or sampling).
You can also save your own profiles with 💾 *Guardar*.

| Profile | What it does | Use it when |
|---|---|---|
| ⚡ **Fast on my GPU** | Whole model on the GPU, 8k context, quantized KV cache | The model fits in your VRAM |
| 📚 **Big context, fast** | The engine computes the largest context that fits in your *free* VRAM, leaving a safety margin (default 0.5 GB) | You want a long context without running out of VRAM |
| 🐘 **Big model (only what fits on the GPU)** | Puts as many layers as fit on the GPU and leaves the rest in RAM, automatic context | The model is bigger than your VRAM (speed is then limited by your RAM/CPU) |
| 🧩 **Big MoE model (experts in RAM)** | Shared layers on the GPU, the "experts" stay in RAM so only what is needed is used | Mixture-of-Experts models (Nemotron 3 Nano 30B, Qwen 35B-A3B…) |
| 🛡️ **Safe (don't saturate VRAM)** | 4k context, 1 GB VRAM margin, small batches | You use the PC for other things at the same time |

## Everything the app does

**Loading & memory**
- **Visual model picker** for GGUF files across multiple folders, with colour hints for what fits in 11 GB of VRAM.
- **TurboQuant (KV-cache quantization)** — shrinks the KV cache (`--cache-type-k/v`: q8_0, q4_0…) so you can fit more context in less VRAM. Flash Attention is enabled with it.
- **Context window up to 1,000,000 tokens** (editable list; type any value).
- **Auto-fit (`--fit`) with a VRAM safety margin (`--fit-target`)** — the engine picks the biggest context that fits and keeps e.g. 512 MB free, so a saturated VRAM does not freeze Windows.
- **GPU layers (`-ngl`)** with `auto` / `all` / any number, CPU threads, batch/ubatch sizes, NUMA.
- **Load mode** (`--load-mode`: auto / mmap / mlock / none).
- **MoE offload** (`--cpu-moe`, `--n-cpu-moe`) to run models much larger than your VRAM.
- **LoRA adapters** (`--lora`, `--lora-scaled`).
- **Vision models** (`--mmproj`).
- **Extend context with YaRN** (×2 / ×4) beyond the model's training context.
- **Devices & multi-GPU**: choose devices (`--device`), split proportions (`--tensor-split`), split mode (`--split-mode`: layer / row / tensor) and main GPU (`--main-gpu`); a button lists the devices llama.cpp can see (CUDA, Vulkan, CPU…).
- **Router mode** (*Modo Router*): serve several models at once from a folder, auto-loaded on demand, with a max-models limit.

**Speed**
- **Speculative decoding**: N-gram (no extra model), **MTP** (the model's own multi-token-prediction head) or a separate draft model, with fine tuning (tokens drafted per step, minimum acceptance probability).

**Quality & behaviour**
- **Sampling & anti-loop panel**: temperature, top-p / top-k / min-p, repetition & presence penalties, **DRY**, with presets *Anti-loops*, *Precise code*, *Creative*.
- **Reasoning budget** (`--reasoning-budget`): caps how many tokens a "thinking" model may spend before answering (fixes empty answers from models that think too long).

**Using the model**
- **Chat / Playground** with Markdown rendering and a **built-in web search tool** (DuckDuckGo, **no API key**): the model can search the web and answer from real results.
- **Cloud providers** (*Proveedores en la nube*): add OpenAI-compatible endpoints or Anthropic (Claude) with your own API key and chat with them from the same window.
- **Connection page**: ready-made config snippets for **Continue**, **Cline** and **OpenCode**.
- **Hugging Face downloader**: search models and download a file, always asking for confirmation first.
- **Remote tunnel** (cloudflared) to expose your server outside your network (optional; needs `cloudflared.exe`).
- **Server security**: optional API key, CORS origins and timeout.

**Monitoring & looks**
- **Live monitor**: GPU, VRAM, temperature, CPU, RAM, and detected hardware (works with NVIDIA, AMD, Intel or CPU-only).
- **Apple-style design** with rounded cards/buttons, a one-click ☀️/🌙 switch in the header, automatic colour combination for any accent colour, and WCAG-checked text contrast in both modes.

## Real numbers (measured, not marketing)

Tested with llama-server b11223 on an **RTX 2080 Ti (11 GB) + AMD FX-8320E + 28 GB DDR3**:

| Model | Setup | Generation speed |
|---|---|---|
| Qwen 3.8 27B **IQ2_XS** | all on GPU ("Fast" profile) | **≈ 19.8 tok/s** |
| Qwen 3.8 27B Q4_K_M (16 GB) | partly in RAM | ≈ 1.3 tok/s (RAM/CPU bound) |
| Same 27B Q4 with **MTP** | partly in RAM | ≈ 1.2 tok/s — MTP worked (178 of 228 drafted tokens accepted) but the CPU part is the bottleneck |

Takeaway: a model that **fits in VRAM** is dramatically faster than one that spills into slow RAM; speculative
decoding helps most when the GPU is the bottleneck. Your numbers will differ with your hardware.

## Known limitations

- The **Agents (Crew)** tab is currently broken: the installed CrewAI version no longer accepts the LangChain model
  object the app passes. The rest of the app is unaffected. A fix is planned.
- Windows only. The UI is in Spanish.
- API keys for cloud providers are stored **in plain text** in a local JSON file next to the app (they never leave your PC).
- The local server has **no password by default**; set an API key (TurboQuant page → *Seguridad del servidor*) if other devices can reach your PC.
- Features that depend on llama.cpp flags (e.g. `--fit`, `--spec-type draft-mtp`, `--split-mode tensor`) need a recent `llama-server.exe`.
- The multi-GPU `tensor` split mode and the MoE profile were not tested on real multi-GPU / MoE hardware.

## Build from source

```bash
pip install pyinstaller crewai langchain-openai psutil pillow mcp beautifulsoup4 requests
pyinstaller interfaz_agentes.spec --noconfirm     # output: dist/gmn ai/interfaz_agentes.exe
```

Run directly with `python interfaz_agentes.py`. Files: `interfaz_agentes.py` (app), `estilo_apple.py` (rounded widgets),
`interfaz_agentes.spec` (build recipe), `LEEME.txt` (Spanish readme).

## Credits

Created by **G.M.N TechLab**. Built on top of [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT).
Ideas and testing inspired by the local-AI community, including the Nichonauta channel.
