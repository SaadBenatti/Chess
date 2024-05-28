# ChessMain.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ChessMain.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('board.png', '.'),
        ('b_pawn.png', '.'),
        ('b_knight.png', '.'),
        ('b_bishop.png', '.'),
        ('b_rook.png', '.'),
        ('b_queen.png', '.'),
        ('b_king.png', '.'),
        ('w_pawn.png', '.'),
        ('w_knight.png', '.'),
        ('w_bishop.png', '.'),
        ('w_rook.png', '.'),
        ('w_queen.png', '.'),
        ('w_king.png', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChessMain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want to see console output
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChessMain',
)
