/**
 * ChemELN Reagent Table — auto-calculating stoichiometry table.
 * Substrate: enter actual feeding mass (g) + MW.
 * Other reagents: choose 当量比 (equivalent ratio) or 重量比 (weight ratio)
 * relative to the substrate → auto-calculate feeding mass (g).
 * Weight-ratio mode computes mass only (no moles/volume).
 */
// 需要按显示规则格式化位数的投料表数值字段（规则见 format.js 顶部注释）。
// 只影响输入框的显示，state 与计算仍是完整精度。
const QTY_FIELDS = ['mass_g', 'moles_mmol', 'volume_ml'];

class ReagentTable {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.reagents = [];
    this.onChange = options.onChange || (() => {});
    this.build();
  }

  build() {
    this.container.innerHTML = `
      <div class="reagent-section">
        <div class="form-row" style="margin-bottom:10px;gap:8px;flex-wrap:wrap;align-items:center">
          <button class="btn btn-secondary btn-sm" id="btn-add-substrate" style="white-space:nowrap">+ 添加原料</button>
          <button class="btn btn-secondary btn-sm" id="btn-add-reagent" style="white-space:nowrap">+ 添加试剂</button>
          <button class="btn btn-primary btn-sm" id="btn-calc" style="white-space:nowrap">⚡ 重新计算</button>
          <span style="color:var(--text-muted);font-size:12px">原料填实际投料质量(g)，其余试剂选「当量比」或「重量比」自动算投料量(g)</span>
        </div>

        <div style="overflow-x:auto">
          <table class="reagent-table" id="reagent-tbl">
            <thead>
              <tr>
                <th style="width:30px">#</th>
                <th>名称</th>
                <th style="width:80px">角色</th>
                <th style="width:70px">分子量</th>
                <th style="width:160px">投料比（相对原料）</th>
                <th style="width:90px">投料质量(g)</th>
                <th style="width:80px">摩尔(mmol)</th>
                <th style="width:80px">体积(mL)</th>
                <th style="width:70px">纯度(%)</th>
                <th style="width:70px">密度</th>
                <th style="width:70px">浓度(M)</th>
                <th style="width:40px"></th>
              </tr>
            </thead>
            <tbody id="reagent-body"></tbody>
          </table>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    this.container.querySelector('#btn-calc').onclick = () => {
      this.localCalculate();
      App.toast('投料表已重新计算', 'success');
    };
    this.container.querySelector('#btn-add-reagent').onclick = () => this.addReagent();
    this.container.querySelector('#btn-add-substrate').onclick = () => this.addReagent({ role: 'substrate' });
  }

  addReagent(data = {}) {
    // Normalize legacy fields (mass_mg/equivalents) into the new g + ratio model
    let ratioType = data.ratio_type || 'equiv';
    let ratioValue = data.ratio_value;
    if (ratioValue == null) ratioValue = (data.equivalents != null ? data.equivalents : 1);
    let massG = data.mass_g;
    if (massG == null && data.mass_mg != null) massG = data.mass_mg / 1000.0;

    this.reagents.push({
      role: data.role || 'reagent',
      name: data.name || '',
      mw: data.mw || null,
      ratio_type: ratioType,
      ratio_value: ratioValue,
      equivalents: ratioType === 'equiv' ? ratioValue : null,   // legacy sync
      mass_g: massG || null,
      mass_mg: massG != null ? Math.round(massG * 1000 * 100) / 100 : null, // legacy sync
      moles_mmol: data.moles_mmol || null,
      volume_ml: data.volume_ml || null,
      density: data.density || null,
      concentration: data.concentration || null,
      purity_pct: data.purity_pct || null,
      sort_order: this.reagents.length,
    });
    this.render();
  }

  render() {
    const tbody = this.container.querySelector('#reagent-body');
    tbody.innerHTML = '';

    this.reagents.forEach((r, i) => {
      const tr = document.createElement('tr');
      tr.className = `role-${r.role}`;

      // 投料比单元格：原料为基准，其余为「当量比/重量比」选择 + 数值
      let ratioCell;
      if (r.role === 'substrate') {
        ratioCell = `<td colspan="1" style="color:var(--text-muted);font-size:12px">基准（原料）</td>`;
      } else {
        const eqSel = r.ratio_type === 'weight' ? '' : 'selected';
        const wtSel = r.ratio_type === 'weight' ? 'selected' : '';
        ratioCell = `
          <td>
            <div style="display:flex;gap:4px;align-items:center;flex-wrap:nowrap">
              <select data-field="ratio_type" data-idx="${i}" style="border:1px solid var(--border);background:var(--bg-card);font-size:12px;width:74px">
                <option value="equiv" ${eqSel}>当量比</option>
                <option value="weight" ${wtSel}>重量比</option>
              </select>
              <input type="number" value="${r.ratio_value != null ? r.ratio_value : ''}" data-field="ratio_value" data-idx="${i}" step="0.01" style="width:64px" title="相对原料的当量比或重量比">
            </div>
          </td>`;
      }

      // 重量比模式下不计算摩尔/体积
      const isWeight = r.role !== 'substrate' && r.ratio_type === 'weight';
      const molCell = isWeight
        ? `<td style="color:var(--text-light);text-align:center">—</td>`
        : `<td><input type="number" value="${Fmt.qty(r.moles_mmol) ?? ''}" data-field="moles_mmol" data-idx="${i}" step="0.001" readonly style="width:70px;color:var(--text-muted);background:var(--bg-light)"></td>`;
      const volCell = isWeight
        ? `<td style="color:var(--text-light);text-align:center">—</td>`
        : `<td><input type="number" value="${Fmt.qty(r.volume_ml) ?? ''}" data-field="volume_ml" data-idx="${i}" step="0.001" style="width:70px"></td>`;

      tr.innerHTML = `
        <td>${i + 1}</td>
        <td><input type="text" value="${r.name || ''}" data-field="name" data-idx="${i}" placeholder="试剂名称"></td>
        <td>
          <select data-field="role" data-idx="${i}" style="border:1px solid transparent;background:transparent;font-size:12px">
            <option value="substrate" ${r.role === 'substrate' ? 'selected' : ''}>原料</option>
            <option value="reagent" ${r.role === 'reagent' ? 'selected' : ''}>试剂</option>
            <option value="solvent" ${r.role === 'solvent' ? 'selected' : ''}>溶剂</option>
            <option value="product" ${r.role === 'product' ? 'selected' : ''}>产物</option>
          </select>
        </td>
        <td><input type="number" value="${r.mw || ''}" data-field="mw" data-idx="${i}" step="0.01" style="width:65px"></td>
        ${ratioCell}
        <td><input type="number" value="${Fmt.qty(r.mass_g) ?? ''}" data-field="mass_g" data-idx="${i}" step="0.0001" style="width:80px" title="投料质量(g)：显示位数随数值大小变化，实际精度不受影响"></td>
        ${molCell}
        ${volCell}
        <td><input type="number" value="${r.purity_pct || ''}" data-field="purity_pct" data-idx="${i}" step="0.1" style="width:60px"></td>
        <td><input type="number" value="${r.density || ''}" data-field="density" data-idx="${i}" step="0.001" style="width:60px"></td>
        <td><input type="number" value="${r.concentration || ''}" data-field="concentration" data-idx="${i}" step="0.1" style="width:60px"></td>
        <td><button class="btn btn-ghost btn-sm" data-action="remove" data-idx="${i}" title="删除此行">✕</button></td>
      `;
      tbody.appendChild(tr);
    });

    // 删除按钮事件绑定
    tbody.querySelectorAll('button[data-action="remove"]').forEach(btn => {
      btn.onclick = () => {
        const idx = parseInt(btn.dataset.idx);
        this.removeReagent(idx);
      };
    });

    // Bind field changes
    tbody.querySelectorAll('input, select').forEach(el => {
      el.onchange = (e) => {
        const idx = parseInt(e.target.dataset.idx);
        const field = e.target.dataset.field;
        let val = e.target.value;
        if (field !== 'name' && field !== 'role' && field !== 'ratio_type') {
          val = val === '' ? null : parseFloat(val);
        }
        this.reagents[idx][field] = val;
        this.onChange(this.reagents);

        // 手输的质量/摩尔/体积：提交后把输入框显示按规则归一（state 仍是完整精度）
        if (QTY_FIELDS.includes(field) && val != null) {
          e.target.value = Fmt.qty(val);
        }

        // 名称变化 → 自动查分子量
        if (field === 'name' && val && val.trim()) {
          this.lookupMw(idx);
        }
        // 切换投料比类型 → 重新渲染该行（摩尔/体积列显隐）
        if (field === 'ratio_type') {
          this.render();
          this.localCalculate();
          return;
        }
        // 投料比/分子量/纯度/密度/浓度/原料质量变化 → 自动计算投料量
        if (['ratio_value', 'mw', 'purity_pct', 'density', 'concentration'].includes(field) ||
            (field === 'mass_g' && this.reagents[idx].role === 'substrate')) {
          this.localCalculate();
        }
      };

      // 名称输入时防抖自动查询分子量（无需失焦）
      if (el.dataset.field === 'name') {
        let timer = null;
        el.oninput = (e) => {
          const idx = parseInt(e.target.dataset.idx);
          this.reagents[idx].name = e.target.value;
          clearTimeout(timer);
          const value = e.target.value;
          timer = setTimeout(() => {
            if (value.trim() && value.trim().length >= 2) {
              this.lookupMw(idx, true);
            }
          }, 600);
        };
      }
    });

    if (this.reagents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="12" style="text-align:center;color:var(--text-light);padding:20px">
        点击"+ 添加试剂"开始添加投料表
      </td></tr>`;
    }
  }

  async calculate() {
    // Local stoichiometry recompute (no backend round-trip needed)
    const sub = this.reagents.find(reg => reg.role === 'substrate');
    if (!sub || !sub.mass_g || !sub.mw || sub.mass_g <= 0 || sub.mw <= 0) {
      App.toast('请先添加「原料」行并填写投料质量(g)与分子量', 'error');
      return;
    }
    this.localCalculate();
    App.toast('投料表已重新计算', 'success');
  }

  removeReagent(idx) {
    this.reagents.splice(idx, 1);
    this.reagents.forEach((r, i) => r.sort_order = i);
    this.render();
  }

  /**
   * 按名称自动查找分子量：先查化合物库，再试 SMILES，最后查内置常用试剂表/化学式。
   * @param {number} idx 行索引
   * @param {boolean} quiet 静默模式（输入过程中触发，不弹"未找到"提示）
   */
  async lookupMw(idx, quiet = false) {
    const name = (this.reagents[idx].name || '').trim();
    if (!name) return;

    try {
      const result = await API.lookupMw(name);
      // 结果回来时用户可能已改名/删行，做一致性校验
      if (result.found && (this.reagents[idx].name || '').trim() === name) {
        this.reagents[idx].mw = result.mw;
        if (result.smiles) this.reagents[idx].smiles = result.smiles;
        if (result.formula) this.reagents[idx].formula = result.formula;
        this.updateRowField(idx, 'mw', result.mw);

        // 库中命中（名称/CAS/SMILES 反查）→ 名称回填为标准名称
        const stdName = result.name || '';
        if (['library', 'cas', 'smiles'].includes(result.source) && stdName && stdName !== name) {
          this.reagents[idx].name = stdName;
          this.updateRowField(idx, 'name', stdName);
        }

        const srcMap = {
          library: '化合物库匹配',
          cas: 'CAS号匹配',
          smiles: 'SMILES识别',
          common: '常用试剂库',
          formula: '化学式解析',
        };
        const src = srcMap[result.source] || result.source;
        App.toast(`「${stdName || name}」MW已自动填充: ${result.mw} (${src})`, 'success');
        this.localCalculate();
        this.onChange(this.reagents);
      } else if (!result.found && !quiet) {
        App.toast(`未找到"${name}"的分子量，请手动输入`, 'info');
      }
    } catch (e) {
      // 静默失败，不打断用户操作
    }
  }

  /**
   * 客户端本地化学计量计算（无需调用后端）。
   * 以「原料」行自身的质量(g)+分子量为反应基准：
   *  - 当量比模式：摩尔 = 原料摩尔 × 当量比；质量(g) = 摩尔 × MW / 1000 / 纯度；
   *    体积 = 摩尔/浓度 或 质量/密度。
   *  - 重量比模式：质量(g) = 重量比 × 原料质量(g)；不计算摩尔/体积。
   */
  localCalculate() {
    const sub = this.reagents.find(reg => reg.role === 'substrate');
    if (!sub || !sub.mass_g || !sub.mw || sub.mass_g <= 0 || sub.mw <= 0) return;

    const substrateMoles = sub.mass_g * 1000 / sub.mw; // mmol

    const r = (v, d) => v == null ? null : Math.round(v * Math.pow(10, d)) / Math.pow(10, d);

    this.reagents.forEach((reg, i) => {
      if (reg.role === 'substrate') {
        // 原料行的摩尔数 = 自身质量/分子量；质量保持用户填写值
        reg.moles_mmol = r(substrateMoles, 4);
      } else if (reg.ratio_value != null && reg.ratio_value > 0) {
        if (reg.ratio_type === 'weight') {
          // 重量比：投料质量 = 重量比 × 原料质量；只算质量
          reg.mass_g = r(reg.ratio_value * sub.mass_g, 4);
          reg.moles_mmol = null;
          reg.volume_ml = null;
        } else {
          // 当量比：需要分子量
          const moles = substrateMoles * reg.ratio_value;
          reg.moles_mmol = r(moles, 4);
          const rMw = reg.mw || 0;
          if (rMw > 0) {
            const purity = (reg.purity_pct || 100) / 100.0;
            const mass_g = purity > 0 ? (moles * rMw / 1000) / purity : moles * rMw / 1000;
            reg.mass_g = r(mass_g, 4);

            // 体积计算
            if (reg.concentration && reg.concentration > 0) {
              // 浓度 mol/L = mmol/mL
              reg.volume_ml = r(moles / reg.concentration, 4);
            } else if (reg.density && reg.density > 0 && mass_g > 0) {
              // 密度 g/mL → 体积 mL = mass_g / density
              reg.volume_ml = r(mass_g / reg.density, 4);
            } else {
              reg.volume_ml = null;
            }
          } else {
            reg.mass_g = null;
            reg.volume_ml = null;
          }
        }
      } else {
        // 未设置投料比：清空联动结果
        if (reg.role !== 'substrate') {
          reg.mass_g = reg.mass_g; // 保留手填值
          reg.moles_mmol = null;
          reg.volume_ml = null;
        }
      }

      // 就地更新只读/联动字段，不触发完整重渲染（避免丢失焦点）
      this.updateRowField(i, 'moles_mmol', reg.moles_mmol);
      this.updateRowField(i, 'mass_g', reg.mass_g);
      this.updateRowField(i, 'volume_ml', reg.volume_ml);

      // 同步旧字段（防御：旧版后端/旧消费方仍读取 equivalents / mass_mg）
      reg.equivalents = (reg.ratio_type === 'equiv' && reg.ratio_value != null) ? reg.ratio_value : null;
      reg.mass_mg = reg.mass_g != null ? Math.round(reg.mass_g * 1000 * 100) / 100 : null;
    });
  }

  /**
   * 就地更新表格中某一行的某个字段值（不重渲染）。
   */
  updateRowField(idx, field, value) {
    const input = this.container.querySelector(
      `input[data-field="${field}"][data-idx="${idx}"]`
    );
    if (input) {
      // 投料质量/摩尔数/体积按显示规则格式化（state 里仍是完整精度，只改输入框显示）
      const shown = QTY_FIELDS.includes(field) ? Fmt.qty(value) : value;
      input.value = shown ?? '';
    }
  }

  getReagents() {
    return this.reagents;
  }

  setReagents(reagents) {
    this.reagents = reagents || [];
    if (this.reagents.length === 0) {
      // 空白时自动补一行原料，方便直接开填
      this.addReagent({ role: 'substrate' });
    } else {
      this.render();
    }
  }

  setSubstrate(massG, mw) {
    const sub = this.reagents.find(reg => reg.role === 'substrate');
    if (!sub) return;
    const idx = this.reagents.indexOf(sub);
    if (massG) {
      sub.mass_g = massG;
      this.updateRowField(idx, 'mass_g', massG);
    }
    if (mw) {
      sub.mw = mw;
      this.updateRowField(idx, 'mw', mw);
    }
    this.localCalculate();
  }
}
