/**
 * ChemELN API Client — all backend communication.
 *
 * 鉴权说明（2026-10-22 安全加固）：
 *   后端现在要求会话令牌（X-ChemLab-Token 头；旧名 X-ChemELN-Token 仍兼容）。
 *   浏览器首次加载页面时后端会下发 HttpOnly cookie，正常浏览无需额外处理；
 *   但 Tauri 子 webview / 脚本调用等场景拿不到 cookie，
 *   因此这里做一次「令牌引导」：从 /api/session 取令牌并缓存，
 *   之后所有请求都带上 header。cookie 与 header 任一有效即放行。
 */
const API = {
  base: '',
  _token: null,        // 会话令牌缓存
  _tokenPromise: null, // 并发时只引导一次

  /** 取会话令牌（带缓存，失败时降级为 cookie 模式） */
  async ensureToken() {
    if (this._token) return this._token;
    if (!this._tokenPromise) {
      this._tokenPromise = fetch('/api/session', { credentials: 'same-origin' })
        .then(r => (r.ok ? r.json() : null))
        .then(j => {
          if (j && j.token) this._token = j.token;
          return this._token;
        })
        .catch(() => null)
        .finally(() => { this._tokenPromise = null; });
    }
    return this._tokenPromise;
  },

  async request(method, path, body = null, isForm = false) {
    const opts = { method, headers: {} };

    // 带令牌（若引导成功）；失败时后端会回退到 cookie 校验
    const token = await this.ensureToken();
    if (token) opts.headers['X-ChemLab-Token'] = token;

    if (body !== null) {
      if (isForm) {
        opts.body = body; // FormData
      } else {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      }
    }
    const res = await fetch(path, opts);
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      return data;
    }
    if (ct.includes('text/') || ct.includes('application/octet-stream')) {
      return res;
    }
    return res;
  },

  // Experiments
  listExperiments(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request('GET', `/api/experiments${qs ? '?' + qs : ''}`);
  },
  getExperiment(id) {
    return this.request('GET', `/api/experiments/${id}`);
  },
  createExperiment(data) {
    return this.request('POST', '/api/experiments', data);
  },
  updateExperiment(id, data) {
    return this.request('PUT', `/api/experiments/${id}`, data);
  },
  deleteExperiment(id) {
    return this.request('DELETE', `/api/experiments/${id}`);
  },
  addTag(expId, tagId) {
    return this.request('POST', `/api/experiments/${expId}/tags/${tagId}`);
  },
  removeTag(expId, tagId) {
    return this.request('DELETE', `/api/experiments/${expId}/tags/${tagId}`);
  },
  updateReagents(expId, reagents) {
    return this.request('PUT', `/api/experiments/${expId}/reagents`, reagents);
  },
  calculateReagents(expId, data) {
    return this.request('POST', `/api/experiments/${expId}/calculate-reagents`, data);
  },
  getReaction(expId) {
    return this.request('GET', `/api/experiments/${expId}/reaction`);
  },
  saveReaction(expId, data) {
    return this.request('PUT', `/api/experiments/${expId}/reaction`, data);
  },
  async uploadReactionImage(expId, file) {
    const fd = new FormData();
    fd.append('file', file);
    return this.request('POST', `/api/experiments/${expId}/reaction-image`, fd, true);
  },
  async uploadAttachment(expId, file, description = '', fileType = '') {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('description', description);
    fd.append('file_type', fileType);
    return this.request('POST', `/api/experiments/${expId}/attachments`, fd, true);
  },
  deleteAttachment(expId, attId) {
    return this.request('DELETE', `/api/experiments/${expId}/attachments/${attId}`);
  },
  getVersion(expId, verId) {
    return this.request('GET', `/api/experiments/${expId}/versions/${verId}`);
  },
  restoreVersion(expId, verId) {
    return this.request('POST', `/api/experiments/${expId}/versions/${verId}/restore`);
  },
  addLink(expId, toExp, linkType = 'related') {
    return this.request('POST', `/api/experiments/${expId}/links/${toExp}?link_type=${linkType}`);
  },
  removeLink(expId, toExp, linkType = 'related') {
    return this.request('DELETE', `/api/experiments/${expId}/links/${toExp}?link_type=${linkType}`);
  },

  // Compounds
  listCompounds(q = '', category = '') {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (category && category !== 'all') params.set('category', category);
    const qs = params.toString();
    return this.request('GET', `/api/compounds${qs ? '?' + qs : ''}`);
  },
  getCompound(id) {
    return this.request('GET', `/api/compounds/${id}`);
  },
  createCompound(data) {
    return this.request('POST', '/api/compounds', data);
  },
  updateCompound(id, data) {
    return this.request('PUT', `/api/compounds/${id}`, data);
  },
  deleteCompound(id) {
    return this.request('DELETE', `/api/compounds/${id}`);
  },
  parseSmiles(smiles) {
    return this.request('POST', '/api/compounds/parse-smiles', { smiles });
  },
  parseMolfile(molfile) {
    return this.request('POST', '/api/compounds/parse-molfile', { molfile });
  },
  renderStructure(smiles) {
    return this.request('POST', '/api/compounds/render', { smiles });
  },
  substructureSearch(smiles) {
    return this.request('POST', '/api/compounds/substructure-search', { smiles });
  },
  lookupMw(name) {
    return this.request('POST', '/api/compounds/lookup-mw', { name });
  },
  importCompoundsExcel(file, defaultCategory = "project") {
    const fd = new FormData();
    fd.append('file', file);
    if (defaultCategory && defaultCategory !== 'all') {
      fd.append('default_category', defaultCategory);
    }
    return this.request('POST', '/api/compounds/import-excel', fd, true);
  },
  exportCompoundsExcel() {
    return this.request('GET', '/api/compounds/export-excel');
  },
  batchDeleteCompounds(ids) {
    return this.request('POST', '/api/compounds/batch-delete', { ids });
  },

  // Templates
  listTemplates(typeFilter = '') {
    const qs = typeFilter ? `?type_filter=${typeFilter}` : '';
    return this.request('GET', `/api/templates${qs}`);
  },
  getTemplate(id) {
    return this.request('GET', `/api/templates/${id}`);
  },
  createTemplate(data) {
    return this.request('POST', '/api/templates', data);
  },
  updateTemplate(id, data) {
    return this.request('PUT', `/api/templates/${id}`, data);
  },
  deleteTemplate(id) {
    return this.request('DELETE', `/api/templates/${id}`);
  },

  // Search
  fulltextSearch(q) {
    return this.request('GET', `/api/search/fulltext?q=${encodeURIComponent(q)}`);
  },
  advancedSearch(params) {
    const qs = new URLSearchParams(params).toString();
    return this.request('GET', `/api/search/advanced?${qs}`);
  },
  listTags() {
    return this.request('GET', '/api/search/tags');
  },
  createTag(data) {
    return this.request('POST', '/api/search/tags', data);
  },
  listProjects() {
    return this.request('GET', '/api/search/projects');
  },
  getStats() {
    return this.request('GET', '/api/search/stats');
  },

  // Data I/O
  exportMarkdown(expId) {
    return this.request('GET', `/api/data/export/experiment/${expId}/markdown`);
  },
  exportHTML(expId) {
    return this.request('GET', `/api/data/export/experiment/${expId}/html`);
  },
  exportPDF(expId) {
    return this.request('GET', `/api/data/export/experiment/${expId}/pdf`);
  },
  exportWord(expId) {
    return this.request('GET', `/api/data/export/experiment/${expId}/docx`);
  },
  exportExcel(ids = '') {
    return this.request('GET', `/api/data/export/experiments/excel?ids=${ids}`);
  },
  exportJSON() {
    return this.request('GET', '/api/data/export/all/json');
  },

  // Backup (auto-backup settings + manual run + history)
  getBackupSettings() {
    return this.request('GET', '/api/data/backup/settings');
  },
  updateBackupSettings(data) {
    return this.request('PUT', '/api/data/backup/settings', data);
  },
  runBackupNow() {
    return this.request('POST', '/api/data/backup/run');
  },
  listBackups() {
    return this.request('GET', '/api/data/backup/list');
  },
  backupDatabase() {
    return this.request('GET', '/api/data/backup/database');
  },
  async importCSV(file, table = 'experiments') {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('table', table);
    return this.request('POST', '/api/data/import/csv', fd, true);
  },
  async importJSON(file) {
    const fd = new FormData();
    fd.append('file', file);
    return this.request('POST', '/api/data/import/json', fd, true);
  },
};
