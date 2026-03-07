# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
#
# For language/codepage info see:
# https://docs.microsoft.com/en-us/windows/win32/menurc/versioninfo-resource
#
# This file is used by PyInstaller to embed version metadata into the exe.
# Having proper version info reduces antivirus false positives.

VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,          # VOS_NT_WINDOWS32
        fileType=0x1,        # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    '040904B0',   # 0409 = US English, 04B0 = Unicode
                    [
                        StringStruct('CompanyName', 'STTS'),
                        StringStruct('FileDescription', 'STTS - Speech to Text to Speech'),
                        StringStruct('FileVersion', '1.0.0.0'),
                        StringStruct('InternalName', 'STTS'),
                        StringStruct('LegalCopyright', 'Copyright (c) 2024-2026 STTS'),
                        StringStruct('OriginalFilename', 'STTS.exe'),
                        StringStruct('ProductName', 'STTS - Speech to Text to Speech'),
                        StringStruct('ProductVersion', '1.0.0.0'),
                    ],
                ),
            ],
        ),
        VarFileInfo([VarStruct('Translation', [0x0409, 0x04B0])]),
    ],
)
