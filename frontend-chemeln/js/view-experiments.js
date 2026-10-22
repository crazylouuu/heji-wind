Object.assign(App, {
  renderContentTab(exp) {
    const container = document.getElementById('tab-content');
    // Auto-embedded blocks: reaction equation preview + reagent summary, in order.
    container.innerHTML = `
      <div class="content-embed">
        <div class="card">
          <div class="card-header"><h3>🧬 反应方程式预览</h3></div>
          <div class="card-body" id="content-rxn-preview"><span class="placeholder">加载中...</span></div>
        </div>
        <div class="card" style="margin-top:14px">
          <div class="card-header"><h3>📊 投料表汇总</h3></div>
          <div class="card-body" id="content-reagent-summary"><span class="placeholder">加载中...</span></div>
        </div>
        <div style="display:flex;gap:8px;margin:14px 0;flex-wrap:wrap;align-items:center">
          <button class="btn btn-secondary btn-sm" id="btn-insert-rxn-reagent" onclick="App.insertReactionReagentToContent()">📥 插入反应与投料表到正文</button>
          <button class="btn btn-danger btn-sm" id="btn-remove-rxn-reagent" onclick="App.removeReactionReagentFromContent()">🗑️ 删除已插入的</button>
          <span style="font-size:11px;color:var(--text-muted)">编辑「反应与结构」「投料表」后切回本页自动刷新；或点此将其固定到实验记录正文（用于导出/归档）。</span>
        </div>
      </div>
      <div id="editor-host"></div>
    `;
    this.editor = new RichEditor(document.getElementById('editor-host'), {
      onChange: (html) => { this.state.editorContent = html; },
      onSave: () => this.saveExperiment(),
      onInsertPdf: (file) => this.uploadPdfToEditor(file),
    });
    this.editor.setHTML(exp.content || '');
  },

  // Build a read-only reagent summary table HTML (used in content embed + template generation)
  renderReagentSummaryHTML(reagents) {
    const rs = reagents || [];
    if (!rs.length) return '<span class="placeholder">尚未添加投料</span>';
    const roleNames = { substrate: '原料', reagent: '试剂', solvent: '溶剂', product: '产物' };
    const rows = rs.map((r, i) => {
      // 投料比展示：原料=基准；当量比=N.NN eq；重量比=N.NN wt
      let ratio = '基准';
      if (r.role !== 'substrate') {
        const rv = r.ratio_value != null ? r.ratio_value : r.equivalents;
        if (rv != null) {
          ratio = (r.ratio_type === 'weight' ? `${rv} wt` : `${rv} eq`);
        } else {
          ratio = '—';
        }
      }
      // 投料质量(g)/摩尔(mmol)/体积(mL) 按显示位数规则格式化（见 format.js）
      //   数值 <0 → 3 位小数 ｜ 0 ≤ 数值 < 10 → 2 位 ｜ ≥10 → 1 位
      // state 与化学计量计算仍是完整精度，这里只改显示。
      const mass = r.mass_g != null ? r.mass_g : (r.mass_mg != null ? r.mass_mg / 1000 : null);
      const mol = r.ratio_type === 'weight' ? null : r.moles_mmol;
      const vol = r.ratio_type === 'weight' ? null : r.volume_ml;
      const massText = Fmt.qty(mass);
      const molText = Fmt.qty(mol);
      const volText = Fmt.qty(vol);
      return `<tr>
      <td>${i + 1}</td>
      <td style="font-weight:500">${this.escape(r.name || '')}</td>
      <td>${roleNames[r.role] || r.role || ''}</td>
      <td>${r.mw != null ? r.mw : '—'}</td>
      <td>${ratio}</td>
      <td>${massText != null ? massText : '—'}</td>
      <td>${molText != null ? molText : '—'}</td>
      <td>${volText != null ? volText : '—'}</td>
    </tr>`;
    }).join('');
    return `<div style="overflow-x:auto"><table class="reagent-table reagent-summary">
      <thead><tr><th>#</th><th>名称</th><th>角色</th><th>MW</th><th>投料比</th><th>投料质量(g)</th><th>摩尔(mmol)</th><th>体积(mL)</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  },

  renderReagentSummary(container, reagents) {
    if (!container) return;
    container.innerHTML = this.renderReagentSummaryHTML(reagents);
  },

  // Refresh the in-content reaction + reagent summary from current state (called on tab switch / load)
  async updateContentEmbedded() {
    const rxnBox = document.getElementById('content-rxn-preview');
    const rgBox = document.getElementById('content-reagent-summary');
    if (!rxnBox && !rgBox) return;
    const rd = this.state.reactionData;
    if (rxnBox) {
      if (rd) rxnBox.innerHTML = await this.renderReactionEquationHTML(rd);
      else rxnBox.innerHTML = '<span class="placeholder">尚未设置反应方程式</span>';
    }
    if (rgBox) {
      const reagents = (this.reagentTable && this.reagentTable.getReagents())
        || this.state.reagents || (this.state.currentExp && this.state.currentExp.reagents) || [];
      this.renderReagentSummary(rgBox, reagents);
    }
  },

  renderStructureTab(exp) {
    const container = document.getElementById('tab-structure');
    const rxn = exp.reaction || null;
    const mode = rxn?.display_mode || 'scheme';

    container.innerHTML = `
      <div class="card">
        <div class="card-header"><h3>🖼️ 反应图片</h3></div>
        <div class="card-body">
          <div style="display:flex;gap:12px;align-items:center;margin-bottom:10px">
            <input type="file" id="rxn-img-file" accept="image/*" style="display:none" onchange="App.handleReactionImage(this)">
            <button class="btn btn-primary btn-sm" onclick="document.getElementById('rxn-img-file').click()">📤 上传反应路线图</button>
            <span style="color:var(--text-muted);font-size:12px">支持 PNG/JPG 格式</span>
          </div>
          <div id="rxn-img-preview" class="structure-viewer" style="min-height:200px">
            ${rxn?.image_path ? `<img src="/attachments/${rxn.image_path}" alt="reaction">` : '<span class="placeholder">尚未上传反应图片</span>'}
          </div>
        </div>
      </div>


      <div class="card" style="margin-top:16px">
        <div class="card-header"><h3>🧬 目标化合物信息</h3></div>
        <div class="card-body">
          ${exp.compound ? `
            <div style="display:flex;gap:20px;flex-wrap:wrap">
              <div><strong>名称:</strong> ${this.escape(exp.compound.name)}</div>
              <div><strong>CAS:</strong> ${this.escape(exp.compound.cas || '—')}</div>
              <div><strong>分子式:</strong> ${exp.compound.formula || '—'}</div>
              <div><strong>分子量:</strong> ${exp.compound.mw || '—'}</div>
              <div><strong>SMILES:</strong> <code style="font-size:11px">${this.escape(exp.compound.smiles || '')}</code></div>
            </div>
          ` : '<p style="color:var(--text-muted)">尚未关联目标化合物。可在「实验内容」中用化合物库关联。</p>'}
        </div>
      </div>
    `;

    // Init state — normalize legacy string[] into object[] {name,smiles,mw,formula}
    this.state.reactionData = {
      mode,
      reactants: [],
      products: [],
      conditions: rxn?.conditions || '',
      arrow_label: rxn?.arrow_label || '',
      notes: rxn?.notes || '',
      image_path: rxn?.image_path || '',
    };
  },





  // 返回反应路线图 HTML（当前仅图片模式）
  async renderReactionEquationHTML(rd) {
    if (!rd) return '<span class="placeholder">尚未设置反应路线图</span>';
    if (rd.image_path) return `<div class="structure-viewer"><img src="/attachments/${rd.image_path}" alt="reaction" style="max-width:100%"></div>`;
    return '<span class="placeholder">尚未上传反应路线图</span>';
  },




  async handleReactionImage(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const preview = document.getElementById('rxn-img-preview');
    preview.innerHTML = '<div class="spinner"></div>';
    try {
      const res = await API.uploadReactionImage(this.state.currentExpId, file);
      this.state.reactionData.image_path = res.image_path;
      preview.innerHTML = `<img src="${res.url}" alt="reaction">`;
      this.toast('图片已上传', 'success');
    } catch (err) {
      preview.innerHTML = '<span class="placeholder" style="color:var(--danger)">上传失败</span>';
      this.toast('上传失败: ' + err.message, 'error');
    }
  },


  renderReagentsTab(exp) {
    const container = document.getElementById('tab-reagents');
    this.reagentTable = new ReagentTable(container, {
      onChange: (reagents) => { this.state.reagents = reagents; },
    });
    this.reagentTable.setReagents(exp.reagents || []);

    // If compound has MW, set as substrate
    if (exp.compound?.mw) {
      const substrate = (exp.reagents || []).find(r => r.role === 'substrate');
      if (substrate) {
        const subMass = substrate.mass_g != null ? substrate.mass_g
          : (substrate.mass_mg != null ? substrate.mass_mg / 1000 : null);
        if (subMass) {
          this.reagentTable.setSubstrate(subMass, exp.compound.mw);
        }
      }
    }
  },

  renderAttachmentsTab(exp) {
    const container = document.getElementById('tab-attachments');
    const atts = exp.attachments || [];

    let html = `
      <div style="margin-bottom:12px">
        <input type="file" id="att-upload" style="display:none" multiple>
        <button class="btn btn-primary btn-sm" onclick="document.getElementById('att-upload').click()">📎 上传附件</button>
        <span style="margin-left:8px;color:var(--text-muted);font-size:12px">支持图片、PDF、HPLC/NMR数据文件</span>
      </div>
      <div class="attachment-list">
    `;

    const fileIcons = { image: '🖼️', pdf: '📄', data: '📊', hplc: '📈', nmr: '🎼', other: '📎', archive: '🗜️' };

    if (atts.length === 0) {
      html += '<div class="empty-state" style="padding:30px"><p>暂无附件</p></div>';
    } else {
      for (const a of atts) {
        const icon = fileIcons[a.file_type] || '📎';
        const size = a.file_size ? (a.file_size > 1024*1024 ? (a.file_size/1024/1024).toFixed(1)+'MB' : Math.round(a.file_size/1024)+'KB') : '';
        const isImage = a.file_type === 'image';
        const isPdf = a.file_type === 'pdf';
        html += `<div class="attachment-item">
          <span class="file-icon">${icon}</span>
          <span class="file-name">${this.escape(a.filename)}</span>
          <span class="file-meta">${size} · ${a.file_type}</span>
          ${a.description ? `<span class="file-meta">"${this.escape(a.description)}"</span>` : ''}
          <a href="/attachments/${a.file_path}" target="_blank" class="btn btn-ghost btn-sm">查看</a>
          ${isImage ? `<button class="btn btn-ghost btn-sm" onclick="App.insertImageToEditor(${JSON.stringify(a.file_path)})">插入正文</button>` : ''}
          ${isPdf ? `<button class="btn btn-ghost btn-sm" onclick="App.insertPdfToEditor(${exp.id}, ${JSON.stringify(a.file_path)}, ${JSON.stringify(a.filename)}, ${a.id})">插入正文</button>` : ''}
          <button class="btn btn-ghost btn-sm" onclick="App.deleteAttachment(${exp.id}, ${a.id})" style="color:var(--danger)">删除</button>
        </div>`;
      }
    }
    html += '</div>';

    container.innerHTML = html;

    document.getElementById('att-upload').onchange = async (e) => {
      for (const file of e.target.files) {
        try {
          await API.uploadAttachment(exp.id, file);
          this.toast(`已上传: ${file.name}`, 'success');
        } catch (err) {
          this.toast(`上传失败: ${file.name}`, 'error');
        }
      }
      // Refresh
      this.state.currentExp = await API.getExperiment(exp.id);
      this.renderAttachmentsTab(this.state.currentExp);
    };
  },

  renderVersionsTab(exp) {
    const container = document.getElementById('tab-versions');
    const versions = exp.versions || [];
    let html = '<div class="card"><div class="card-body">';
    if (versions.length === 0) {
      html += '<div class="empty-state" style="padding:30px"><p>暂无版本历史</p><p style="font-size:12px">每次保存实验时自动创建版本快照</p></div>';
    } else {
      html += '<table class="exp-table"><thead><tr><th>ID</th><th>备注</th><th>时间</th><th>操作</th></tr></thead><tbody>';
      for (const v of versions) {
        html += `<tr>
          <td>#${v.id}</td>
          <td>${this.escape(v.version_note || '自动保存')}</td>
          <td style="color:var(--text-muted)">${v.created_at}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="App.viewVersion(${exp.id}, ${v.id})">查看</button>
            <button class="btn btn-ghost btn-sm" onclick="App.restoreVersion(${exp.id}, ${v.id})">恢复</button>
          </td>
        </tr>`;
      }
      html += '</tbody></table>';
    }
    html += '</div></div>';
    container.innerHTML = html;
  },

  async viewVersion(expId, verId) {
    const ver = await API.getVersion(expId, verId);
    this.showModal('版本内容 #' + verId, `
      <div style="max-height:500px;overflow-y:auto;border:1px solid var(--border);padding:16px;border-radius:4px;background:#fff">
        ${ver.content || '<p style="color:var(--text-muted)">（此版本无文字内容）</p>'}
      </div>
      ${ver.reagents_json && ver.reagents_json !== '[]' ? '<p style="margin-top:12px">此版本包含投料表快照</p>' : ''}
      <div style="margin-top:16px;display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" onclick="App.restoreVersion(${expId}, ${verId})">恢复此版本</button>
      </div>
    `);
  },

  async restoreVersion(expId, verId) {
    if (!confirm('确定恢复到此版本？当前内容将自动保存为新版本。')) return;
    try {
      await API.restoreVersion(expId, verId);
      this.toast('版本已恢复', 'success');
      this.renderExperimentDetail();
    } catch (err) {
      this.toast('恢复失败: ' + err.message, 'error');
    }
  },

  renderLinksTab(exp) {
    const container = document.getElementById('tab-links');
    const links = exp.links || [];
    let html = `
      <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
        <input type="text" id="link-target" placeholder="关联实验ID" style="width:120px;padding:5px 8px;border:1px solid var(--border-dark);border-radius:4px">
        <select id="link-type" style="padding:5px 8px;border:1px solid var(--border-dark);border-radius:4px">
          <option value="related">相关</option>
          <option value="predecessor">前序实验</option>
          <option value="followup">后续实验</option>
        </select>
        <button class="btn btn-primary btn-sm" onclick="App.addLink(${exp.id})">添加关联</button>
      </div>
    `;
    if (links.length === 0) {
      html += '<div class="empty-state" style="padding:30px"><p>暂无关联实验</p></div>';
    } else {
      html += '<div class="card"><div class="card-body"><table class="exp-table"><thead><tr><th>关联实验</th><th>类型</th><th>操作</th></tr></thead><tbody>';
      for (const l of links) {
        const typeNames = { related: '相关', predecessor: '前序实验', followup: '后续实验' };
        html += `<tr>
          <td><a href="#" onclick="App.openExperiment(${l.to_exp});return false">${this.escape(l.linked_title)}</a></td>
          <td>${typeNames[l.link_type] || l.link_type}</td>
          <td><button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="App.removeLink(${exp.id}, ${l.to_exp}, '${l.link_type}')">移除</button></td>
        </tr>`;
      }
      html += '</tbody></table></div></div>';
    }
    container.innerHTML = html;
  },

  async addLink(expId) {
    const target = document.getElementById('link-target').value;
    const type = document.getElementById('link-type').value;
    if (!target) { this.toast('请输入实验ID', 'error'); return; }
    try {
      await API.addLink(expId, parseInt(target), type);
      this.toast('关联已添加', 'success');
      this.state.currentExp = await API.getExperiment(expId);
      this.renderLinksTab(this.state.currentExp);
    } catch (err) { this.toast(err.message, 'error'); }
  },

  async removeLink(expId, toExp, linkType) {
    await API.removeLink(expId, toExp, linkType);
    this.state.currentExp = await API.getExperiment(expId);
    this.renderLinksTab(this.state.currentExp);
  },

  async saveExperiment() {
    const exp = this.state.currentExp;
    if (!exp) return;

    const data = {
      title: document.getElementById('exp-title').value,
      project: document.getElementById('exp-project').value,
      status: document.getElementById('exp-status').value,
      exp_date: document.getElementById('exp-date').value,
      target_compound: document.getElementById('exp-target').value,
      yield_pct: parseFloat(document.getElementById('exp-yield').value) || null,
      purity_pct: parseFloat(document.getElementById('exp-purity').value) || null,
      step_no: (() => {
        const v = document.getElementById('exp-step')?.value;
        return v === undefined || v === '' ? null : parseInt(v, 10) || null;
      })(),
    };

    // Content from editor
    if (this.editor) data.content = this.editor.getHTML();

    try {
      await API.updateExperiment(exp.id, data);

      // Save reagents if changed
      if (this.reagentTable) {
        await API.updateReagents(exp.id, this.reagentTable.getReagents());
      }

      // Auto-save reaction scheme if present
      if (this.state.reactionData) {
        const rd = this.state.reactionData;
        if (rd.image_path) {
          await API.saveReaction(exp.id, {
            display_mode: 'image',
            image_path: rd.image_path || '',
          });
        }
      }

      this.toast('已保存', 'success');
    } catch (err) {
      this.toast('保存失败: ' + err.message, 'error');
    }
  },

  async deleteExperiment(id) {
    if (!confirm('确定删除此实验？此操作不可撤销。')) return;
    try {
      await API.deleteExperiment(id);
      this.toast('已删除', 'success');
      this.navigate('experiments');
    } catch (err) { this.toast(err.message, 'error'); }
  },

  // Delete from the experiment list page (no need to open the record first)
  async deleteExperimentFromList(id) {
    if (!confirm('确定删除此实验？此操作不可撤销。')) return;
    try {
      await API.deleteExperiment(id);
      this.toast('已删除', 'success');
      this.renderExperiments();
    } catch (err) { this.toast(err.message, 'error'); }
  },

  async deleteAttachment(expId, attId) {
    if (!confirm('删除此附件？')) return;
    try {
      await API.deleteAttachment(expId, attId);
      this.state.currentExp = await API.getExperiment(expId);
      this.renderAttachmentsTab(this.state.currentExp);
      this.toast('附件已删除', 'success');
    } catch (err) { this.toast(err.message, 'error'); }
  },

  insertImageToEditor(filePath) {
    if (this.editor) {
      this.editor.insertImage(`/attachments/${filePath}`);
      this.toast('已插入到正文', 'success');
    }
  },

  // Insert a PDF into the editor from the attachment list (appendix)
  insertPdfToEditor(expId, filePath, filename, attId) {
    if (!this.editor) return;
    const url = `/attachments/${filePath}`;
    this.editor.insertPdf(url, filename, attId);
    this.toast('已插入到正文', 'success');
  },

  // Upload a PDF selected from the editor toolbar, then embed it into the content.
  async uploadPdfToEditor(file) {
    const exp = this.state.currentExp;
    if (!exp) {
      this.toast('请先保存实验，再插入 PDF', 'error');
      return;
    }
    try {
      const res = await API.uploadAttachment(exp.id, file, '', 'pdf');
      const url = `/attachments/${exp.id}/${encodeURIComponent(res.filename)}`;
      // 同步刷新附件（附录）列表
      this.state.currentExp = await API.getExperiment(exp.id);
      this.renderAttachmentsTab(this.state.currentExp);
      // 插入正文
      if (this.editor) this.editor.insertPdf(url, res.filename, res.id);
      this.toast('PDF 已插入正文并加入附件', 'success');
    } catch (err) {
      this.toast('PDF 插入失败: ' + err.message, 'error');
    }
  },

  // Delete a PDF embedded in the content: removes the card AND its attachment record/file.
  async deletePdfEmbed(btn) {
    const card = btn.closest('.pdf-embed');
    if (!card) return;
    const attId = parseInt(card.dataset.attId, 10);
    const expId = this.state.currentExpId || (this.state.currentExp && this.state.currentExp.id);
    if (!attId || !expId) {
      this.toast('无法定位该 PDF 的附件记录', 'error');
      return;
    }
    if (!confirm('删除该 PDF？对应的附件记录与文件将一并删除，不可恢复。')) return;
    try {
      await API.deleteAttachment(expId, attId);
      card.remove();
      // 手动删除 DOM 不触发编辑器 input 事件 → 同步内容并落库
      this.state.editorContent = this.editor ? this.editor.getHTML() : this.state.editorContent;
      this.state.currentExp = await API.getExperiment(expId);
      this.renderAttachmentsTab(this.state.currentExp);
      this.saveExperiment();
      this.toast('PDF 及其附件已删除', 'success');
    } catch (err) {
      this.toast('删除失败: ' + err.message, 'error');
    }
  },

  // Insert the reaction equation preview + reagent summary table into the rich-text body
  async insertReactionReagentToContent() {
    if (!this.editor) return;
    const rd = this.state.reactionData;
    let block = '<div class="rxn-reagent-embed" data-embed="rxn-reagent">';
    block += '<hr>';
    block += '<h2>反应方程式</h2>';
    block += await this.renderReactionEquationHTML(rd) || '<p>（尚未设置反应方程式）</p>';
    block += '<h2>投料表汇总</h2>';
    const reagents = (this.reagentTable && this.reagentTable.getReagents())
      || this.state.reagents || (this.state.currentExp && this.state.currentExp.reagents) || [];
    block += this.renderReagentSummaryHTML(reagents);
    block += '</div>';
    this.editor.insertHTML(block);
    this.toast('已插入反应与投料表到正文', 'success');
  },

  // Remove the reaction + reagent block previously embedded into the content.
  removeReactionReagentFromContent() {
    if (!this.editor || !this.editor.content) return;
    const root = this.editor.content;
    let removed = 0;

    // 1) Remove marked embeds (inserted by current version)
    const embeds = root.querySelectorAll('[data-embed="rxn-reagent"]');
    removed += embeds.length;
    embeds.forEach(el => el.remove());

    // 2) Legacy fallback: content inserted before the wrapper marker existed
    if (!embeds.length) {
      const before = root.querySelectorAll('h2').length;
      this._removeLegacyReactionBlock(root);
      removed = before - root.querySelectorAll('h2').length;
    }

    if (!removed) {
      this.toast('正文中没有已插入的反应与投料表', 'info');
      return;
    }

    // Programmatic DOM removal does not fire the editor 'input' event → sync state manually
    this.state.editorContent = this.editor.getHTML();
    this.toast('已从正文删除反应与投料表', 'success');
    this.saveExperiment();
  },

  // Fallback: locate the legacy 「反应方程式」…「投料表汇总」 region and strip it.
  _removeLegacyReactionBlock(root) {
    const h2s = Array.from(root.querySelectorAll('h2'));
    const startIdx = h2s.findIndex(h => h.textContent.trim() === '反应方程式');
    if (startIdx === -1) return;
    const endIdx = h2s.findIndex(h => h.textContent.trim() === '投料表汇总');

    const startNode = h2s[startIdx];
    let endNode = endIdx !== -1 ? h2s[endIdx] : startNode;
    // include the summary table right after the 投料表汇总 heading
    if (endIdx !== -1) {
      const next = endNode.nextElementSibling;
      if (next && (next.tagName === 'TABLE' || next.classList.contains('reagent-summary'))) {
        endNode = next;
      }
    }

    const toRemove = [];
    let node = startNode;
    while (node) {
      toRemove.push(node);
      if (node === endNode) break;
      node = node.nextElementSibling;
      if (toRemove.length > 60) break; // safety
    }
    // also strip the <hr> preceding the heading if present
    const prev = startNode.previousElementSibling;
    if (prev && prev.tagName === 'HR') toRemove.unshift(prev);
    toRemove.forEach(n => n.remove());
  },

  // Generate a reusable template from the current experiment:
  // captures content + reagent_template + reaction_template so new experiments
  // from this template include the reaction equation and feeding table.
  async generateTemplateFromExp() {
    const exp = this.state.currentExp;
    if (!exp) return;
    try {
      // Ensure latest reaction + reagents + content are persisted first
      await this.saveExperiment();
      const fresh = await API.getExperiment(exp.id);
      this.state.currentExp = fresh;

      const rd = this.state.reactionData;
      // Embed reaction equation (with rendered structures) into template content
      let embed = '<hr><h2>反应方程式</h2>'
        + (rd ? await this.renderReactionEquationHTML(rd) : '<p>（未设置反应方程式）</p>');
      const reagents = (this.reagentTable && this.reagentTable.getReagents())
        || fresh.reagents || [];
      embed += '<h2>投料表汇总</h2>' + this.renderReagentSummaryHTML(reagents);

      const editorHTML = this.editor ? this.editor.getHTML() : (fresh.content || '');
      const content = editorHTML + embed;

      const reagent_template = JSON.stringify(
        (reagents || []).map(r => ({
          role: r.role, name: r.name, mw: r.mw, smiles: r.smiles,
          ratio_type: r.ratio_type || 'equiv',
          ratio_value: r.ratio_value != null ? r.ratio_value : r.equivalents,
          mass_g: r.mass_g != null ? r.mass_g : (r.mass_mg != null ? r.mass_mg / 1000 : null),
        }))
      );

      let reaction_template = '';
      const reaction = fresh.reaction;
      if (reaction) {
        reaction_template = JSON.stringify({
          display_mode: reaction.display_mode,
          reactant_smiles: reaction.reactant_smiles,
          product_smiles: reaction.product_smiles,
          conditions: reaction.conditions,
          arrow_label: reaction.arrow_label,
          notes: reaction.notes,
          image_path: reaction.image_path,
        });
      }

      const name = prompt('模板名称：', `实验模板 - ${exp.title}`);
      if (name === null) return;

      const res = await API.createTemplate({
        name: name.trim() || `实验模板 - ${exp.title}`,
        type: 'reaction',
        content,
        reagent_template,
        reaction_template,
      });
      this.toast(`模板已生成：${name}`, 'success');
      if (confirm('已生成模板，是否前往模板管理查看？')) {
        this.navigate('templates');
      }
    } catch (err) {
      this.toast('生成模板失败: ' + err.message, 'error');
    }
  },

  async exportExp(format) {
    const id = this.state.currentExpId;
    const fmtMap = {
      markdown: ['exportMarkdown', 'md', 'text/markdown'],
      html: ['exportHTML', 'html', 'text/html'],
      pdf: ['exportPDF', 'pdf', 'application/pdf'],
      word: ['exportWord', 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    };
    const [apiMethod, ext] = fmtMap[format] || [];
    if (!apiMethod) return;
    try {
      const res = await API[apiMethod](id);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `experiment_${id}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      this.toast('已导出', 'success');
    } catch (err) { this.toast(err.message, 'error'); }
  },

  // --- Compounds ---
  async renderCompounds() {
    if (this.state.compoundCategory === undefined) this.state.compoundCategory = 'all';
    this.contentEl.innerHTML = '<div class="loading"><div class="spinner"></div> 加载中...</div>';
    try {
      const cat = this.state.compoundCategory;
      const data = await API.listCompounds('', cat);
      const tabs = [
        ['all', '全部'],
        ['solvent', '常用溶剂库'],
        ['reagent', '常用试剂库'],
        ['project', '项目化合物库'],
      ];
      const tabHtml = tabs.map(([k, label]) =>
        `<button class="seg-btn ${cat === k ? 'active' : ''}" data-cat="${k}" onclick="App.setCompoundCategory('${k}')">${label}</button>`
      ).join('');
      let html = `
        <div class="filter-bar" style="flex-wrap:wrap;gap:10px">
          <div class="seg-control" style="margin-right:auto">${tabHtml}</div>
          <input type="text" id="compound-search" placeholder="搜索名称/CAS/SMILES..." style="flex:1;min-width:200px" oninput="App.debounceSearch('compound-search', () => App.searchCompounds())">
          <button class="btn btn-primary btn-sm" onclick="App.showAddCompoundModal()">+ 添加化合物</button>
          <button class="btn btn-secondary btn-sm" onclick="App.openImportCompounds()">📥 导入Excel</button>
          <button class="btn btn-ghost btn-sm" onclick="App.exportCompounds()">📤 导出Excel</button>
          <button class="btn btn-sm" id="btn-batch-del" style="color:var(--danger);display:none" onclick="App.batchDeleteCompounds()">🗑️ 批量删除(<span id="sel-count">0</span>)</button>
          <input type="file" id="compound-import-file" accept=".xlsx" style="display:none" onchange="App.handleImportCompounds(this)">
        </div>
        <div class="card"><div class="card-body" style="padding:0">
      `;
      if (data.count === 0) {
        const empty = cat === 'solvent' ? '常用溶剂库为空'
          : cat === 'reagent' ? '常用试剂库为空'
          : cat === 'project' ? '项目化合物库为空，添加你的第一个化合物，或导入Excel批量录入'
          : '化合物库为空';
        html += `<div class="empty-state"><div class="icon">⚗️</div><h3>${empty}</h3><p>添加 / 导入 即可录入</p></div>`;
      } else {
        html += '<table class="exp-table"><thead><tr><th style="width:36px"><input type="checkbox" id="comp-select-all" onchange="App.toggleSelectAll(this)"></th><th>名称</th><th>CAS</th><th>SMILES</th><th>分子式</th><th>分子量</th><th>操作</th></tr></thead><tbody>';
        for (const c of data.compounds) {
          html += `<tr>
            <td><input type="checkbox" class="comp-check" value="${c.id}" onchange="App.updateSelCount()"></td>
            <td style="font-weight:500">${this.escape(c.name)}</td>
            <td>${this.escape(c.cas || '—')}</td>
            <td><code style="font-size:11px">${this.escape(c.smiles || '')}</code></td>
            <td>${c.formula || '—'}</td>
            <td>${c.mw || '—'}</td>
            <td>
              <button class="btn btn-ghost btn-sm" onclick="App.viewCompound(${c.id})">查看</button>
              <button class="btn btn-secondary btn-sm" onclick="App.editCompound(${c.id})">编辑</button>
              <button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="App.deleteCompound(${c.id})">删除</button>
            </td>
          </tr>`;
        }
        html += '</tbody></table>';
      }
      html += '</div></div>';
      this.contentEl.innerHTML = html;
    } catch (err) {
      this.contentEl.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${err.message}</p></div>`;
    }
  },

  setCompoundCategory(cat) {
    this.state.compoundCategory = cat;
    this.renderCompounds();
  },

  async searchCompounds() {
    const q = document.getElementById('compound-search').value;
    const cat = this.state.compoundCategory || '';
    const data = await API.listCompounds(q, cat);
    const tbody = this.contentEl.querySelector('tbody');
    if (!tbody) return;
    if (data.count === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">无结果</td></tr>';
    } else {
      tbody.innerHTML = data.compounds.map(c => `<tr>
        <td><input type="checkbox" class="comp-check" value="${c.id}" onchange="App.updateSelCount()"></td>
        <td style="font-weight:500">${this.escape(c.name)}</td>
        <td>${this.escape(c.cas || '—')}</td>
        <td><code style="font-size:11px">${this.escape(c.smiles || '')}</code></td>
        <td>${c.formula || '—'}</td>
        <td>${c.mw || '—'}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="App.viewCompound(${c.id})">查看</button>
          <button class="btn btn-secondary btn-sm" onclick="App.editCompound(${c.id})">编辑</button>
          <button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="App.deleteCompound(${c.id})">删除</button>
        </td>
      </tr>`).join('');
    }
  },

  // Compound bulk operations
  toggleSelectAll(cb) {
    this.contentEl.querySelectorAll('.comp-check').forEach(c => { c.checked = cb.checked; });
    this.updateSelCount();
  },

  updateSelCount() {
    const n = this.contentEl.querySelectorAll('.comp-check:checked').length;
    const btn = document.getElementById('btn-batch-del');
    const cnt = document.getElementById('sel-count');
    if (btn) btn.style.display = n > 0 ? '' : 'none';
    if (cnt) cnt.textContent = n;
  }
});
