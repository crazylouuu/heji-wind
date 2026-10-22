/**
 * ChemELN Main Application — SPA router, state, and view rendering.
 */

const App = {
  state: {
    view: 'dashboard',
    experiments: [],
    tags: [],
    projects: [],
    currentExp: null,
    sortField: 'updated_at',
    sortOrder: 'desc',
    filters: {},
  },

  contentEl: null,
  pageTitleEl: null,

  init() {
    this.contentEl = document.getElementById('content');
    this.pageTitleEl = document.getElementById('page-title');

    // Nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.onclick = () => this.navigate(item.dataset.view);
    });

    // ==== P4：主壳桥接（合记 ChemLab）====
    // 整合后本页被主壳以 iframe 嵌入，主壳用 postMessage 控制视图切换。
    // 协议（主壳 → 本页）：
    //   { type: 'chemlab:invoke', id, method: 'navigate', params: { view } }
    // 回复（本页 → 主壳）：
    //   { type: 'chemlab:response', id, ok: true }
    // 只接受本机来源的消息 —— 本页同源访问也能发，但那是自己的窗口，无害。
    window.addEventListener('message', (e) => {
      const msg = e.data;
      if (!msg || msg.type !== 'chemlab:invoke') return;
      const allowed = [
        'http://127.0.0.1:8765',
        'http://localhost:8765',
        'http://tauri.localhost',
        'tauri://localhost',
        'http://localhost:1420',
        'http://127.0.0.1:1420',
      ];
      if (msg.origin && allowed.indexOf(msg.origin) === -1) return;
      const { method, params, id } = msg;
      if (method === 'navigate' && params && params.view) {
        App.navigate(params.view);
        if (e.source && e.source.postMessage) {
          e.source.postMessage({ type: 'chemlab:response', id, ok: true }, '*');
        }
      }
    });

    // New experiment button
    document.getElementById('new-exp-btn').onclick = () => this.showNewExpModal();

    // Global search
    document.getElementById('global-search').onkeydown = (e) => {
      if (e.key === 'Enter' && e.target.value.trim()) {
        this.state.view = 'search-results';
        this.state.searchQuery = e.target.value;
        this.render();
      }
    };

    // Load initial data
    this.loadTags();
    this.navigate('dashboard');

    // ==== P5：原生子 webview 模式下的桥接 ====
    // 在子 webview 里（http://127.0.0.1:8765 远程 origin）没法调 Tauri 命令，
    // 所以主壳→子页走 Rust eval 注入，约定一个入口函数：
    //   主壳 eval: window.__chemlabNav('experiments')
    //   这里实现它，内部转到 App.navigate
    window.__chemlabNav = (view) => {
      if (view && typeof view === 'string') {
        App.navigate(view);
        return true;
      }
      return false;
    };

    // 子页→主壳：加载完成后向后端报个到，主壳轮询后端就知道子页活了
    // （on_page_load 对子 webview 不可靠，不能用来判断就绪）
    this.reportReady();
  },

  /** 向上报就绪（失败不影响使用，静默忽略） */
  reportReady() {
    try {
      // 走 API.request 而不是裸 fetch：/api/lab/events 在鉴权保护下，
      // API.request 会自动带上引导来的会话令牌头
      if (typeof API !== 'undefined' && API && API.request) {
        API.request('POST', '/api/lab/events', { event: 'ready' }).catch(() => {});
      }
    } catch (e) {
      /* 后端没有这个端点（老版本）时忽略 */
    }
  },

  navigate(view) {
    this.state.view = view;
    document.querySelectorAll('.nav-item').forEach(i =>
      i.classList.toggle('active', i.dataset.view === view));
    this.render();
  },

  async render() {
    const view = this.state.view;
    const titles = {
      'dashboard': '仪表盘',
      'experiments': '实验记录',
      'kanban': '看板视图',
      'experiment-detail': '实验详情',
      'compounds': '化合物库',
      'structure-search': '结构检索',
      'templates': '模板管理',
      'tags': '标签管理',
      'data': '导入导出',
      'backup': '备份管理',
      'search-results': '搜索结果',
    };
    this.pageTitleEl.textContent = titles[view] || 'ChemELN';

    switch (view) {
      case 'dashboard': await this.renderDashboard(); break;
      case 'experiments': await this.renderExperiments(); break;
      case 'kanban': await this.renderKanban(); break;
      case 'experiment-detail': await this.renderExperimentDetail(); break;
      case 'compounds': await this.renderCompounds(); break;
      case 'structure-search': await this.renderStructureSearch(); break;
      case 'templates': await this.renderTemplates(); break;
      case 'tags': await this.renderTags(); break;
      case 'data': await this.renderData(); break;
      case 'backup': await this.renderBackup(); break;
      case 'search-results': await this.renderSearchResults(); break;
      default: this.contentEl.innerHTML = '<div class="empty-state"><h3>未知视图</h3></div>';
    }
  },

  // --- Dashboard ---
  async renderDashboard() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const stats = await API.getStats();
      const statusColors = { draft: 'status-draft', ongoing: 'status-ongoing', completed: 'status-completed', archived: 'status-archived' };
      const statusNames = { draft: '草稿', ongoing: '进行中', completed: '已完成', archived: '已归档' };

      let statsHtml = `
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">实验总数</div>
            <div class="stat-value">${stats.total_experiments}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">化合物数</div>
            <div class="stat-value">${stats.total_compounds}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">模板数</div>
            <div class="stat-value">${stats.total_templates}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">平均收率</div>
            <div class="stat-value">${stats.avg_yield}%</div>
          </div>
        </div>
      `;

      // Status breakdown
      let statusHtml = '<div class="card"><div class="card-header"><h3>📊 按状态分布</h3></div><div class="card-body">';
      if (Object.keys(stats.by_status).length === 0) {
        statusHtml += '<p style="color:var(--text-muted)">暂无数据</p>';
      } else {
        for (const [s, c] of Object.entries(stats.by_status)) {
          statusHtml += `<span class="status-badge ${statusColors[s]||''}" style="margin:4px;font-size:13px;padding:4px 12px">${statusNames[s]||s}: ${c}</span>`;
        }
      }
      statusHtml += '</div></div>';

      // Recent activity
      let recentHtml = '<div class="card" style="margin-top:16px"><div class="card-header"><h3>🕘 最近活动</h3></div><div class="card-body">';
      if (stats.recent.length === 0) {
        recentHtml += '<div class="empty-state"><div class="icon">📝</div><h3>还没有实验</h3><p>点击"新建实验"开始记录</p></div>';
      } else {
        recentHtml += '<table class="exp-table"><thead><tr><th>标题</th><th>状态</th><th>更新时间</th></tr></thead><tbody>';
        for (const r of stats.recent) {
          recentHtml += `<tr onclick="App.openExperiment(${r.id})">
            <td>${this.escape(r.title)}</td>
            <td><span class="status-badge ${statusColors[r.status]||''}">${statusNames[r.status]||r.status}</span></td>
            <td style="color:var(--text-muted)">${r.updated_at}</td>
          </tr>`;
        }
        recentHtml += '</tbody></table>';
      }
      recentHtml += '</div></div>';

      this.contentEl.innerHTML = statsHtml + statusHtml + recentHtml;
    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
    }
  },

  // --- Experiments List ---
  async renderExperiments() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const [exps, tags, projects] = await Promise.all([
        API.listExperiments(this.state.filters),
        API.listTags(),
        API.listProjects(),
      ]);
      this.state.tags = tags.tags;
      this.state.projects = projects.projects;

      const statusColors = { draft: 'status-draft', ongoing: 'status-ongoing', completed: 'status-completed', archived: 'status-archived' };
      const statusNames = { draft: '草稿', ongoing: '进行中', completed: '已完成', archived: '已归档' };

      // Filter bar
      let filterHtml = `
        <div class="filter-bar">
          <select id="filter-project" onchange="App.updateFilter('project', this.value)">
            <option value="">所有项目</option>
            ${projects.projects.map(p => `<option value="${this.escape(p)}" ${this.state.filters.project === p ? 'selected' : ''}>${this.escape(p)}</option>`).join('')}
          </select>
          <select id="filter-status" onchange="App.updateFilter('status', this.value)">
            <option value="">所有状态</option>
            <option value="draft" ${this.state.filters.status === 'draft' ? 'selected' : ''}>草稿</option>
            <option value="ongoing" ${this.state.filters.status === 'ongoing' ? 'selected' : ''}>进行中</option>
            <option value="completed" ${this.state.filters.status === 'completed' ? 'selected' : ''}>已完成</option>
            <option value="archived" ${this.state.filters.status === 'archived' ? 'selected' : ''}>已归档</option>
          </select>
          <select id="filter-tag" onchange="App.updateFilter('tag', this.value)">
            <option value="">所有标签</option>
            ${tags.tags.map(t => `<option value="${this.escape(t.name)}" ${this.state.filters.tag === t.name ? 'selected' : ''}>${this.escape(t.name)}</option>`).join('')}
          </select>
          <select id="filter-step" onchange="App.updateFilter('step', this.value)">
            <option value="">所有步骤</option>
            ${Array.from({length: 10}, (_, i) => i + 1).map(n =>
              `<option value="${n}" ${String(this.state.filters.step) === String(n) ? 'selected' : ''}>第${n}步</option>`).join('')}
          </select>
          <input type="number" id="filter-min-yield" placeholder="最低收率%" style="width:100px" oninput="App.updateFilter('min_yield', this.value)">
          <input type="number" id="filter-min-purity" placeholder="最低纯度%" style="width:100px" oninput="App.updateFilter('min_purity', this.value)">
          <button class="btn btn-ghost btn-sm" onclick="App.clearFilters()">清除筛选</button>
        </div>
      `;

      // Table
      let tableHtml = '<div class="card"><div class="card-body" style="padding:0;overflow-x:auto">';
      if (exps.count === 0) {
        tableHtml += `<div class="empty-state"><div class="icon">📝</div><h3>暂无实验</h3><p>点击"新建实验"开始记录</p><button class="btn btn-primary" onclick="App.showNewExpModal()">+ 新建实验</button></div>`;
      } else {
        const sortArrow = (f) => this.state.sortField === f ? (this.state.sortOrder === 'desc' ? ' ↓' : ' ↑') : '';
        tableHtml += `<table class="exp-table">
          <thead><tr>
            <th onclick="App.sortBy('title')">标题${sortArrow('title')}</th>
            <th onclick="App.sortBy('project')">项目${sortArrow('project')}</th>
            <th onclick="App.sortBy('status')">状态${sortArrow('status')}</th>
            <th onclick="App.sortBy('exp_date')">日期${sortArrow('exp_date')}</th>
            <th>步骤</th>
            <th onclick="App.sortBy('target_compound')">目标化合物${sortArrow('target_compound')}</th>
            <th onclick="App.sortBy('yield_pct')">收率${sortArrow('yield_pct')}</th>
            <th onclick="App.sortBy('purity_pct')">纯度${sortArrow('purity_pct')}</th>
            <th>标签</th>
            <th onclick="App.sortBy('updated_at')">更新时间${sortArrow('updated_at')}</th>
            <th style="width:110px">操作</th>
          </tr></thead><tbody>`;
        for (const e of exps.experiments) {
          const expTags = (e.tags || []).map(t => `<span class="tag" style="background:${t.color}">${this.escape(t.name)}</span>`).join('');
          tableHtml += `<tr onclick="App.openExperiment(${e.id})" style="cursor:pointer">
            <td style="font-weight:500">${this.escape(e.title)}</td>
            <td>${this.escape(e.project || '')}</td>
            <td><span class="status-badge ${statusColors[e.status]||''}">${statusNames[e.status]||e.status}</span></td>
            <td>${e.exp_date || '—'}</td>
            <td>${e.step_no ? '第' + e.step_no + '步' : '—'}</td>
            <td>${this.escape(e.target_compound || '—')}</td>
            <td>${e.yield_pct !== null ? e.yield_pct + '%' : '—'}</td>
            <td>${e.purity_pct !== null ? e.purity_pct + '%' : '—'}</td>
            <td>${expTags}</td>
            <td style="color:var(--text-muted);font-size:12px">${e.updated_at || ''}</td>
            <td onclick="event.stopPropagation()" style="white-space:nowrap">
              <button class="btn btn-secondary btn-sm" onclick="App.openExperiment(${e.id})" title="编辑此实验">✏️ 编辑</button>
              <button class="btn btn-danger btn-sm" onclick="App.deleteExperimentFromList(${e.id})" title="删除此实验">🗑️</button>
            </td>
          </tr>`;
        }
        tableHtml += '</tbody></table>';
      }
      tableHtml += '</div></div>';

      this.contentEl.innerHTML = filterHtml + tableHtml;
    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
    }
  },

  // --- Kanban View ---
  async renderKanban() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const exps = await API.listExperiments();
      const statuses = ['draft', 'ongoing', 'completed', 'archived'];
      const statusNames = { draft: '草稿', ongoing: '进行中', completed: '已完成', archived: '已归档' };

      let html = '<div class="kanban">';
      for (const s of statuses) {
        const items = exps.experiments.filter(e => e.status === s);
        html += `<div class="kanban-col">
          <div class="kanban-col-header">${statusNames[s]} <span class="badge">${items.length}</span></div>
          <div class="kanban-col-body">
            ${items.map(e => `
              <div class="kanban-card" onclick="App.openExperiment(${e.id})">
                <h4>${this.escape(e.title)}</h4>
                <div class="meta">
                  ${e.project ? '📁 ' + this.escape(e.project) + ' · ' : ''}
                  ${e.target_compound ? '🎯 ' + this.escape(e.target_compound) : ''}
                </div>
                ${e.yield_pct !== null ? `<div class="meta">📊 收率 ${e.yield_pct}%</div>` : ''}
                ${(e.tags||[]).map(t => `<span class="tag" style="background:${t.color}">${this.escape(t.name)}</span>`).join('')}
              </div>
            `).join('') || '<div style="text-align:center;color:var(--text-light);padding:20px;font-size:12px">无</div>'}
          </div>
        </div>`;
      }
      html += '</div>';
      this.contentEl.innerHTML = html;
    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
    }
  },

  // --- Experiment Detail ---
  async openExperiment(id) {
    this.state.currentExpId = id;
    this.state.view = 'experiment-detail';
    this.render();
  },

  async renderExperimentDetail() {
    const id = this.state.currentExpId;
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const exp = await API.getExperiment(id);
      this.state.currentExp = exp;

      const statusColors = { draft: 'status-draft', ongoing: 'status-ongoing', completed: 'status-completed', archived: 'status-archived' };
      const statusNames = { draft: '草稿', ongoing: '进行中', completed: '已完成', archived: '已归档' };
      const allTags = this.state.tags || (await API.listTags()).tags;

      this.contentEl.innerHTML = `
        <div class="exp-detail">
          <div class="exp-meta-bar">
            <div class="meta-field">
              <label>标题</label>
              <input type="text" id="exp-title" value="${this.escape(exp.title)}" style="width:300px;font-weight:600">
            </div>
            <div class="meta-field">
              <label>项目</label>
              <input type="text" id="exp-project" value="${this.escape(exp.project)}" list="project-list" style="width:150px">
              <datalist id="project-list">${this.state.projects.map(p=>`<option value="${this.escape(p)}">`).join('')}</datalist>
            </div>
            <div class="meta-field">
              <label>状态</label>
              <select id="exp-status">
                ${Object.entries(statusNames).map(([v,n])=>`<option value="${v}" ${exp.status===v?'selected':''}>${n}</option>`).join('')}
              </select>
            </div>
            <div class="meta-field">
              <label>步骤（第几步）</label>
              <input type="number" id="exp-step" value="${exp.step_no ?? ''}" style="width:80px" step="1" min="1" placeholder="选填">
            </div>
            <div class="meta-field">
              <label>日期</label>
              <input type="date" id="exp-date" value="${exp.exp_date}">
            </div>
            <div class="meta-field">
              <label>目标化合物</label>
              <input type="text" id="exp-target" value="${this.escape(exp.target_compound)}" style="width:150px">
            </div>
            <div class="meta-field">
              <label>收率%</label>
              <input type="number" id="exp-yield" value="${exp.yield_pct ?? ''}" style="width:70px" step="0.1">
            </div>
            <div class="meta-field">
              <label>纯度%</label>
              <input type="number" id="exp-purity" value="${exp.purity_pct ?? ''}" style="width:70px" step="0.1">
            </div>
          </div>

          <div class="tabs">
            <div class="tab active" data-tab="structure">⚗️ 反应与结构</div>
            <div class="tab" data-tab="reagents">📊 投料表</div>
            <div class="tab" data-tab="content">📝 实验内容</div>
            <div class="tab" data-tab="attachments">📎 附件 (${exp.attachments?.length || 0})</div>
            <div class="tab" data-tab="versions">🕘 版本历史</div>
            <div class="tab" data-tab="links">🔗 关联实验</div>
          </div>

          <div style="flex:1;overflow-y:auto;padding:16px">
            <div id="tab-structure" class="tab-content"></div>
            <div id="tab-reagents" class="tab-content" style="display:none"></div>
            <div id="tab-content" class="tab-content" style="display:none"></div>
            <div id="tab-attachments" class="tab-content" style="display:none"></div>
            <div id="tab-versions" class="tab-content" style="display:none"></div>
            <div id="tab-links" class="tab-content" style="display:none"></div>
          </div>

          <div style="padding:10px 20px;border-top:1px solid var(--border);display:flex;gap:8px;background:var(--bg-card)">
            <button class="btn btn-primary" id="btn-save-exp">💾 保存 (Ctrl+S)</button>
            <button class="btn btn-secondary" id="btn-export-md">导出Markdown</button>
            <button class="btn btn-secondary" id="btn-export-html">导出HTML</button>
            <button class="btn btn-secondary" id="btn-export-pdf">导出PDF</button>
            <button class="btn btn-secondary" id="btn-export-word">导出Word</button>
            <button class="btn btn-secondary" id="btn-gen-template">📑 生成模板</button>
            <div style="flex:1"></div>
            <button class="btn btn-danger btn-sm" id="btn-delete-exp">删除</button>
          </div>
        </div>
      `;

      // Tab switching
      document.querySelectorAll('.tab').forEach(tab => {
        tab.onclick = () => {
          document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
          document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
          tab.classList.add('active');
          document.getElementById(`tab-${tab.dataset.tab}`).style.display = 'block';
          if (tab.dataset.tab === 'content') this.updateContentEmbedded();
        };
      });

      // Save button
      document.getElementById('btn-save-exp').onclick = () => this.saveExperiment();
      document.getElementById('btn-export-md').onclick = () => this.exportExp('markdown');
      document.getElementById('btn-export-html').onclick = () => this.exportExp('html');
      document.getElementById('btn-export-pdf').onclick = () => this.exportExp('pdf');
      document.getElementById('btn-export-word').onclick = () => this.exportExp('word');
      document.getElementById('btn-gen-template').onclick = () => this.generateTemplateFromExp();
      document.getElementById('btn-delete-exp').onclick = () => this.deleteExperiment(id);

      // Render tabs
      this.renderContentTab(exp);
      this.renderStructureTab(exp);
      this.renderReagentsTab(exp);
      this.renderAttachmentsTab(exp);
      this.renderVersionsTab(exp);
      this.renderLinksTab(exp);
      // Fill the in-content reaction + reagent summary (state now populated by above renders)
      this.updateContentEmbedded();

    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
    }
  }
};

Object.assign(App, {
  showModal(title, bodyHtml, onConfirm = null, confirmText = '确定') {
    const root = document.getElementById('modal-root');
    root.innerHTML = `
      <div class="modal-overlay" id="modal-overlay">
        <div class="modal">
          <div class="modal-header">
            <h3>${title}</h3>
            <button class="modal-close" onclick="App.closeModal()">&times;</button>
          </div>
          <div class="modal-body">${bodyHtml}</div>
          ${onConfirm ? `<div class="modal-footer">
            <button class="btn btn-secondary" onclick="App.closeModal()">取消</button>
            <button class="btn btn-primary" id="modal-confirm">${confirmText}</button>
          </div>` : ''}
        </div>
      </div>
    `;
    document.getElementById('modal-overlay').onclick = (e) => {
      if (e.target.id === 'modal-overlay') this.closeModal();
    };
    if (onConfirm) {
      document.getElementById('modal-confirm').onclick = onConfirm;
    }
  },

  closeModal() {
    document.getElementById('modal-root').innerHTML = '';
  },

  _debounceTimer: null,
  debounce(id, fn) {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(fn, 300);
  },

  debounceSearch(inputId, fn) {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(fn, 300);
  }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', () => App.init());
