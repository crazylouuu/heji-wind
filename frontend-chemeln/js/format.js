/**
 * ChemELN 展示层格式化工具
 *
 * 投料表里「投料质量(g)」「摩尔(mmol)」「体积(mL)」三列的显示规则：
 *   v < 0       → 3 位小数
 *   0 ≤ v < 10  → 2 位小数
 *   v ≥ 10      → 1 位小数
 *
 * ⚠ 只影响「显示」：数据库存储与化学计量计算仍使用完整精度，
 *   与 Excel 的「单元格值不变、只是数字格式变了」是同一个模型。
 *   后端同名规则见 backend/utils/export.py: fmt_quantity()，
 *   verify_export.py 里有跨语言一致性断言，两边改动必须同步。
 */
const Fmt = {
  /** 按数值大小取显示位数 */
  digits(n) {
    if (!isFinite(n)) return 2;
    if (n < 0) return 3;
    return n < 10 ? 2 : 1;
  },

  /**
   * 十进制四舍五入（半进位），与后端 Decimal(str(v), ROUND_HALF_UP) 一致。
   * 先 toFixed(d+6) 把二进制浮点还原成「人类看到的那个十进制数」，
   * 避免 (2.675).toFixed(2) === '2.67' 这类浮点坑，再按字符串进位。
   */
  roundHalfUp(n, d) {
    const neg = n < 0;
    const s = Math.abs(n).toFixed(Math.min(20, d + 6));
    const [intPart, frac = ''] = s.split('.');
    const keep = frac.slice(0, d);
    const nextDigit = (frac.charCodeAt(d) - 48) || 0;
    let digits = intPart + keep.padEnd(d, '0');
    if (nextDigit >= 5) {
      const arr = digits.split('');
      let i = arr.length - 1;
      for (; i >= 0; i--) {
        if (arr[i] === '9') { arr[i] = '0'; }
        else { arr[i] = String(Number(arr[i]) + 1); break; }
      }
      if (i < 0) arr.unshift('1');
      digits = arr.join('');
    }
    const head = d ? digits.slice(0, digits.length - d) : digits;
    const tail = d ? digits.slice(digits.length - d) : '';
    // 舍入到 0 的负数（如 -0.0004）不要显示成 "-0.00"
    if (!Number(head) && !Number(tail || 0)) return '0' + (d ? '.' + tail : '');
    return (neg ? '-' : '') + head + (d ? '.' + tail : '');
  },

  /** 投料质量 / 摩尔数 → 显示字符串；空值返回 null，非法值原样返回 */
  qty(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    if (!isFinite(n)) return String(v);
    return this.roundHalfUp(n, this.digits(n));
  },
};

if (typeof window !== 'undefined') window.Fmt = Fmt;
if (typeof module !== 'undefined' && module.exports) module.exports = Fmt;
