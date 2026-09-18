# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files('crewai')
datas += [('jaguar_logo.png', '.')]
datas += [('gmn_logo.png', '.')]


a = Analysis(
    ['interfaz_agentes.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Modo "onedir": el exe queda pequeno y las dependencias se dejan sueltas en
# _internal, en vez de un solo .exe comprimido con UPX (mas rapido de compilar
# y de arrancar, y evita que el antivirus escanee cada bloque comprimido).
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='interfaz_agentes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pantera_icono.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='gmn ai',
)
