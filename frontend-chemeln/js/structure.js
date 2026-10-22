/**
 * ChemELN Structure Editor — SMILES input, mol paste, live RDKit rendering.
 *
 * 结构式录入有两条路：① 直接输 SMILES（RDKit 校验并渲染成 PNG）
 * ② 从 ChemDraw 复制 Molfile 粘贴（自动转 SMILES）。
 *
 * 2026-10-27 移除了内嵌的 Ketcher 画板 —— 它单独占 30MB（完整化学编辑器），
 * 而实际使用中绝大多数结构式来自已知 SMILES 或 ChemDraw 导出，
 * 画板带来的收益远小于把安装包从 53MB 涨到 83MB 的代价。
 */
class StructureEditor {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.currentSmiles = '';
    this.currentMolfile = '';
    this.onChange = options.onChange || (() => {});
    this.build();
  }

  build() {
    this.container.innerHTML = `
      <div class="structure-editor">
        <div class="form-row">
          <div class="form-group" style="flex:1">
            <label>SMILES / 结构式</label>
            <div style="display:flex;gap:6px">
              <input type="text" class="form-input" id="smiles-input"
                     placeholder="输入SMILES，如 CCO (乙醇) 或 c1ccccc1 (苯)"
                     style="font-family:monospace;font-size:13px">
              <button class="btn btn-secondary btn-sm" id="btn-render">渲染</button>
            </div>
          </div>
        </div>

        <div class="form-row" style="margin-top:8px">
          <div class="form-group" style="flex:1">
            <label>结构预览</label>
            <div class="structure-viewer" id="struct-preview">
              <span class="placeholder">输入SMILES后点击渲染</span>
            </div>
          </div>
          <div class="form-group" style="flex:1">
            <label>分子信息</label>
            <div id="mol-info" style="font-size:12px;padding:8px;border:1px solid var(--border);border-radius:4px;min-height:120px;background:var(--bg-hover)">
              <span style="color:var(--text-light)">等待输入...</span>
            </div>
          </div>
        </div>

        <div class="form-group" style="margin-top:8px">
          <label>从 ChemDraw 粘贴 Mol 文件
            <button class="btn btn-ghost btn-sm" id="btn-toggle-mol" style="margin-left:8px">展开/收起</button>
          </label>
          <textarea class="form-textarea" id="mol-input" style="display:none;font-family:monospace;font-size:11px;min-height:100px"
                    placeholder="从 ChemDraw 复制结构式（Edit > Copy Mol File），粘贴到此处..."></textarea>
          <button class="btn btn-secondary btn-sm" id="btn-parse-mol" style="display:none;margin-top:6px">解析 Mol 文件</button>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const smilesInput = this.container.querySelector('#smiles-input');
    const renderBtn = this.container.querySelector('#btn-render');
    const molToggle = this.container.querySelector('#btn-toggle-mol');
    const molInput = this.container.querySelector('#mol-input');
    const parseMolBtn = this.container.querySelector('#btn-parse-mol');

    // Render on Enter
    smilesInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.renderStructure(smilesInput.value);
      }
    });
    renderBtn.addEventListener('click', () => this.renderStructure(smilesInput.value));

    // Mol toggle
    molToggle.addEventListener('click', () => {
      const show = molInput.style.display === 'none';
      molInput.style.display = show ? 'block' : 'none';
      parseMolBtn.style.display = show ? 'inline-block' : 'none';
      molToggle.textContent = show ? '收起' : '展开/收起';
    });

    // Parse mol
    parseMolBtn.addEventListener('click', () => {
      const mol = molInput.value.trim();
      if (mol) this.parseMolfile(mol);
    });
  }

  async renderStructure(smiles) {
    if (!smiles || !smiles.trim()) {
      this.container.querySelector('#struct-preview').innerHTML =
        '<span class="placeholder">输入SMILES后点击渲染</span>';
      this.container.querySelector('#mol-info').innerHTML =
        '<span style="color:var(--text-light)">等待输入...</span>';
      return;
    }

    const preview = this.container.querySelector('#struct-preview');
    const info = this.container.querySelector('#mol-info');
    preview.innerHTML = '<div class="spinner"></div>';

    try {
      const result = await API.parseSmiles(smiles);
      if (result.valid) {
        this.currentSmiles = result.smiles;
        this.currentMolfile = result.molfile || '';
        // Update input with canonical SMILES
        this.container.querySelector('#smiles-input').value = result.smiles;

        if (result.image) {
          preview.innerHTML = `<img src="data:image/png;base64,${result.image}" alt="structure">`;
        } else {
          preview.innerHTML = '<span class="placeholder">无法渲染</span>';
        }

        info.innerHTML = `
          <div><strong>分子式:</strong> ${result.formula}</div>
          <div><strong>分子量:</strong> ${result.mw} g/mol</div>
          <div><strong>重原子数:</strong> ${result.heavy_atoms}</div>
          <div><strong>环数:</strong> ${result.ring_count}</div>
          <div><strong>InChIKey:</strong> <code style="font-size:10px">${result.inchikey}</code></div>
          <div><strong>SMILES:</strong> <code style="font-size:10px">${result.smiles}</code></div>
        `;

        this.onChange({
          smiles: result.smiles,
          molfile: this.currentMolfile,
          formula: result.formula,
          mw: result.mw,
          inchikey: result.inchikey,
          inchi: result.inchi,
        });
      } else {
        preview.innerHTML = `<span class="placeholder" style="color:var(--danger)">❌ ${result.error}</span>`;
        info.innerHTML = '<span style="color:var(--danger)">解析失败</span>';
      }
    } catch (err) {
      preview.innerHTML = `<span class="placeholder" style="color:var(--danger)">❌ ${err.message}</span>`;
      info.innerHTML = `<span style="color:var(--danger)">${err.message}</span>`;
    }
  }

  async parseMolfile(mol) {
    const info = this.container.querySelector('#mol-info');
    const preview = this.container.querySelector('#struct-preview');
    preview.innerHTML = '<div class="spinner"></div>';

    try {
      const result = await API.parseMolfile(mol);
      if (result.valid) {
        this.currentSmiles = result.smiles;
        this.currentMolfile = mol;
        this.container.querySelector('#smiles-input').value = result.smiles;

        if (result.image) {
          preview.innerHTML = `<img src="data:image/png;base64,${result.image}" alt="structure">`;
        }

        info.innerHTML = `
          <div><strong>分子式:</strong> ${result.formula}</div>
          <div><strong>分子量:</strong> ${result.mw} g/mol</div>
          <div><strong>InChIKey:</strong> <code style="font-size:10px">${result.inchikey}</code></div>
          <div><strong>SMILES:</strong> <code style="font-size:10px">${result.smiles}</code></div>
        `;

        this.onChange({
          smiles: result.smiles,
          molfile: mol,
          formula: result.formula,
          mw: result.mw,
          inchikey: result.inchikey,
          inchi: result.inchi,
        });
      }
    } catch (err) {
      preview.innerHTML = `<span class="placeholder" style="color:var(--danger)">❌ ${err.message}</span>`;
    }
  }

  setSmiles(smiles) {
    this.container.querySelector('#smiles-input').value = smiles;
    if (smiles) this.renderStructure(smiles);
  }

  getSmiles() {
    return this.currentSmiles;
  }
}
