; STTS Installer - NSIS Script
; Creates a Windows installer for STTS (Speech to Text to Speech)

Unicode true
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

; App info
!define APPNAME "STTS"
!define APPFULLNAME "STTS - Speech to Text to Speech"
!define VERSION "1.0.0"
!define PUBLISHER "STTS"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

; Build paths - relative to this .nsi file
!define LITE_BUILD "..\python\dist\STTS-Lite"
!define INSTALL_FEATURES "install-features.bat"
!define ICON "..\assets\stts-icon.ico"

; Version metadata — proper version info reduces AV false positives on the installer exe
VIProductVersion "${VERSION}.0"
VIFileVersion "${VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "${APPFULLNAME}"
VIAddVersionKey /LANG=1033 "CompanyName" "${PUBLISHER}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright (c) 2024-2026 ${PUBLISHER}"
VIAddVersionKey /LANG=1033 "FileDescription" "${APPFULLNAME} Installer"
VIAddVersionKey /LANG=1033 "FileVersion" "${VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductVersion" "${VERSION}.0"
VIAddVersionKey /LANG=1033 "OriginalFilename" "STTS-Setup.exe"

; Output
Name "${APPFULLNAME}"
OutFile "..\STTS-Setup.exe"
InstallDir "$LOCALAPPDATA\${APPNAME}"
InstallDirRegKey HKCU "${UNINSTKEY}" "InstallLocation"
RequestExecutionLevel user

; UI
!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_ABORTWARNING

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Finish page - offer to launch
!define MUI_FINISHPAGE_RUN "$INSTDIR\STTS.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch STTS"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Create Desktop Shortcut"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateDesktopShortcut
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

Function CreateDesktopShortcut
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\STTS.exe" "" "$INSTDIR\STTS.exe" 0
FunctionEnd

Section "Install"
    SetOutPath $INSTDIR

    ; Copy the Lite PyInstaller build (exe + _internal/)
    File "${LITE_BUILD}\STTS.exe"
    File /r "${LITE_BUILD}\_internal"

    ; Copy install-features script
    File "${INSTALL_FEATURES}"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Start menu shortcuts
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\STTS.exe"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Install Features.lnk" "$INSTDIR\install-features.bat" "" "" "" SW_SHOWNORMAL "" "Install extra features (Whisper, Translation, etc.)"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPFULLNAME}"
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$\"$INSTDIR\STTS.exe$\""
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "${PUBLISHER}"
    WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$\"$INSTDIR$\""
    WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1

    ; Calculate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
    ; Kill running processes (STTS and VOICEVOX engine)
    nsExec::ExecToLog 'taskkill /IM STTS.exe /F'
    nsExec::ExecToLog 'taskkill /IM run.exe /F'

    ; Remove known files
    Delete "$INSTDIR\STTS.exe"
    Delete "$INSTDIR\install-features.bat"
    Delete "$INSTDIR\uninstall.exe"
    Delete "$INSTDIR\crash.log"

    ; Remove all subdirectories (includes _internal, dist, venv, python, __pycache__, etc.)
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\dist"
    RMDir /r "$INSTDIR\venv"
    RMDir /r "$INSTDIR\python"

    ; Remove install directory and any remaining files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Install Features.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"

    ; Remove user data (models, VOICEVOX, cache, logs) in %APPDATA%\STTS
    ; BUT preserve settings-backup.json so device selections survive reinstall
    ; Remove known subdirectories individually instead of wiping the whole folder
    RMDir /r "$APPDATA\STTS\logs"
    RMDir /r "$APPDATA\STTS\models"
    RMDir /r "$APPDATA\STTS\cache"
    RMDir /r "$APPDATA\STTS\voicevox"
    ; Delete individual files except settings-backup.json
    Delete "$APPDATA\STTS\*.log"
    ; Try to remove the folder — will only succeed if empty (settings-backup.json keeps it)
    RMDir "$APPDATA\STTS"

    ; Remove registry
    DeleteRegKey HKCU "${UNINSTKEY}"
SectionEnd
