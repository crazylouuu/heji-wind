// ============================================================
// commands.rs —— 前端能调用的"服务窗口"
// 每个 #[tauri::command] 函数 = 一个服务窗口：
// 前端点按钮 → invoke("命令名", 参数) → 这里执行 → 结果返回前端
// 类比：银行柜台。前端是客户，invoke 是叫号，
//       这些函数是窗口里的柜员 —— 你说要办什么业务（命令名），
//       柜员办完给你回执（返回值）。
//
// 【2026-10-27 开源清理】这里原来还有 13 个命令，全部删除了：
//   - 实验记录 CRUD（create/update/delete/list_experiments、db_health）
//   - PDF 导出（export_pdf）
//   - SOP 文件读取（list_sop_files / read_sop_file / get_sops_root /
//     read_sop_image）
//   - 键值设置（get_setting / set_setting）
//   - 脚手架残留（greet）
// 原因：实验记录已由合迹 ChemELN 取代，前端全部改走 HTTP API，
// 这些 Tauri 命令一个调用点都没有了。连带删掉 db.rs（rusqlite）、
// models.rs 与 printpdf / chrono 依赖。
//
// 现在只剩三件事：后端进程管理、启动自检上报。
// ============================================================
use crate::backend::{Backend, BackendStatus};
// Manager trait 提供 app.path() 路径查询方法（backend_restart 要用）
use tauri::Manager;
use tauri::State;

// ========== 后端进程管理（合记 ChemELN 的 FastAPI 服务） ==========

/// 查后端状态：地址、端口、PID、令牌、是否就绪。
/// 前端拿它来决定「能不能调后端 API」以及请求头该带什么令牌。
#[tauri::command]
pub fn backend_status(backend: State<Backend>) -> BackendStatus {
    backend.status()
}

/// 重启后端：先停掉本进程拉起的子进程，再按同一套流程重新拉起。
/// 改了 Python 代码后用它热重启，不用整个退出应用。
#[tauri::command]
pub fn backend_restart(
    backend: State<Backend>,
    app: tauri::AppHandle,
) -> Result<BackendStatus, String> {
    let bdir = crate::backend::backend_dir(&app);
    let ldir = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join("logs");
    let sidecar = crate::backend::sidecar_path(app.path().resource_dir().ok().as_deref());
    backend.stop();
    Ok(backend.start(
        &bdir,
        &ldir,
        crate::backend::default_port(),
        sidecar.as_deref(),
    ))
}

// ========== 启动自检 ==========

/// 前端启动后主动上报「当前 URL + IPC 是否可用」。
///
/// 用途：排查「主 webview 停在 about:blank」这类问题时，
/// Rust 侧读 webview.url() 不可靠，由前端自己报最准。
#[tauri::command]
pub fn report_startup_info(url: String, hash: String, has_tauri: bool) {
    println!(
        "[ChemLab] 前端上报: url={url} hash={hash} ipc={has_tauri}"
    );
}
