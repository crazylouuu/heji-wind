// ============================================================
// lab.rs —— 实验记录页的原生子 webview 管理（P5）
//
// P4 用 iframe 嵌入合迹前端，P5 换成 Tauri 原生子 webview：
// 同一桌面窗口内多一个原生 webview 控件，渲染更实、无 iframe 边框与沙箱限制。
//
// 三个实测约束（来自 docs/三应用整合方案.md 的原型验证，本模块严格遵守）：
//
// 1. `add_child` / `WebviewBuilder` 需要 tauri 的 `unstable` feature
//    → Cargo.toml 已开启；若将来编译不过，前端自动退回 iframe（P4 已实现）
//
// 2. `add_child` 定义在 `Window` 上，不是 `WebviewWindow`
//    → 用 app.get_window("main")
//
// 3. Windows 上在同步命令里调用 `add_child` 会死锁
//    → 创建动作放到独立线程（主线程不被阻塞），前端轮询状态等待就绪
//
// 另外两点：
// - `on_page_load` 对子 webview 触发不可靠 → 不用它判断就绪，
//   改用「子页向后端上报 ready，主壳轮询后端」的方式
// - 子 webview 是远程 origin，不走 Tauri IPC → 主壳→子页用 eval 注入，
//   子页→后端用同源 fetch
//
// 显隐控制：Webview 没有 set_visible，改为「移出客户区」来隐藏
// （移到 -10000,-10000），显示时移回主 webview 内容区。
// ============================================================
use serde::Serialize;
use std::sync::{Arc, Mutex};
use tauri::AppHandle;

// ── 子 webview 相关依赖的门控 ────────────────────────────────────────────
//
// 为什么门控得这么细：
//   只要二进制里链接了 tauri::Webview，就会连带引入 WebView2 的 COM 依赖。
//   应用 exe 没问题，但 `cargo test` 生成的测试进程在初始化 COM 时会直接
//   失败（STATUS_ENTRYPOINT_NOT_FOUND / 0xc0000139）—— 这是测试宿主的限制，
//   不是业务代码的问题。
//   于是把「用到 Webview 的代码」整体放到 feature 门控之下：
//     - 应用构建（含 feature）→ 有原生子 webview 能力
//     - 测试构建（not(test)）  → 不含 COM 依赖，cargo test 正常
//   未开启 feature 时，实验记录页走 iframe 通道（前端自动降级）。

/// 子 webview 句柄类型：未启用时用 () 占位，避免链接 WebView2 COM
#[cfg(all(feature = "lab-child-webview", not(test)))]
type ChildWebview = tauri::Webview;
#[cfg(any(not(feature = "lab-child-webview"), test))]
type ChildWebview = ();

/// 子 webview 的标签（与前端约定）
#[cfg(feature = "lab-child-webview")]
const LAB_LABEL: &str = "chemlab-lab";

/// 隐藏时把子 webview 挪到的位置（客户区外）
#[cfg(all(feature = "lab-child-webview", not(test)))]
const HIDDEN_POS: f64 = -10000.0;

// ---------------------------------------------------------------- 状态

/// 暴露给前端的子 webview 状态
#[derive(Debug, Clone, Serialize, Default)]
pub struct LabStatus {
    /// 子 webview 是否已创建
    pub open: bool,
    /// 子页是否已加载就绪（子页向后端上报 ready，主壳轮询得知）
    pub ready: bool,
    /// 当前是否显示在内容区
    pub visible: bool,
    /// 子 webview 的地址
    pub url: String,
    /// 嵌入方式：child = 原生子 webview，iframe = 降级
    pub mode: String,
    /// 失败原因
    pub error: Option<String>,
}

struct Inner {
    webview: Option<ChildWebview>,
    url: String,
    ready: bool,
    visible: bool,
    /// 记录上次放置的位置与尺寸（逻辑像素）：x, y, w, h
    placed: Option<(f64, f64, f64, f64)>,
    /// 创建过程里的错误（异步线程写入）
    error: Option<String>,
}

/// 全局状态。
///
/// inner 用 Arc 包一层：创建子 webview 的动作要放到独立线程里执行
/// （Windows 上 add_child 会阻塞主线程），Arc 让这份状态能被安全地 move 进线程。
pub struct LabEmbed {
    inner: Arc<Mutex<Inner>>,
}

impl LabEmbed {
    pub fn new() -> Self {
        LabEmbed {
            inner: Arc::new(Mutex::new(Inner {
                webview: None,
                url: String::new(),
                ready: false,
                visible: false,
                placed: None,
                error: None,
            })),
        }
    }

