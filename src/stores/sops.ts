// ============================================================
// stores/sops.ts —— SOP 数据的全局仓库（Pinia）
// 作用：把"SOP 列表"这份数据放进行车记录袋，所有页面共享。
// 好处：列表页加载一次，详情页直接用，不用每个页面重复读取。
// 类比：楼下有个公共储物柜（store），谁要用 SOP 数据就来取，
//       不用每个人都自己跑到仓库（文件系统）搬一趟。
// ============================================================
import { defineStore } from "pinia";
import { loadAllSops } from "../utils/loadSops";
import type { Sop } from "../types/sop";

export const useSopsStore = defineStore("sops", {
  // state：这份数据的"当前状态"
  state: () => ({
    sops: [] as Sop[],      // 全部 SOP（解析好的结构化数据）
    loaded: false,          // 是否已加载过（避免重复读取）
    loading: false,         // 是否正在加载（列表页显示"加载中"）
    error: "" as string,    // 加载失败时的错误信息
  }),

  // getters：根据 state 派生出来的"计算值"（相当于只读函数）
  getters: {
    // 按 SOP 的 id 查找（详情页用）：byId("alkylation-001") → Sop | undefined
    byId: (state) => (id: string) => state.sops.find((s) => s.meta.id === id),
    // 所有分类名（列表页分组用）：new Set 自动去重
    categories: (state) => [...new Set(state.sops.map((s) => s.meta.category))],
  },

  // actions：修改 state 的"动作"（异步操作放这里）
  actions: {
    /// 加载全部 SOP；已加载过就直接返回（不会重复请求）
    async fetchAll() {
      if (this.loaded) return;
      this.loading = true;
      this.error = "";
      try {
        this.sops = await loadAllSops();
        this.loaded = true;
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
  },
});
