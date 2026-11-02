# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['openpyxl']
hiddenimports += collect_submodules('texflow')
hiddenimports += collect_submodules('texflow_desktop')
hiddenimports += collect_submodules('reportlab')


a = Analysis(
    ['texflow_app.py'],
    pathex=['desktop', '.'],
    binaries=[],
    datas=[('texflow/templates', 'texflow/templates'), ('texflow/static', 'texflow/static'), ('texflow/schema.sql', 'texflow'), ('samples', 'samples'), ('install/texflow.png', 'install'), ('install/texflow.ico', 'install'), ('install/texflow.icns', 'install')],
    hiddenimports=hiddenimports,
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
    name='TexFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['install/texflow.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TexFlow',
)
