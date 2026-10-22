Object.assign(App, {
  openImportCompounds() {
    const el = document.getElementById('compound-import-file');
    if (el) el.click();
  },

  async handleImportCompounds(input) {
    const file = input.files[0];
    if (!file) return;
    try {
      const r = await API.importCompoundsExcel(file, this.state.compoundCategory || "project");
      this.toast(r.message || `导入 ${r.imported} 条`, 'success');
      input.value = '';
      this.renderCompounds();
    } catch (err) {
      this.toast(err.message, 'error');
      input.value = '';
    }
  },

  async exportCompounds() {
    try {
      const res = await API.exportCompoundsExcel();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `化合物库_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.toast('已导出Excel', 'success');
    } catch (e) { this.toast(e.message, 'error'); }
  },

  async batchDeleteCompounds() {
    const ids = Array.from(this.contentEl.querySelectorAll('.comp-check:checked')).map(c => parseInt(c.value, 10));
    if (!ids.length) return;
    if (!confirm(`确认删除选中的 ${ids.length} 个化合物？此操作不可撤销`)) return;
    try {
      const r = await API.batchDeleteCompounds(ids);
      this.toast(`已删除 ${r.deleted} 个化合物`, 'success');
      this.renderCompounds();
    } catch (err) { this.toast(err.message, 'error'); }
  },

  async viewCompound(id) {
    const c = await API.getCompound(id);
    let imgHtml = '';
    if (c.smiles) {
      try {
        const r = await API.renderStructure(c.smiles);
        if (r.image) imgHtml = `<img src="${r.image}" style="max-width:300px">`;
      } catch(e) {}
    }
    this.showModal('化合物详情', `
      <div style="display:flex;gap:20px">
        <div style="flex:1">
          <div class="structure-viewer" style="min-height:200px">${imgHtml || '<span class="placeholder">无结构式</span>'}</div>
        </div>
        <div style="flex:1;font-size:13px">
          <p><strong>名称:</strong> ${this.escape(c.name)}</p>
          <p><strong>CAS:</strong> ${this.escape(c.cas || '—')}</p>
          <p><strong>分子式:</strong> ${c.formula || '—'}</p>
          <p><strong>分子量:</strong> ${c.mw || '—'}</p>
          <p><strong>SMILES:</strong> <code style="font-size:11px">${this.escape(c.smiles || '')}</code></p>
          <p><strong>InChIKey:</strong> <code style="font-size:11px">${this.escape(c.inchikey || '')}</code></p>
          <p><strong>备注:</strong> ${this.escape(c.notes || '—')}</p>
        </div>
      </div>
    `);
  },

  async deleteCompound(id) {
    if (!confirm('删除此化合物？')) return;
    try { await API.deleteCompound(id); this.renderCompounds(); this.toast('已删除', 'success'); }
    catch(err) { this.toast(err.message, 'error'); }
  },

  async editCompound(id) {
    const c = await API.getCompound(id);
    this.showCompoundModal(c);
  },

  showAddCompoundModal() {
    const cat = this.state.compoundCategory;
    const defaultCat = (cat === 'solvent' || cat === 'reagent' || cat === 'project') ? cat : 'project';
    this.showCompoundModal(null, defaultCat);
  },

  showCompoundModal(compound = null, defaultCat = 'project') {
    const isEdit = !!compound;
    const c = compound || {};
    const catVal = c.category || defaultCat;
    const cats = [
      ['project', '项目化合物库'],
      ['solvent', '常用溶剂库'],
      ['reagent', '常用试剂库'],
    ];
    const catOpts = cats.map(([v, l]) => `<option value="${v}" ${catVal === v ? 'selected' : ''}>${l}</option>`).join('');
    this.showModal(isEdit ? '编辑化合物' : '添加化合物', `
      <div class="form-group"><label>名称</label><input type="text" class="form-input" id="comp-name" value="${this.escape(c.name || '')}" placeholder="如：乙醇"></div>
      <div class="form-group"><label>分类</label><select class="form-input" id="comp-category">${catOpts}</select></div>
      <div class="form-group"><label>CAS号</label><input type="text" class="form-input" id="comp-cas" value="${this.escape(c.cas || '')}" placeholder="如：64-17-5"></div>
      <div class="form-group"><label>SMILES</label><input type="text" class="form-input" id="comp-smiles" value="${this.escape(c.smiles || '')}" placeholder="如：CCO" style="font-family:monospace"></div>
      <div class="form-group"><label>备注</label><textarea class="form-textarea" id="comp-notes">${this.escape(c.notes || '')}</textarea></div>
      <div id="comp-preview" style="margin-top:8px"></div>
    `, async () => {
      const data = {
        name: document.getElementById('comp-name').value,
        category: document.getElementById('comp-category').value,
        cas: document.getElementById('comp-cas').value,
        smiles: document.getElementById('comp-smiles').value,
        notes: document.getElementById('comp-notes').value,
      };
      try {
        if (isEdit) {
          await API.updateCompound(c.id, data);
        } else {
          const r = await API.createCompound(data);
          // Backend rejected as duplicate — show why and offer to edit the existing entry
          if (r && r.duplicate) {
            const ex = r.existing || {};
            const catLabel = ({ solvent: '常用溶剂库', reagent: '常用试剂库', project: '项目化合物库' })[ex.category] || '化合物库';
            const casTxt = ex.cas ? `，CAS ${ex.cas}` : '';
            const head = r.reason === 'inchikey'
              ? `结构相同的化合物已存在于${catLabel}：\n「${ex.name}」${casTxt}`
              : `同名化合物已存在于${catLabel}：\n「${ex.name}」${casTxt}`;
            const go = confirm(`${head}\n\n点击「确定」查看并编辑该条目（可修改名称/分类等）；\n点击「取消」返回当前窗口修改输入。`);
            if (go) {
              this.closeModal();
              await this.editCompound(ex.id);
            }
            return;
          }
        }
        this.closeModal();
        this.renderCompounds();
        this.toast(isEdit ? '化合物已更新' : '化合物已添加', 'success');
      } catch (err) { this.toast(err.message, 'error'); }
    });

    // Live preview on SMILES blur
    document.getElementById('comp-smiles').onblur = async () => {
      const smiles = document.getElementById('comp-smiles').value;
      if (!smiles) return;
      const preview = document.getElementById('comp-preview');
      preview.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
      try {
        const r = await API.parseSmiles(smiles);
        if (r.valid) {
          preview.innerHTML = `<div class="form-row">
            <div class="form-group" style="flex:1">${r.image ? `<img src="data:image/png;base64,${r.image}" style="max-width:200px">` : ''}</div>
            <div class="form-group" style="flex:1;font-size:12px">
              <div>分子式: ${r.formula}</div><div>分子量: ${r.mw}</div>
              <div>InChIKey: <code style="font-size:10px">${r.inchikey}</code></div>
            </div>
          </div>`;
        }
      } catch(e) {}
    };
  },

  // --- Structure Search ---
  renderStructureSearch() {
    this.contentEl.innerHTML = `
      <div class="card">
        <div class="card-header"><h3>🔍 子结构检索</h3></div>
        <div class="card-body">
          <p style="color:var(--text-muted);margin-bottom:12px">输入SMILES进行子结构搜索，找到包含该结构的所有化合物</p>
          <div id="struct-search-editor"></div>
          <button class="btn btn-primary" id="btn-struct-search" style="margin-top:12px">搜索</button>
          <div id="struct-search-results" style="margin-top:16px"></div>
        </div>
      </div>
    `;
    this.structSearchEditor = new StructureEditor(document.getElementById('struct-search-editor'), {});
    document.getElementById('btn-struct-search').onclick = async () => {
      const smiles = this.structSearchEditor.getSmiles();
      if (!smiles) { this.toast('请先输入结构', 'error'); return; }
      const results = document.getElementById('struct-search-results');
      results.innerHTML = '<div class="loading"><div class="spinner"></div> 搜索中...</div>';
      try {
        const data = await API.substructureSearch(smiles);
        if (data.count === 0) {
          results.innerHTML = '<div class="empty-state"><p>未找到匹配的化合物</p></div>';
        } else {
          results.innerHTML = `<p style="margin-bottom:8px">找到 ${data.count} 个匹配化合物:</p>
            <table class="exp-table"><thead><tr><th>名称</th><th>SMILES</th><th>分子式</th><th>分子量</th></tr></thead><tbody>
            ${data.matches.map(c => `<tr><td>${this.escape(c.name)}</td><td><code style="font-size:11px">${this.escape(c.smiles)}</code></td><td>${c.formula}</td><td>${c.mw}</td></tr>`).join('')}
            </tbody></table>`;
        }
      } catch(err) { results.innerHTML = `<p style="color:var(--danger)">${err.message}</p>`; }
    };
  },

  // --- Templates ---
  async renderTemplates() {
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const data = await API.listTemplates();
      let html = `
        <div style="margin-bottom:12px">
          <button class="btn btn-primary btn-sm" onclick="App.showTemplateModal()">+ 新建模板</button>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px">
      `;
      for (const t of data.templates) {
        const typeNames = { reaction: '反应', workup: '后处理', crystallization: '结晶', custom: '自定义' };
        html += `<div class="card">
          <div class="card-header"><h3>${this.escape(t.name)}</h3><span class="status-badge status-draft" style="margin-left:auto">${typeNames[t.type]||t.type}</span></div>
          <div class="card-body" style="font-size:12px;color:var(--text-muted);max-height:100px;overflow:hidden">
            ${(t.content||'').replace(/<[^>]+>/g, ' ').substring(0, 100)}...
          </div>
          <div style="padding:8px 12px;border-top:1px solid var(--border);display:flex;gap:8px">
            <button class="btn btn-secondary btn-sm" onclick="App.editTemplate(${t.id})">编辑</button>
            <button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="App.deleteTemplate(${t.id})">删除</button>
          </div>
        </div>`;
      }
      html += '</div>';
      this.contentEl.innerHTML = html;
    } catch(err) { this.contentEl.innerHTML = `<p>${err.message}</p>`; }
  }
});