    fn status_of(inner: &Inner, mode: &str) -> LabStatus {
        LabStatus {
            open: inner.webview.is_some(),
            ready: inner.ready,
            visible: inner.visible,
            url: inner.url.clone(),
            mode: mode.to_string(),
            error: inner.error.clone(),
        }
    }
}

impl Default for LabEmbed {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------- 子 webview 创建

/// 创建子 webview（unstable API，用 feature 门控）
///
/// 未开启 `lab-child-webview` feature 时返回错误，前端据此退回 iframe 通道。
#[cfg(all(feature = "lab-child-webview", not(test)))]
fn create_child_webview(app: &AppHandle, url: &str) -> Result<ChildWebview, String> {
    use tauri::webview::WebviewBuilder;
    use tauri::{LogicalPosition, LogicalSize, Manager, WebviewUrl};

    let window = app.get_window("main").ok_or("找不到主窗口")?;
    let parsed: tauri::Url = url.parse().map_err(|e| format!("URL 解析失败: {e}"))?;
    let builder = WebviewBuilder::new(LAB_LABEL, WebviewUrl::External(parsed));
    // 初始就放到客户区外：等前端放好位置再显示，避免闪现
    window
        .add_child(
            builder,
            LogicalPosition::new(HIDDEN_POS, HIDDEN_POS),
            LogicalSize::new(100.0, 100.0),
        )
        .map_err(|e| e.to_string())
}

/// 未开启 feature 时：明确报错，前端自动降级到 iframe
#[cfg(any(not(feature = "lab-child-webview"), test))]
fn create_child_webview(_app: &AppHandle, _url: &str) -> Result<ChildWebview, String> {
    Err(
        "当前构建未启用子 webview 通道（需 --features lab-child-webview），已降级到 iframe"
            .to_string(),
    )
}

// ---------------------------------------------------------------- 命令

/// 打开（创建）实验记录子 webview
///
/// 立即返回「创建中」；前端随后轮询 `lab_poll` 直到 ready。
/// 创建动作在独立线程执行 —— Windows 上 add_child 会阻塞主线程，
/// 放在同步命令里会死锁。
#[tauri::command]
pub fn lab_open(app: AppHandle, state: tauri::State<'_, LabEmbed>, url: String) -> LabStatus {
    let inner_arc = state.inner.clone();
    {
        let mut inner = match inner_arc.lock() {
            Ok(g) => g,
            Err(e) => {
                return LabStatus {
                    mode: "child".into(),
                    error: Some(format!("状态锁异常: {e}")),
                    ..Default::default()
                }
            }
        };
        // 已有实例：先关掉再重建（地址可能变了）
        #[cfg(all(feature = "lab-child-webview", not(test)))]
        if let Some(wv) = inner.webview.take() {
            let _ = wv.close();
        }
        #[cfg(any(not(feature = "lab-child-webview"), test))]
        {
            inner.webview = None;
        }
        inner.ready = false;
        inner.visible = false;
        inner.placed = None;
        inner.url = url.clone();
    }

    let app2 = app.clone();
    let inner_thread = inner_arc.clone();
    std::thread::spawn(move || {
        match create_child_webview(&app2, &url) {
            Ok(wv) => {
                if let Ok(mut inner) = inner_thread.lock() {
                    inner.webview = Some(wv);
                }
                eprintln!("[lab] 子 webview 已创建: {url}");
            }
            Err(e) => {
                eprintln!("[lab] 创建子 webview 失败: {e}");
                if let Ok(mut inner) = inner_thread.lock() {
                    inner.error = Some(e);
                }
            }
        }
    });

    let inner = inner_arc.lock().ok();
    match inner {
        Some(g) => LabEmbed::status_of(&g, "child"),
        None => LabStatus {
            mode: "child".into(),
            error: Some("状态锁异常".into()),
            ..Default::default()
        },
    }
}

/// 关闭子 webview
#[tauri::command]
pub fn lab_close(state: tauri::State<'_, LabEmbed>) -> LabStatus {
    let mut inner = match state.inner.lock() {
        Ok(g) => g,
        Err(e) => {
            return LabStatus {
                mode: "child".into(),
                error: Some(format!("状态锁异常: {e}")),
                ..Default::default()
            }
        }
    };
    #[cfg(all(feature = "lab-child-webview", not(test)))]
    if let Some(wv) = inner.webview.take() {
        let _ = wv.close();
    }
    #[cfg(any(not(feature = "lab-child-webview"), test))]
    {
        inner.webview = None;
    }
    inner.ready = false;
    inner.visible = false;
    inner.placed = None;
    LabEmbed::status_of(&inner, "child")
}

/// 放置子 webview：传主 webview 内容区的矩形（CSS 逻辑像素）
///
/// visible = true 时显示在内容区；false 时挪到客户区外隐藏。
#[tauri::command]
pub fn lab_place(
    state: tauri::State<'_, LabEmbed>,
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    visible: bool,
) -> LabStatus {
    let mut inner = match state.inner.lock() {
        Ok(g) => g,
        Err(e) => {
            return LabStatus {
                mode: "child".into(),
                error: Some(format!("状态锁异常: {e}")),
                ..Default::default()
            }
        }
    };

    // 位置调整要调用 Webview 的方法（会引入 WebView2 COM 依赖），
    // 因此只在启用 feature 且非测试构建时编译
    #[cfg(all(feature = "lab-child-webview", not(test)))]
    if let Some(wv) = inner.webview.as_ref() {
        use tauri::{LogicalPosition, LogicalSize};
        if visible {
            let _ = wv.set_position(LogicalPosition::new(x, y));
            let _ = wv.set_size(LogicalSize::new(w, h));
        } else {
            let _ = wv.set_position(LogicalPosition::new(HIDDEN_POS, HIDDEN_POS));
        }
    }
    inner.placed = Some((x, y, w, h));
    inner.visible = visible;
    LabEmbed::status_of(&inner, "child")
}

/// 切换子页视图（主壳 → 子 webview，走 eval 注入）
///
/// 合迹前端暴露了 `window.__chemlabNav(view)`，这里调用它。
#[tauri::command]
pub fn lab_nav(state: tauri::State<'_, LabEmbed>, view: String) -> Result<(), String> {
    let inner = state.inner.lock().map_err(|e| e.to_string())?;
    // 视图名做白名单过滤：它会被拼进 JS，必须只允许字母数字与短横线
    if !view
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(format!("非法视图名: {view}"));
    }

