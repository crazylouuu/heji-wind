// ============================================================
// backend.rs —— Python 后端（FastAPI）子进程管理
//
// 职责：把「合记 ChemELN 后端」当成 Tauri 主壳的子进程来管——
//   1. 找 Python 解释器（多级回退）
//   2. 端口探测：已有健康实例就复用，没有才拉起
//   3. 拉起子进程，注入会话令牌，把 stdout/stderr 落到日志文件
//   4. 轮询 /api/health 等就绪
//   5. 应用退出时回收子进程（不留下孤儿端口）
//
// 为什么要主壳管：原来 ChemELN 是独立启动的（launch.py / 桌面快捷方式），
// 端口占用就静默退出，和工具箱是两套生命周期。统一到主壳后，
// 「开应用 → 后端就绪」是一件事，退出时也不会留僵尸进程。
//
// 零新增依赖：健康检查用 std::net::TcpStream 手写最小 HTTP/1.0 请求，
// 不引入 reqwest（避免为了探活拖进一整套 TLS 栈）。
// ============================================================
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

/// 后端默认端口（与 backend/config.py 的 DEFAULT_PORT 保持一致）
pub const DEFAULT_PORT: u16 = 8765;

/// 期望端口：环境变量 `CHEMLAB_PORT` 优先，其次默认端口。
/// 端口被占用时改这个变量比改代码方便。
pub fn default_port() -> u16 {
    std::env::var("CHEMLAB_PORT")
        .ok()
        .and_then(|s| s.trim().parse::<u16>().ok())
        .filter(|p| *p > 0)
        .unwrap_or(DEFAULT_PORT)
}

/// 启动后等待就绪的最长秒数。超时不代表失败——窗口照常显示，
/// 只是状态里带 error，前端可以提示「后端未就绪」。
const READY_TIMEOUT_SECS: u64 = 20;

/// 轮询间隔
const POLL_INTERVAL_MS: u64 = 250;

/// Windows 下隐藏子进程控制台窗口
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// 让子进程脱离父进程所属的 Job Object。
///
/// 为什么需要：Windows 上若父进程在某个 Job 里（部分启动器、沙箱、崩溃回收器
/// 会创建 Job 并设置 KILL_ON_JOB_CLOSE），父进程退出时整棵进程树会被一起杀掉。
/// 「启动器模式」下壳拉起后端就退出，一旦发生连带杀，浏览器刚打开就连接失败。
/// 带上这个标志可以让后端独立存活。
///
/// 若所在 Job 不允许 breakaway（会返回 ERROR_ACCESS_DENIED），
/// 代码会自动回退到不带该标志的创建方式。
#[cfg(windows)]
const CREATE_BREAKAWAY_FROM_JOB: u32 = 0x0100_0000;

// ---------------------------------------------------------------- 状态

/// 暴露给前端的��端状态
#[derive(Debug, Clone, Serialize, Default)]
pub struct BackendStatus {
    /// 后端是否就绪（健康检查通过）
    pub running: bool,
    /// 前端访问后端用的基地址，如 http://127.0.0.1:8765
    pub base_url: String,
    pub port: u16,
    /// 后端进程 PID（复用已有实例时为该实例的 PID，可能探测不到则为 None）
    pub pid: Option<u32>,
    /// true = 复用了本机已在运行的实例，本次没有拉起子进程
    pub reused: bool,
    /// 会话令牌：API 请求需带 X-ChemELN-Token 头
    pub token: String,
    /// 后端版本（来自 /api/health）
    pub version: String,
    /// 失败原因（成功时为空）
    pub error: Option<String>,
    /// 后端日志文件路径
    pub log_path: String,
}

// ---------------------------------------------------------------- 管理器

/// 子进程管理器。放在 Tauri 全局状态里，命令与退出钩子共用。
pub struct Backend {
    inner: Mutex<Inner>,
}

struct Inner {
    /// 由本进程拉起的子进程；复用已有实例时为 None
    child: Option<Child>,
    status: BackendStatus,
}

impl Backend {
    pub fn new() -> Self {
        Backend {
            inner: Mutex::new(Inner {
                child: None,
                status: BackendStatus {
                    port: DEFAULT_PORT,
                    ..Default::default()
                },
            }),
        }
    }

