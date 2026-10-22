Object.assign(App, {
  showTemplateModal(tpl = null) {
    const isEdit = !!tpl;
    this.showModal(isEdit ? '编辑模板' : '新建模板', `
      <div class="form-group"><label>模板名称</label><input type="text" class="form-input" id="tpl-name" value="${tpl ? this.escape(tpl.name) : ''}"></div>
      <div class="form-group"><label>类型</label><select class="form-select" id="tpl-type">
        <option value="reaction" ${tpl?.type==='reaction'?'selected':''}>反应</option>
        <option value="workup" ${tpl?.type==='workup'?'selected':''}>后处理</option>
        <option value="crystallization" ${tpl?.type==='crystallization'?'selected':''}>结晶</option>
        <option value="custom" ${tpl?.type==='custom'?'selected':''}>自定义</option>
      </select></div>
      <div class="form-group"><label>内容模板 (HTML)</label><textarea class="form-textarea" id="tpl-content" style="min-height:200px;font-family:monospace;font-size:12px">${tpl ? this.escape(tpl.content) : ''}</textarea></div>
      <p style="font-size:11px;color:var(--text-muted)">可使用HTML标签：&lt;h2&gt;标题&lt;/h2&gt; &lt;ol&gt;&lt;li&gt;步骤&lt;/li&gt;&lt;/ol&gt; 等</p>
    `, async () => {
      const data = {
        name: document.getElementById('tpl-name').value,
        type: document.getElementById('tpl-type').value,
        content: document.getElementById('tpl-content').value,
      };
      try {
        if (isEdit) await API.updateTemplate(tpl.id, data);
        else await API.createTemplate(data);
        this.closeModal();
        this.renderTemplates();
        this.toast(isEdit ? '已更新' : '已创建', 'success');
      } catch(err) { this.toast(err.message, 'error'); }
    });
  },

  async editTemplate(id) {
    const tpl = await API.getTemplate(id);
    this.showTemplateModal(tpl);
  },

  async deleteTemplate(id) {
    if (!confirm('删除此模板？')) return;
    await API.deleteTemplate(id);
    this.renderTemplates();
    this.toast('已删除', 'success');
  },

  // --- Tags ---
  async renderTags() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const data = await API.listTags();
      let html = '<div class="card"><div class="card-body">';
      html += '<div style="margin-bottom:12px;display:flex;gap:8px">';
      html += '<input type="text" class="form-input" id="new-tag-name" placeholder="标签名" style="width:200px">';
      html += '<input type="color" id="new-tag-color" value="#4a90d9" style="width:40px;height:34px;border:1px solid var(--border);border-radius:4px;cursor:pointer">';
      html += '<button class="btn btn-primary btn-sm" onclick="App.createTag()">添加标签</button>';
      html += '</div>';
      html += '<div style="display:flex;flex-wrap:wrap;gap:8px">';
      for (const t of data.tags) {
        html += `<span class="tag" style="background:${t.color};font-size:13px;padding:4px 12px">
          ${this.escape(t.name)} (${t.exp_count})
          <button onclick="App.deleteTag(${t.id})" style="background:none;border:none;color:#fff;cursor:pointer;margin-left:4px">✕</button>
        </span>`;
      }
      html += '</div></div></div>';
      this.contentEl.innerHTML = html;
    } catch(err) { this.contentEl.innerHTML = `<p>${err.message}</p>`; }
  },

  async createTag() {
    const name = document.getElementById('new-tag-name').value;
    const color = document.getElementById('new-tag-color').value;
    if (!name) { this.toast('请输入标签名', 'error'); return; }
    try {
      await API.createTag({ name, color });
      this.renderTags();
      this.toast('标签已创建', 'success');
    } catch(err) { this.toast(err.message, 'error'); }
  },

  async deleteTag(id) {
    if (!confirm('删除此标签？')) return;
    // No direct API — tags are removed via experiment associations
    // For now, delete via SQL would need a dedicated endpoint
    this.toast('请从实验中移除标签后再删除', 'info');
  },

  // --- Data Import/Export ---
  renderData() {
    this.contentEl.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="card">
          <div class="card-header"><h3>📤 导出</h3></div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
            <button class="btn btn-secondary" onclick="App.exportAllExcel()">导出实验列表 (Excel)</button>
            <button class="btn btn-secondary" onclick="App.exportAllJSON()">导出全库 (JSON)</button>
            <p style="font-size:12px;color:var(--text-muted);margin-top:8px">
              Excel导出包含实验列表和投料表两个工作表。<br>
              JSON导出包含所有数据，可用于迁移或备份。
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>📥 导入</h3></div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
            <div>
              <label style="font-size:12px;font-weight:600;color:var(--text-muted)">从CSV导入实验</label>
              <input type="file" id="import-csv" accept=".csv" style="margin-top:4px">
            </div>
            <div>
              <label style="font-size:12px;font-weight:600;color:var(--text-muted)">从JSON导入（全库恢复）</label>
              <input type="file" id="import-json" accept=".json" style="margin-top:4px">
            </div>
            <p style="font-size:12px;color:var(--text-muted);margin-top:8px">
              CSV文件需包含列标题：title,project,status,exp_date,target_compound,yield_pct,purity_pct,content<br>
              JSON导入会合并数据，不会覆盖已有记录。
            </p>
          </div>
        </div>
      </div>
    `;

    document.getElementById('import-csv').onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const r = await API.importCSV(file);
        this.toast(`已导入 ${r.imported} 条记录`, 'success');
      } catch(err) { this.toast('导入失败: ' + err.message, 'error'); }
    };
    document.getElementById('import-json').onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (!confirm('导入JSON将合并数据到当前数据库，是否继续？')) return;
      try {
        const r = await API.importJSON(file);
        let msg = '导入完成: ';
        for (const [table, count] of Object.entries(r.tables)) {
          msg += `${table}=${count} `;
        }
        this.toast(msg, 'success');
      } catch(err) { this.toast('导入失败: ' + err.message, 'error'); }
    };
  },

  async exportAllExcel() {
    try {
      const res = await API.exportExcel('');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `experiments_${new Date().toISOString().slice(0,10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      this.toast('已导出Excel', 'success');
    } catch(err) { this.toast(err.message, 'error'); }
  },

  async exportAllJSON() {
    try {
      const res = await API.exportJSON();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chemeln_export_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.toast('已导出JSON', 'success');
    } catch(err) { this.toast(err.message, 'error'); }
  },

  // --- Backup ---
  async renderBackup() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    let cfg = { enabled: true, interval_hours: 24, keep: 7, last_backup_at: '', backups: [] };
    try {
      cfg = await API.getBackupSettings();
    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
      return;
    }
    const hOpts = [6, 12, 24, 48, 72];
    const kOpts = [3, 5, 7, 14, 30];
    this.contentEl.innerHTML = `
      <div class="card">
        <div class="card-header"><h3>🔒 自动备份</h3></div>
        <div class="card-body">
          <p style="color:var(--text-muted);margin-bottom:14px">
            服务运行期间自动把<strong>数据库与附件</strong>打包备份为一个 zip 文件（解压覆盖 <code>data/</code> 目录即可恢复）。
          </p>
          <div style="display:flex;gap:20px;flex-wrap:wrap;align-items:flex-end">
            <label style="display:flex;align-items:center;gap:6px;font-size:13px">
              <input type="checkbox" id="bk-enabled" ${cfg.enabled ? 'checked' : ''}> 启用自动备份
            </label>
            <div class="meta-field">
              <label>备份间隔</label>
              <select id="bk-interval">
                ${hOpts.map(h => `<option value="${h}" ${cfg.interval_hours === h ? 'selected' : ''}>每 ${h} 小时</option>`).join('')}
              </select>
            </div>
            <div class="meta-field">
              <label>保留份数</label>
              <select id="bk-keep">
                ${kOpts.map(k => `<option value="${k}" ${cfg.keep === k ? 'selected' : ''}>${k} 份</option>`).join('')}
              </select>
            </div>
            <button class="btn btn-primary btn-sm" onclick="App.saveBackupSettings()">保存设置</button>
            <button class="btn btn-secondary btn-sm" onclick="App.runBackupNow()">💾 立即备份</button>
          </div>
          <div style="margin-top:14px;font-size:12px;color:var(--text-muted)">
            上次备份：<strong>${cfg.last_backup_at || '暂无'}</strong>
            · 自动备份保留最近 ${cfg.keep} 份（超出自动清理旧文件）
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:16px">
        <div class="card-header"><h3>📦 备份文件（共 ${(cfg.backups || []).length} 个）</h3></div>
        <div class="card-body" style="padding:0;overflow-x:auto">
          ${this.renderBackupTable(cfg.backups || [])}
        </div>
      </div>

      <div class="card" style="margin-top:16px">
        <div class="card-header"><h3>⚠️ 数据安全提示</h3></div>
        <div class="card-body">
          <p style="font-size:13px;color:var(--text-muted);margin:0">
            备份文件保存在本机 <code>data/backups/</code>。建议定期把备份文件<strong>复制到U盘或网盘</strong>——
            本机磁盘损坏时，本地备份无法挽救数据。
          </p>
        </div>
      </div>
    `;
  },

  renderBackupTable(backups) {
    if (!backups.length) {
      return '<div class="empty-state" style="padding:30px"><p>还没有备份文件</p></div>';
    }
    const tagNames = { auto: '自动', manual: '手动', 'manual-db': '手动(SQLite)' };
    let html = `<table class="exp-table"><thead><tr>
      <th>文件名</th><th>类型</th><th>时间</th><th>大小</th><th style="width:100px">操作</th>
    </tr></thead><tbody>`;
    for (const b of backups) {
      const size = b.size > 1024 * 1024
        ? (b.size / 1024 / 1024).toFixed(1) + ' MB'
        : Math.round(b.size / 1024) + ' KB';
      html += `<tr>
        <td style="font-family:monospace;font-size:12px">${this.escape(b.name)}</td>
        <td>${tagNames[b.tag] || b.tag}</td>
        <td style="color:var(--text-muted);font-size:12px">${b.created_at}</td>
        <td>${size}</td>
        <td><a class="btn btn-ghost btn-sm" href="/api/data/backup/download/${encodeURIComponent(b.name)}" download>下载</a></td>
      </tr>`;
    }
    html += '</tbody></table>';
    return html;
  },

  async saveBackupSettings() {
    const enabled = document.getElementById('bk-enabled').checked;
    const interval_hours = parseInt(document.getElementById('bk-interval').value, 10);
    const keep = parseInt(document.getElementById('bk-keep').value, 10);
    try {
      await API.updateBackupSettings({ enabled, interval_hours, keep });
      this.toast('自动备份设置已保存', 'success');
      this.renderBackup();
    } catch (err) { this.toast('保存失败: ' + err.message, 'error'); }
  },

  async runBackupNow() {
    this.toast('正在备份...', 'info');
    try {
      const info = await API.runBackupNow();
      const size = info.size > 1024 * 1024
        ? (info.size / 1024 / 1024).toFixed(1) + ' MB'
        : Math.round(info.size / 1024) + ' KB';
      this.toast(`备份完成：${info.name}（${size}，含 ${info.attachments} 个附件）`, 'success');
      this.renderBackup();
    } catch (err) { this.toast('备份失败: ' + err.message, 'error'); }
  },

  async createBackup() {
    this.toast('正在创建备份...', 'info');
    try {
      const res = await API.backupDatabase();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chemeln_backup_${new Date().toISOString().slice(0,10)}.db`;
      a.click();
      URL.revokeObjectURL(url);
      this.toast('备份已创建并下载', 'success');
      this.renderBackup();
    } catch(err) { this.toast('备份失败: ' + err.message, 'error'); }
  },

  async downloadBackup() { this.createBackup(); },

  // --- New Experiment Modal ---
  async showNewExpModal() {
    const tpls = await API.listTemplates();
    const tplOptions = tpls.templates.map(t => `<option value="${t.id}">${this.escape(t.name)}</option>`).join('');

    this.showModal('新建实验', `
      <div class="form-group"><label>标题</label><input type="text" class="form-input" id="new-title" placeholder="如：Suzuki偶联反应优化" autofocus></div>
      <div class="form-row">
        <div class="form-group"><label>项目</label><input type="text" class="form-input" id="new-project" placeholder="如：项目A"></div>
        <div class="form-group"><label>状态</label><select class="form-select" id="new-status">
          <option value="draft">草稿</option>
          <option value="ongoing">进行中</option>
          <option value="completed">已完成</option>
          <option value="archived">已归档</option>
        </select></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>日期</label><input type="date" class="form-input" id="new-date" value="${new Date().toISOString().slice(0,10)}"></div>
        <div class="form-group"><label>目标化合物</label><input type="text" class="form-input" id="new-target" placeholder="如：化合物X-1"></div>
      </div>
      <div class="form-group"><label>使用模板</label><select class="form-select" id="new-template">
        <option value="">不使用模板</option>
        ${tplOptions}
      </select></div>
    `, async () => {
      const data = {
        title: document.getElementById('new-title').value || '未命名实验',
        project: document.getElementById('new-project').value,
        status: document.getElementById('new-status').value,
        exp_date: document.getElementById('new-date').value,
        target_compound: document.getElementById('new-target').value,
        template_id: document.getElementById('new-template').value ? parseInt(document.getElementById('new-template').value) : null,
      };
      try {
        const r = await API.createExperiment(data);
        this.closeModal();
        this.openExperiment(r.id);
        this.toast('实验已创建', 'success');
      } catch(err) { this.toast(err.message, 'error'); }
    });
  },

  // --- Search Results ---
  async renderSearchResults() {
    const q = this.state.searchQuery;
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 搜索中...</div>';
    try {
      const data = await API.fulltextSearch(q);
      let html = `<p style="margin-bottom:12px">搜索 "<strong>${this.escape(q)}</strong>" — 找到 ${data.count} 条结果</p>`;
      if (data.count === 0) {
        html += '<div class="empty-state"><div class="icon">🔍</div><p>未找到匹配的实验</p></div>';
      } else {
        html += '<div class="card"><div class="card-body" style="padding:0">';
        for (const r of data.results) {
          html += `<div style="padding:12px;border-bottom:1px solid var(--border);cursor:pointer" onclick="App.openExperiment(${r.id})">
            <div style="font-weight:500">${this.escape(r.title)}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${r.snippet || ''}</div>
            <div style="font-size:11px;color:var(--text-light);margin-top:4px">${r.project || ''} · ${r.updated_at || ''}</div>
          </div>`;
        }
        html += '</div></div>';
      }
      this.contentEl.innerHTML = html;
    } catch(err) { this.contentEl.innerHTML = `<p>${err.message}</p>`; }
  },

  // --- Filters ---
  updateFilter(key, value) {
    if (value === '') {
      delete this.state.filters[key];
    } else {
      this.state.filters[key] = value;
    }
    this.renderExperiments();
  },

  clearFilters() {
    this.state.filters = {};
    this.renderExperiments();
  },

  sortBy(field) {
    if (this.state.sortField === field) {
      this.state.sortOrder = this.state.sortOrder === 'desc' ? 'asc' : 'desc';
    } else {
      this.state.sortField = field;
      this.state.sortOrder = 'desc';
    }
    this.state.filters.sort = this.state.sortField;
    this.state.filters.order = this.state.sortOrder;
    this.renderExperiments();
  },

  async loadTags() {
    try {
      const data = await API.listTags();
      this.state.tags = data.tags;
    } catch(e) {}
  },

  // --- Utilities ---
  escape(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },

  toast(msg, type = 'info') {
    const container = document.getElementById('toasts');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(100%)'; setTimeout(() => el.remove(), 300); }, 3000);
  }
});
