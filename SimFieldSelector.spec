# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("roster.json", "."),
        ("tracks.json", "."),
    ],
    hiddenimports=["irsdk", "yaml"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SimFieldSelector",
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
    version="packaging/version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SimFieldSelector",
)