    #[cfg(all(feature = "lab-child-webview", not(test)))]
    {
        let wv = inner.webview.as_ref().ok_or("子 webview 尚未创建")?;
        let js = format!("window.__chemlabNav && window.__chemlabNav('{view}');");
        wv.eval(js).map_err(|e| e.to_string())
    }
    #[cfg(any(not(feature = "lab-child-webview"), test))]
    {
        let _ = &inner;
        Err("当前构建未启用子 webview 通道".to_string())
    }
}

/// 查询状态：顺便从后端拉一次事件，判断子页是否已就绪
///
/// 子页加载完成后会 POST /api/lab/events {event:'ready'}，
/// 主壳轮询这个端点就知道它活了 —— 不依赖 on_page_load（实测不可靠）。
#[tauri::command]
pub fn lab_poll(
    state: tauri::State<'_, LabEmbed>,
    token: String,
    port: u16,
) -> LabStatus {
    let mut inner = match state.inner.lock() {
        Ok(g) => g,
        Err(e) => {
            return LabStatus {
                mode: "child".into(),
                error: Some(format!("状态锁异常: {e}")),
                ..Default::default()
            }
        }
    };

    if !inner.ready && inner.webview.is_some() {
        if let Some(v) = crate::backend::fetch_lab_ready(port, &token) {
            if v {
                inner.ready = true;
            }
        }
    }
    LabEmbed::status_of(&inner, "child")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 视图名会被拼进 eval 注入的 JS，必须严格白名单：
    /// 只允许字母数字与 - _，防止注入任意脚本。
    #[test]
    fn rejects_unsafe_view_names() {
        let ok = ["dashboard", "experiments", "kanban", "compounds", "templates"];
        for v in ok {
            assert!(
                v.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'),
                "{v} 应该被放行"
            );
        }
        let bad = [
            "'; alert(1); '",
            "a b",
            "视图",
            "experiments'); fetch('http://evil'); ('",
        ];
        for v in bad {
            assert!(
                !(v.chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')),
                "{v} 应该被拒绝"
            );
        }
    }

    /// 初始状态：没有子 webview、不可见、未就绪
    #[test]
    fn initial_state_is_clean() {
        let lab = LabEmbed::new();
        let inner = lab.inner.lock().unwrap();
        let st = LabEmbed::status_of(&inner, "child");
        assert!(!st.open);
        assert!(!st.ready);
        assert!(!st.visible);
        assert_eq!(st.mode, "child");
        assert!(st.error.is_none());
    }

    /// 状态序列化后字段名与前端约定一致（前端 src/utils 里按这些字段名读）
    #[test]
    fn status_serializes_with_expected_field_names() {
        let lab = LabEmbed::new();
        let inner = lab.inner.lock().unwrap();
        let st = LabEmbed::status_of(&inner, "child");
        let json = serde_json::to_string(&st).unwrap();
        for key in ["open", "ready", "visible", "url", "mode", "error"] {
            assert!(json.contains(&format!("\"{key}\"")), "缺少字段 {key}");
        }
    }
}
