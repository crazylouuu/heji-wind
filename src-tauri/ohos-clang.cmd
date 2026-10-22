@echo off
REM ============================================================
REM ohos-clang.cmd —— aarch64 OHOS 链接器包装（Windows 专用）
REM 作用：OHOS NDK 自带的 aarch64-unknown-linux-ohos-clang 是 Unix
REM        shell 脚本，Windows 无法直接执行。这里用 clang.exe 包一层，
REM        Rust 在链接 .so 时调用本脚本完成交叉链接。
REM 类比：Unix 脚本是"英文说明书"，Windows 看不懂；这个 .cmd 是
REM        "中文翻译"，告诉 clang.exe 该怎么干活。
REM ============================================================
"D:\Huawei\DevEco Studio\sdk\default\openharmony\native\llvm\bin\clang.exe" ^
 -target aarch64-linux-ohos ^
 --sysroot="D:\Huawei\DevEco Studio\sdk\default\openharmony\native\sysroot" ^
 -D__MUSL__ -fuse-ld=lld %*
