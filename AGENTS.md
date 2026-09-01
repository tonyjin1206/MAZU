# MAZU 外贸 ERP — Agent 必读铁律

项目一句话：外贸ERP，公司无工厂，两条对称业务线（纯贸易买A卖A / 委外买ABC→加工厂→卖D）。

## 核心铁律（全 ERP 强制，换人换机都别踩）

1. **上游禁止下游改，退下游才解锁**：下游有单据时，上游不能变更/删除/退回；想改上游，先到对应单据页退下游。
2. **BOM 只约束委外领料量**：转直采按成品采购，无视 BOM（恒买产品本身）；委外「领料」按 BOM 算需领量（BOM 只约束委外领料量，不约束转直采采购）。
3. **状态颜色四档**：本环节完成=绿 / 进行中=橙 / 未开始=灰 / 终止=红。别自创蓝色当状态色。
4. **编码自动生成**：客户 CU / 供应商 SU / 材料 RM / 产品 FG，均 6 位数字流水（如 FG000001），禁手输。
5. **单据号规则**：前缀-YYMMDD+2位序号，如 SO-26080101、WO-26080101，同天序号从 01 起。
6. **完成=人工点**：采购/委外的"完成"由业务员手动点（可取消完成再追加），系统只自动判"达上限"。
7. **一步一步来不跳步**：源头单据只做"标记推送"，下游单据在专门页面生成，别让源头按钮直接造下游单据。

## 技术栈 / 启动命令

- 仓库：https://github.com/tonyjin1206/MAZU（私有，和朋友协作）
- 分支：main = 统一版本（朋友维护）；Sales_Purchase = 自己的工作分支
- 技术栈：FastAPI(8788) + Vue3 Vite(5173) + SQLite(backend/data/erp.db)
- 账号：admin / admin123

```bash
# 后端（必须清 PYTHONPATH，见坑）
cd ~/MAZU/backend && env -u PYTHONPATH PYTHONPATH=. venv/bin/python run.py

# 前端
cd ~/MAZU/frontend && npm run dev
```

⚠️ 坑：所有项目 Python 命令必须清 PYTHONPATH（`env -u PYTHONPATH`），否则会加载到 Hermes 终端的包，版本全乱。

## 完整上下文

改代码前先读仓库根的 **DEVELOPMENT_STATUS.md**（开发现状速览），那是给接手开发者看的全貌。
深度细节（合并冲突实战 / 单据链 / 各模块陷阱）见 Hermes 的 mazu-development 技能。
