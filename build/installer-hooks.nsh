; ============================================================
; installer-hooks.nsh —— NSIS 安装钩子
;
; 为什么需要：NSIS 升级安装只会「覆盖」同名文件，不会删除旧版本里
; 存在、新版本里已不存在的文件。实测过：去掉 Ketcher（31MB）后重新打包，
; 安装包确实变成 47MB，但装到旧版本上，磁盘里那 31MB 的 ketcher 目录
; 仍然在 —— 用户看到的占用没变。
;
; 这里在写入新文件之前，先删掉整个 resources\backend。
; 这个目录是纯程序资源（Python 运行时 + 前端静态文件），不含用户数据：
; 用户数据在 %APPDATA%\<应用名>\ 下，与本目录无关，不会被动到。
; ============================================================

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "清理旧版本的程序资源..."
  RMDir /r "$INSTDIR\resources\backend"
  ; 工具箱前端也一起清（同样属于程序资源）
  RMDir /r "$INSTDIR\resources\frontend-toolbox"
!macroend