    /// 读取当前状态快照
    pub fn status(&self) -> BackendStatus {
        match self.inner.lock() {
            Ok(g) => g.status.clone(),
            Err(_) => BackendStatus::default(),
        }
    }

    /// 启动后端：先探测端口，再决定「拉起」还是「复用」。
    ///
    /// * `backend_dir` —— 源码模式下 backend/ 的绝对路径（放 main.py）
    /// * `log_dir`    —— 日志目录（不存在会创建）
    /// * `port`       —— 期望端口
    /// * `sidecar`    —— 打包版的后端 exe（PyInstaller onedir 产物）
    pub fn start(
        &self,
        backend_dir: &Path,
        log_dir: &Path,
        port: u16,
        sidecar: Option<&Path>,
    ) -> BackendStatus {
        let mut guard = match self.inner.lock() {
            Ok(g) => g,
            Err(e) => return BackendStatus {
                error: Some(format!("后端状态锁异常: {e}")),
                ..Default::default()
            },
        };

        let base_url = format!("http://127.0.0.1:{port}");

        // ① 已有健康实例 → 复用（不重复拉起，也不抢端口）
        //    注意顺序：必须先探测再回收旧子进程，否则「复用」永远命中不了
        //    （旧进程被自己杀掉后，端口就空了）
        if let Some(health) = probe_health(port) {
            // 代码指纹比对：端口上的实例跑的是不是当前这份代码？
            // 不一致时若是我们自己拉起的，直接重启（改了 Python 代码却用旧进程，
            // 这类问题极难自查 —— 日志一切正常，功能却是旧的）；
            // 若是外部实例则复用，但明确提示用户去重启。
            let running_fp = health
                .get("code_fingerprint")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let disk_fp = health
                .get("disk_fingerprint")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let stale = !running_fp.is_empty() && running_fp != disk_fp;

            if stale && guard.child.is_some() {
                // 自家进程：杀掉重启
                if let Some(mut old) = guard.child.take() {
                    let _ = old.kill();
                    let _ = old.wait();
                }
                // 落回下面走「拉起」流程
            } else {
                let token = fetch_token(port).unwrap_or_default();
                // 关键：这里**不能**清空 child 句柄。
                // 端口上的实例可能正是本进程上一轮拉起来的那个，
                // 丢掉句柄就等于放弃回收它 —— 退应用后端口被孤儿占住。
                let pid = guard.child.as_ref().map(|c| c.id());
                guard.status = BackendStatus {
                    running: true,
                    base_url,
                    port,
                    pid,
                    reused: true,
                    token,
                    version: health
                        .get("version")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string(),
                    error: if stale {
                        Some(
                            "端口上运行的是旧代码的后端实例，已复用但功能可能不一致。\
                             请在「设置 → 后端服务」点「重启后端」。"
                                .to_string(),
                        )
                    } else {
                        None
                    },
                    log_path: guard.status.log_path.clone(),
                };
                return guard.status.clone();
            }
        }

        // ② 端口被别的服务占着（常见：旧版 ChemELN 还在跑）
        //    这时不能再拉一个——Python 侧发现端口占用会静默退出，
        //    结果就是「启动了但永远不��绪」，比直接报错更难查。
        if port_open(port) {
            guard.status.error = Some(format!(
                "端口 {port} 已被其它服务占用（可能是旧版 ChemELN 实例）。\
                 请先关闭该实例，或设置环境变量 CHEMLAB_PORT 使用其它端口。"
            ));
            guard.status.port = port;
            guard.status.base_url = base_url;
            return guard.status.clone();
        }

        // ③ 回收本进程此前拉起的旧子进程（restart 场景走的是 stop()，
        //    这里是兜底：端口上的实例不是我们的，但手里还攥着旧进程）
        if let Some(mut old) = guard.child.take() {
            let _ = old.kill();
            let _ = old.wait();
        }

        // ④ 找后端启动器（打包 sidecar 优先，其次 Python 解释器）
        let launcher = match find_backend_launcher(backend_dir, sidecar) {
            Some(l) => l,
            None => {
                guard.status.error = Some(
                    "找不到可用的后端程序：\n\
                     · 打包版应存在 resources\\backend\\ChemLabBackend.exe；\n\
                     · 源码版请在 backend/ 下执行 `python -m venv venv && \
                     venv\\Scripts\\pip install -r requirements.txt`；\n\
                     · 或设置环境变量 CHEMLAB_PYTHON 指向 Python 解释器。"
                        .to_string(),
                );
                return guard.status.clone();
            }
        };

        // ④ 日志文件
        if let Err(e) = std::fs::create_dir_all(log_dir) {
            guard.status.error = Some(format!("创建日志目录失败: {e}"));
            return guard.status.clone();
        }
        let log_path = log_dir.join("backend.log");
        let log_file = match OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
        {
            Ok(f) => f,
            Err(e) => {
                guard.status.error = Some(format!("打开后端日志失败: {e}"));
                return guard.status.clone();
            }
        };
        let err_file = match log_file.try_clone() {
            Ok(f) => f,
            Err(e) => {
                guard.status.error = Some(format!("复制日志句柄失败: {e}"));
                return guard.status.clone();
            }
        };

        // ⑤ 生成会话令牌并注入环境变量
        //    后端 utils/security.py 优先读 CHEMLAB_TOKEN，
        //    这样主壳与后端共享同一个令牌，前端从主壳拿到即可直接用。
        let token = new_token();

        // 打包 sidecar：直接跑 exe，参数只有 --port
        // 源码版：<python> backend/main.py --port N
        let mut cmd = match &launcher {
            BackendLauncher::Sidecar { exe } => {
                let mut c = Command::new(exe);
                c.current_dir(exe.parent().unwrap_or(backend_dir));
                c
            }
            BackendLauncher::Python { exe, script } => {
                let mut c = Command::new(exe);
                c.arg(script);
                c.current_dir(backend_dir);
                c
            }
        };
        cmd.arg("--port")
            .arg(port.to_string())
            .env("CHEMLAB_TOKEN", &token)
            // 让子进程知道自己是被主壳拉起来的（后端可用它改启动行为）
            .env("CHEMLAB_PARENT", "tauri")
            // stdout 重定向到文件时 Python 默认是块缓冲，日志会迟迟不落盘；
            // 关掉缓冲才能实时看到后端启动过程
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::from(log_file))
            .stderr(Stdio::from(err_file));

