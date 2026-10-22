// ============================================================
// lib.rs —— 应用的总调度台
// 职责：把各个模块（数据库、命令、后端进程）组装起来，告诉 Tauri：
//       1. 启动时要做什么（setup：初始化数据库 + 拉起 Python 后端）
//       2. 哪些命令允许前端调用（invoke_handler）
//       3. 退出时清理什么（run：回收后端子进程）
// 类比：公司开业典礼。setup 是"布置办公室"（打开档案柜、开灯），
//       invoke_handler 是"给前台登记哪些窗口提供服务"（注册柜员）。
// ============================================================
mod backend;
mod commands;
mod lab;

use tauri::Manager;
use tauri_plugin_opener::OpenerExt;

/// 是否「启动器模式」——拉起后端 → 打开浏览器 → 壳自行退出。
///
/// 为什么默认开：壳在此模式下只剩下「启动后端」这一件事的价值，
/// 界面全部由浏览器承载，从而省掉 WebView2 那 150~300MB 常驻内存。
///
/// 三种取值（环境变量 `CHEMLAB_MODE`）：
/// * `browser` —— 强制启动器模式
/// * `window`  —— 强制完整窗口（要子 webview / 原生通知时用）
/// * 未设置    —— **debug 构建默认 window**（否则 `pnpm tauri dev` 一启动就退出，
///               没法开发调试），**release 构建默认 browser**
fn launcher_mode() -> bool {
    match std::env::var("CHEMLAB_MODE").ok().as_deref() {
        Some("browser") => true,
        Some("window") => false,
        _ => !cfg!(debug_assertions),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 插件链：opener 是启动器模式的核心（拉起后端后用它打开浏览器）。
    // fs / dialog / notification 三个已逐步脱离前端依赖：
    // notification 已摘除（通知走浏览器 Notification API）；
    // fs / dialog 目前只剩「实验记录面板」那段休眠代码在用，
    // 保留是为将来恢复该面板留余地。
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        // 文件系统插件（导出备份/读取用）
        // 文件对话框插件（导出备份时选路径用）
        // setup：应用启动后、窗口显示前，执行一次初始化
        .setup(|app| {
            // 注：这里原来会初始化一个 SQLite（heji_toolbox.db）供实验记录
            // CRUD 命令使用。2026-10-27 开源清理时随死代码一起删除 ——
            // 实验记录已由合迹 ChemELN（Python 后端 + 自己的 SQLite）接管。

            // --- 拉起 Python 后端（合记 ChemELN 的 FastAPI 服务）---
            // 主壳统一管后端的生命周期：开应用时自动就绪，退应用时回收进程，
            // 不再需要用户自己点桌面图标另开一个服务。
            let bdir = backend::backend_dir(app.handle());
            let ldir = app.path().app_data_dir()?.join("logs");
            // 打包版的 Python sidecar：resources/backend/ChemLabBackend.exe
            // （开发模式下不存在，会自动回退到 backend/venv 的解释器）
            let resource_dir = app.path().resource_dir().ok();
            let sidecar = backend::sidecar_path(resource_dir.as_deref());
            if let Some(sc) = sidecar.as_ref() {
                println!("[ChemLab] 使用打包后端: {}", sc.display());
            }
            let be = backend::Backend::new();
            let st = be.start(&bdir, &ldir, backend::default_port(), sidecar.as_deref());
            println!(
                "[ChemLab] backend: running={} url={} pid={:?} reused={} err={:?}",
                st.running, st.base_url, st.pid, st.reused, st.error
            );
            // 把后端启动过程写进 startup.log。
            //
            // 为什么需要：打包版是 GUI 子系统（没有控制台），上面的 println 根本
            // 看不到。而 start() 的失败分支只把原因写进内存里的 status.error，
            // 一旦前端窗口没起来，这个错误就彻底不可见 —— 表现成「应用开着，
            // 但后端就是不启动」，排查时毫无线索。
            // 有了这个文件，这类静默失败一眼可查。
            backend::write_startup_log(
                &ldir,
                &[
                    ("exe", std::env::current_exe().map(|p| p.display().to_string()).unwrap_or_default()),
                    ("resource_dir", resource_dir.as_ref().map(|p| p.display().to_string()).unwrap_or_else(|| "<Err>".into())),
                    ("backend_dir", bdir.display().to_string()),
                    ("sidecar", sidecar.as_ref().map(|p| p.display().to_string()).unwrap_or_else(|| "<未找到>".into())),
                    ("running", st.running.to_string()),
                    ("base_url", st.base_url.clone()),
                    ("pid", format!("{:?}", st.pid)),
                    ("reused", st.reused.to_string()),
                    ("error", st.error.clone().unwrap_or_default()),
                ],
            );
            app.manage(be);

            // --- 实验记录页的原生子 webview 状态（P5）---
            // 子 webview 按需创建（进入「实验记录」时），这里只放状态
            app.manage(lab::LabEmbed::new());

            // --- 启动器模式：拉起后端后打开浏览器，壳自己退出 ---
            //
            // 只在「后端确实起来了」时才交棒：后端起不来还退掉壳的话，
            // 用户只会看到一个 404 的浏览器标签页，毫无线索。
            // 后端起不来 → 留在窗口模式，让用户在「设置 → 后端服务」看到错误。
            let launcher = launcher_mode();
            let mut handed_off = false;
            if launcher && st.running {
                let url = format!("{}/toolbox/", st.base_url.trim_end_matches('/'));
                match app.opener().open_url(&url, None::<&str>) {
                    Ok(()) => {
                        // 关键顺序：先交棒（放弃子进程所有权），再退出。
                        // 反过来的话，退出钩子会把后端当自己的子进程杀掉，
                        // 浏览器刚打开就连接失败。
                        let pid = app.state::<backend::Backend>().detach();
                        println!("[ChemLab] 启动器模式：已打开 {url}，交棒后端 pid={pid:?}");
                        backend::write_startup_log(
                            &ldir,
                            &[
                                ("mode", "browser（启动器）".to_string()),
                                ("opened_url", url.clone()),
                                ("detached_pid", format!("{pid:?}")),
                                ("note", "壳即将退出，后端继续独立运行，供浏览器使用".to_string()),
                            ],
                        );
                        handed_off = true;
                    }
                    Err(e) => {
                        // 打不开浏览器（没有默认浏览器 / 被策略禁用）→ 退回窗口模式
                        println!("[ChemLab] 打开浏览器失败，退回窗口模式: {e}");
                        backend::write_startup_log(
                            &ldir,
                            &[
                                ("mode", "browser（启动器）→ 打开失败，退回窗口".to_string()),
                                ("opened_url", url.clone()),
                                ("error", e.to_string()),
                            ],
                        );
                    }
                }
            }

            if handed_off {
                // 稍等片刻再退出：给 opener 一点时间去拉起浏览器进程，
                // 也避免在 setup 里直接 exit 引发的时序问题。
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(600));
                    handle.exit(0);
                });
            }
            Ok(())
        })
        // 注册允许前端调用的命令（新命令都要来这里"登记"）
        .invoke_handler(tauri::generate_handler![
            commands::backend_status,
            commands::backend_restart,
            lab::lab_open,
            lab::lab_close,
            lab::lab_place,
            lab::lab_nav,
            lab::lab_poll,
            commands::report_startup_info,
        ])
        // 先 build 出 App，再交给 run 回调处理生命周期事件
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        // 退出钩子：回收后端子进程，避免留下占着端口的孤儿进程
        .run(|app_handle: &tauri::AppHandle, event: tauri::RunEvent| {
            if let tauri::RunEvent::Exit = event {
                app_handle.state::<backend::Backend>().stop();
            }
        });
}