        // 创建子进程。先尝试带 BREAKAWAY（脱离父进程的 Job，避免壳退出时被
        // 连带杀掉）；若所在 Job 不允许 breakaway（ERROR_ACCESS_DENIED），
        // 退回普通创建 —— 不能因为一个「优化」让后端彻底起不来。
        #[cfg(windows)]
        let spawn_result = {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB);
            match cmd.spawn() {
                Ok(c) => Ok(c),
                Err(e) => {
                    println!("[ChemLab] breakaway 创建失败（{e}），回退普通创建");
                    cmd.creation_flags(CREATE_NO_WINDOW);
                    cmd.spawn()
                }
            }
        };
        #[cfg(not(windows))]
        let spawn_result = cmd.spawn();

        let child = match spawn_result {
            Ok(c) => c,
            Err(e) => {
                let desc = match &launcher {
                    BackendLauncher::Sidecar { exe } => exe.display().to_string(),
                    BackendLauncher::Python { exe, .. } => exe.display().to_string(),
                };
                guard.status.error = Some(format!("启动后端进程失败 ({desc}): {e}"));
                return guard.status.clone();
            }
        };
        let pid = child.id();

        // ⑥ 等就绪
        let ready = wait_ready(port, READY_TIMEOUT_SECS);
        let version = if ready {
            probe_health(port)
                .and_then(|h| h.get("version").and_then(|v| v.as_str()).map(String::from))
                .unwrap_or_default()
        } else {
            String::new()
        };

        guard.child = Some(child);
        guard.status = BackendStatus {
            running: ready,
            base_url,
            port,
            pid: Some(pid),
            reused: false,
            token,
            version,
            error: if ready {
                None
            } else {
                Some(format!(
                    "后端启动超时（{}s 未就绪），详见日志 {}",
                    READY_TIMEOUT_SECS,
                    log_path.display()
                ))
            },
            log_path: log_path.to_string_lossy().to_string(),
        };
        guard.status.clone()
    }

    /// 回收子进程（应用退出时调用）
    ///
    /// 只杀本进程拉起的子进程；复用的已有实例不该被我们杀掉
    /// （可能是用户手动开的服务）。
    pub fn stop(&self) {
        let mut guard = match self.inner.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        if let Some(mut child) = guard.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        guard.status.running = false;
    }

    /// 交棒：放弃对子进程的所有权，但**不杀它**。
    ///
    /// 用途：「启动器模式」下主壳打开浏览器后要自行退出，
    /// 但后端必须继续活着给浏览器用。若不做这一步，退出钩子（以及 Drop）
    /// 会把它当作自己的子进程杀掉 —— 浏览器刚打开就 404。
    ///
    /// 返回被交棒的 PID（用于日志）。
    pub fn detach(&self) -> Option<u32> {
        let mut guard = match self.inner.lock() {
            Ok(g) => g,
            Err(_) => return None,
        };
        let pid = guard.child.as_ref().map(|c| c.id());
        // 关键：只丢句柄、不 kill。之后 stop()/Drop 都拿不到它，自然也就杀不了。
        guard.child = None;
        pid
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        // 兜底：即使退出钩子没跑到，也不能留下占着端口的孤儿进程
        if let Ok(mut g) = self.inner.lock() {
            if let Some(mut child) = g.child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

// ---------------------------------------------------------------- 目录解析

/// 解析后端代码目录（含 main.py）
///
/// - debug（开发模式）：`src-tauri/../backend`（仓库内）
/// - release（打包模式）：资源目录下的 `backend/`（P6 打包时随 sidecar 一起分发）
/// 把后端启动过程写进 `startup.log`（覆盖写，只保留最近一次启动）。
///
/// 打包版是 GUI 子系统，没有控制台，`println!` 的输出看不到；`Backend::start()`
/// 的失败分支也只把原因写进内存里的 `status.error`。一旦窗口没起来（或用户
/// 根本没注意设置页的提示），这类失败就完全不可见。
///
/// 写失败时静默忽略 —— 诊断信息本身不该影响应用启动。
pub fn write_startup_log(log_dir: &Path, fields: &[(&str, String)]) {
    let _ = std::fs::create_dir_all(log_dir);
    let path = log_dir.join("startup.log");
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let mut s = format!("=== startup @ unix {now} ===\n");
    for (k, v) in fields {
        s.push_str(&format!("{k:14} = {v}\n"));
    }
    let _ = std::fs::write(path, s);
}

pub fn backend_dir(app: &tauri::AppHandle) -> PathBuf {
    let _ = app; // debug 分支不用它，但保留参数签名一致
    #[cfg(debug_assertions)]
    {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .map(|p| p.join("backend"))
            .unwrap_or_else(|| PathBuf::from("backend"))
    }
    #[cfg(not(debug_assertions))]
    {
        use tauri::Manager;
        app.path()
            .resource_dir()
            .map(|d| d.join("backend"))
            .unwrap_or_else(|_| PathBuf::from("backend"))
    }
}

// ---------------------------------------------------------------- 后端启动器发现

/// 后端启动方式
#[derive(Debug, Clone, PartialEq)]
pub enum BackendLauncher {
    /// Python 解释器 + 脚本：`<解释器> backend/main.py --port N`
    Python { exe: PathBuf, script: PathBuf },
    /// 打包好的 sidecar：`<exe> --port N`（PyInstaller onedir，无需系统 Python）
    Sidecar { exe: PathBuf },
}

/// 找一个可用的后端启动方式。
///
/// 回退顺序（先具体后通用）：
///   1. 环境变量 `CHEMLAB_PYTHON`（运维/开发显式指定解释器）
///   2. 打包模式：PyInstaller sidecar `resources/backend/ChemLabBackend.exe`
///      （P6 打包后随 NSIS 分发，用户机器上不需要装 Python）
///   3. 源码模式：`backend/venv/Scripts/python.exe`（Windows）
///      或 `backend/venv/bin/python`（macOS/Linux）
///   4. 系统 PATH 上的 `python` / `python3`
pub fn find_backend_launcher(
    backend_dir: &Path,
    sidecar: Option<&Path>,
) -> Option<BackendLauncher> {
    // ① 环境变量
    if let Ok(p) = std::env::var("CHEMLAB_PYTHON") {
        let p = PathBuf::from(p.trim());
        if p.exists() {
            return Some(BackendLauncher::Python {
                exe: p,
                script: backend_dir.join("main.py"),
            });
        }
    }

    // ② 打包 sidecar（优先于系统 Python：用户机器上可能压根没装 Python）
    if let Some(sc) = sidecar {
        if sc.exists() {
            return Some(BackendLauncher::Sidecar { exe: sc.to_path_buf() });
        }
    }

    // ③ backend/venv
    let venv_dir = backend_dir.join("venv");
    for rel in [
        Path::new("Scripts/python.exe"),
        Path::new("bin/python"),
        Path::new("Scripts/python"),
    ] {
        let cand = venv_dir.join(rel);
        if cand.exists() {
            return Some(BackendLauncher::Python {
                exe: cand,
                script: backend_dir.join("main.py"),
            });
        }
    }

    // ④ PATH
    for name in ["python", "python3", "py"] {
        if which(name) {
            return Some(BackendLauncher::Python {
                exe: PathBuf::from(name),
                script: backend_dir.join("main.py"),
            });
        }
    }
    None
}

/// 打包模式下 sidecar 的位置。
///
/// 候选布局（Tauri 各版本/平台的资源放置方式不完全一致，多试几个更稳）：
///   - `<资源目录>/backend/ChemLabBackend.exe`
///   - `<资源目录>/resources/backend/ChemLabBackend.exe`（Windows 上
///     `resource_dir()` 返回 exe 目录，而 resources 资源在 exe 同级的
///     `resources/` 子目录里）
///   - `<exe 同级>/backend/ChemLabBackend.exe`
pub fn sidecar_path(resource_dir: Option<&Path>) -> Option<PathBuf> {
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Some(dir) = resource_dir {
        roots.push(dir.join("backend"));
        roots.push(dir.join("resources").join("backend"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            roots.push(dir.join("backend"));
            roots.push(dir.join("resources").join("backend"));
        }
    }
    for root in roots {
        for name in ["ChemLabBackend.exe", "ChemLabBackend"] {
            let cand = root.join(name);
            if cand.exists() {
                return Some(cand);
            }
        }
    }
    None
}

/// 极简 which：只判断 PATH 里能否找到可执行文件
fn which(name: &str) -> bool {
    let path_var = match std::env::var_os("PATH") {
        Some(p) => p,
        None => return false,
    };
    let exts: Vec<String> = if cfg!(windows) {
        std::env::var("PATHEXT")
            .unwrap_or_else(|_| ".EXE;.CMD;.BAT;.COM".to_string())
            .split(';')
            .map(|s| s.to_ascii_lowercase())
            .collect()
    } else {
        vec![String::new()]
    };
    for dir in std::env::split_paths(&path_var) {
        for ext in &exts {
            let cand = dir.join(format!("{name}{ext}"));
            if cand.is_file() {
                return true;
            }
            if ext.is_empty() {
                let cand = dir.join(name);
                if cand.is_file() {
                    return true;
                }
            }
        }
    }
    false
}

// ---------------------------------------------------------------- HTTP 探活

/// 发一个最小 HTTP/1.0 GET，返回响应体（失败返回 None）
fn http_get(port: u16, path: &str, timeout: Duration) -> Option<String> {
    http_get_with_headers(port, path, timeout, &[])
}

/// 发一个最小 HTTP/1.0 GET，可带自定义请求头（如会话令牌）
fn http_get_with_headers(
    port: u16,
    path: &str,
    timeout: Duration,
    headers: &[(String, String)],
) -> Option<String> {
    let addrs: Vec<SocketAddr> = format!("127.0.0.1:{port}").to_socket_addrs().ok()?.collect();
    let addr = addrs.first()?;
    let mut stream = TcpStream::connect_timeout(addr, timeout).ok()?;
    stream.set_read_timeout(Some(timeout)).ok()?;
    stream.set_write_timeout(Some(timeout)).ok()?;

    // 用 HTTP/1.0：服务端响应后直接关连接，不会分块，省掉解码 chunked 的麻烦
    let mut req = format!(
        "GET {path} HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nAccept: application/json\r\nConnection: close\r\n"
    );
    for (k, v) in headers {
        req.push_str(&format!("{k}: {v}\r\n"));
    }
    req.push_str("\r\n");
    stream.write_all(req.as_bytes()).ok()?;

    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).ok()?;
    let text = String::from_utf8_lossy(&raw).to_string();

    let sep = text.find("\r\n\r\n")?;
    let head = &text[..sep];
    let body = &text[sep + 4..];

    // 状态码
    let status_ok = head
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok())
        .map(|c| (200..300).contains(&c))
        .unwrap_or(false);
    if !status_ok {
        return None;
    }

    // 保险起见处理一次 chunked（万一路由中间有代理层）
    if head.to_ascii_lowercase().contains("transfer-encoding: chunked") {
        return Some(dechunk(body));
    }
    Some(body.to_string())
}

/// 解码 chunked 响应体
fn dechunk(body: &str) -> String {
    let mut out = String::new();
    let mut rest = body;
    loop {
        let line_end = match rest.find("\r\n") {
            Some(i) => i,
            None => break,
        };
        let size_line = &rest[..line_end];
        let size = match usize::from_str_radix(size_line.trim().split(';').next().unwrap_or(""), 16) {
            Ok(n) => n,
            Err(_) => break,
        };
        rest = &rest[line_end + 2..];
        if size == 0 {
            break;
        }
        if rest.len() < size {
            out.push_str(rest);
            break;
        }
        out.push_str(&rest[..size]);
        rest = &rest[size..];
        if rest.starts_with("\r\n") {
            rest = &rest[2..];
        }
    }
    out
}

/// 健康检查：返回 /api/health 的 JSON（解析失败返回 None）
///
/// 只认 service == "ChemLab"：旧版 ChemELN 实例也提供 /api/health，
/// 误当成自己的后端复用会导致数据写到另一个库。
pub fn probe_health(port: u16) -> Option<serde_json::Value> {
    let body = http_get(port, "/api/health", Duration::from_millis(1500))?;
    let v: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    if v.get("service").and_then(|s| s.as_str()) != Some("ChemLab") {
        return None;
    }
    Some(v)
}

/// 端口是否有人监听（不关心是什么服务）
fn port_open(port: u16) -> bool {
    let addrs: Vec<SocketAddr> = match format!("127.0.0.1:{port}").to_socket_addrs() {
        Ok(a) => a.collect(),
        Err(_) => return false,
    };
    addrs
        .first()
        .map(|a| TcpStream::connect_timeout(a, Duration::from_millis(500)).is_ok())
        .unwrap_or(false)
}

/// 取会话令牌（/api/session 是免鉴权路径）
pub fn fetch_token(port: u16) -> Option<String> {
    let body = http_get(port, "/api/session", Duration::from_millis(1500))?;
    let v: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    v.get("token")
        .and_then(|t| t.as_str())
        .map(String::from)
}

/// 轮询直到就绪
pub fn wait_ready(port: u16, timeout_secs: u64) -> bool {
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    while Instant::now() < deadline {
        if probe_health(port).is_some() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(POLL_INTERVAL_MS));
    }
    false
}

/// 查后端是否收到过子页的 ready 上报（P5 子 webview 就绪判定）
///
/// 子页加载完成后会 POST /api/lab/events {event:"ready"}；
/// 这里只关心「有没有 ready 事件」，不看内容。
pub fn fetch_lab_ready(port: u16, token: &str) -> Option<bool> {
    let headers: Vec<(String, String)> = if token.is_empty() {
        Vec::new()
    } else {
        vec![("X-ChemLab-Token".to_string(), token.to_string())]
    };
    let body = http_get_with_headers(
        port,
        "/api/lab/events?since=0",
        Duration::from_millis(1500),
        &headers,
    )?;
    let v: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    let events = v.get("events")?.as_array()?;
    Some(
        events
            .iter()
            .any(|e| e.get("event").and_then(|s| s.as_str()) == Some("ready")),
    )
}

/// 生成一个随机会话令牌（URL 安全字符集）
fn new_token() -> String {
    // 32 字节随机 → base64url 风格字符串
    let bytes: [u8; 32] = {
        let mut b = [0u8; 32];
        // 用系统时间 + 进程 id + 地址做种子源；这里不引入 rand crate，
        // 安全性由「仅回环可达 + 随机性够用」保证（真正的对手是局域网）。
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        let pid = std::process::id() as u64;
        let mut state = now ^ (pid << 32) ^ (&b as *const _ as u64);
        for slot in b.iter_mut() {
            // xorshift64*
            state ^= state >> 12;
            state ^= state << 25;
            state ^= state >> 27;
            let r = state.wrapping_mul(0x2545_F491_4F6C_DD1D);
            *slot = (r >> 33) as u8;
        }
        b
    };
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_is_hex_and_long() {
        let t = new_token();
        assert_eq!(t.len(), 64);
        assert!(t.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn dechunk_works() {
        let raw = "5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n";
        assert_eq!(dechunk(raw), "hello world");
    }

    /// 端到端：拉起真实后端 → 复用 → 停止后端口释放。
    ///
    /// 需要本机已装好 Python 依赖（backend/venv），默认不跑：
    ///   cargo test --lib -- --ignored spawns_reuses_and_stops_backend
    #[test]
    #[ignore = "需要本机 Python 环境与后端依赖"]
    fn spawns_reuses_and_stops_backend() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("仓库根目录")
            .to_path_buf();
        let backend_dir = repo.join("backend");
        let log_dir = std::env::temp_dir().join("chemlab-backend-test");
        let port = 8798u16;

        let be = Backend::new();
        let st = be.start(&backend_dir, &log_dir, port, None);
        assert!(st.running, "后端未就绪: {:?}", st.error);
        assert!(!st.token.is_empty(), "没拿到会话令牌");
        assert_eq!(st.port, port);
        assert!(st.base_url.contains(&port.to_string()));
        assert!(!st.reused, "首次启动不该是复用");

        // 再 start 一次：应命中已有实例（复用），而不是拉第二个
        let st2 = be.start(&backend_dir, &log_dir, port, None);
        assert!(st2.running, "复用失败: {:?}", st2.error);
        assert!(st2.reused, "第二次 start 应复用已有实例");

        // 停止后端口应释放（不留孤儿进程）
        be.stop();
        std::thread::sleep(Duration::from_millis(1200));
        assert!(!port_open(port), "停止后端口仍被占用，说明子进程没被回收");
    }

    /// 在临时目录里造一个假的 sidecar 布局，返回临时根目录
    fn fake_layout(rel: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "chemlab-sidecar-test-{}-{}",
            std::process::id(),
            rel.replace(['/', '\\', '.'], "_")
        ));
        let dir = root.join(rel);
        std::fs::create_dir_all(&dir).expect("建临时目录失败");
        // 只要有这个文件名即可（sidecar_path 只做存在性判断）
        std::fs::write(dir.join("ChemLabBackend.exe"), b"stub").expect("写桩文件失败");
        root
    }

    #[test]
    fn sidecar_found_in_resources_subdir() {
        // 安装版的真实布局：<资源目录>/resources/backend/ChemLabBackend.exe
        // Windows 上 resource_dir() 返回 exe 所在目录，而 resources 是它的子目录，
        // 所以第二个候选必须能命中 —— 这是安装版能正常拉起后端的前提。
        let root = fake_layout("resources/backend");
        let found = sidecar_path(Some(&root));
        assert!(
            found.is_some(),
            "resources/backend 候选未命中，安装版会找不到后端"
        );
        assert!(found.unwrap().ends_with("ChemLabBackend.exe"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn sidecar_found_in_backend_subdir() {
        let root = fake_layout("backend");
        let found = sidecar_path(Some(&root));
        assert!(found.is_some(), "backend 候选未命中");
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn sidecar_none_when_absent() {
        // 两个候选都没有时必须是 None（交给 find_backend_launcher 回退到 Python）
        let root = std::env::temp_dir().join(format!("chemlab-sidecar-empty-{}", std::process::id()));
        std::fs::create_dir_all(&root).ok();
        let _ = std::fs::remove_file(root.join("backend").join("ChemLabBackend.exe"));
        let _ = std::fs::remove_file(
            root.join("resources").join("backend").join("ChemLabBackend.exe"),
        );
        // 注意：sidecar_path 还会检查 current_exe() 所在目录，
        // 测试二进制目录下不会有 backend/ChemLabBackend.exe，所以这里预期 None
        assert!(sidecar_path(Some(&root)).is_none());
        let _ = std::fs::remove_dir_all(&root);
    }
}
