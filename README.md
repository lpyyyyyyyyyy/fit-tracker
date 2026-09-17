# 燃 · 减脂打卡

移动端优先的单文件 PWA。**零外部依赖、可离线、数据只存在本机。**

---

## 部署（GitHub Pages）—— 两步

**第一步**：在这个文件夹里执行

```powershell
cd "C:\Users\32890\Desktop\自己\fit-tracker"
git push -u origin main
```

**第二步**：打开 GitHub 仓库页面 → **Settings → Pages → Source 选 `Deploy from a branch` → Branch 选 `main` / `/(root)` → Save**

等 1 分钟左右，你的永久地址是：

```
https://leo-emily.github.io/fit-tracker/
```

（如果用户名不是 leo-emily，把地址里的用户名换掉。）

---

## 手机上安装

用手机浏览器打开上面的地址 → 菜单 → **「添加到主屏幕」**。

之后像原生 App 一样全屏打开，**并且能收到系统通知**。

> ⚠️ 系统通知**只在这个 https 地址下可用**。本地 http 预览地址浏览器不给通知权限 —— 这是浏览器的安全限制，不是 App 的问题。

---

## 本地预览（可选）

```powershell
node _serve.js 8080
```

- 电脑：http://localhost:8080/
- 手机：http://<局域网IP>:8080/（需同一 WiFi，且防火墙放行 8080）

防火墙规则已经加过了（规则名 `fit-tracker-8080`）。没加过的话用管理员 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "fit-tracker-8080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080
```

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `index.html` | **整个 App**（HTML + CSS + JS 全在一个文件里） |
| `manifest.json` | PWA 清单，让手机能装到主屏幕全屏运行 |
| `.nojekyll` | 告诉 GitHub Pages 不要用 Jekyll 处理，避免文件被忽略 |
| `README.md` | 本文件 |
| `_serve.js` | 本地预览服务（部署不需要，但留着方便） |
| `_test.js` | 逻辑测试 203 项（开发用） |
| `_static_test.js` | 静态校验 36 项（开发用） |

---

## 开发

```powershell
node _test.js          # 逻辑测试 203 项
node _static_test.js   # 静态校验 36 项
node _serve.js 8080    # 本地预览
```

改完 `index.html` 跑一遍两个测试，全绿再 push。

---

## 算法出处

所有公式都来自公开文献，不是自创：

| 项目 | 模型 |
|---|---|
| BMR 基础代谢 | Mifflin-St Jeor 1989 |
| BMI | WHO 标准 |
| 体脂率 | Deurenberg 1991（R²=0.79，SEE=4.1%） |
| 体脂率（可选更准） | US Navy 围度法（SEE 3~4%）／ RFM Woolcott 2018 |
| 脂肪 / 肌肉分配 | Forbes 模型（Thomas 2010 男性拟合 FFM = 13.8·ln(FM) + 16.9） |
| 能量密度 | ED(FM) = 9440.7 − 7624.3 × 10.4/(FM + 10.4)，替代硬编码 7700 |
| 代谢适应 | Hall EBMM：dAT/dt = (0.14·ΔEI − AT)/14 |
| 保肌系数 | 抗阻训练 Sardeli 2018（消除 93.5% LBM 损失）／ 蛋白 Krieger 2006（阈值 1.05 g/kg）／ 睡眠 Nedeltcheva 2010 ／ 缺口 Murphy & Koehler 2022（>500 kcal/日 有害） |

---

## 数据在哪

**只存在这台手机的浏览器里**（localStorage），不上传任何服务器。

- 设置页可以**导出 / 导入 JSON**
- **换手机或清缓存之前，一定要先导出**
- 导入时按日期逐条合并：**同一天保留完成度更高的那条，本地历史永不覆盖**

---

## 功能清单

**今日**：统一时间轴（五个时段：上午/中午/下午/晚上/睡前）· 环形完成度 · 补水点阵 · 步数 · 断签补救 · 到点提醒

**体重**：17:00 记录 · Canvas 折线图（单日点 + 7 日均线 + 目标线）

**进度**：主目标进度 · 已减/还差/预计达标日 · **肌肉守护分**（含算法解释与激励机制）

**模拟**：切换「满分计划 / 按今天实际」看 30 天后的体重、BMI、体脂、脂肪与肌肉 · **每个选择不做的后果表** · 过去两周实际 vs 满分

**训练**：全自动计时器（热身→4 动作→休息→拉伸，共 590 秒）· 平板支撑正计时 · 动作要领 · 原地踏步计时器

**日历**：30 天满勤/部分/断签总览 · 连续天数统计

**设置**：身体参数（身高/年龄/性别/体重）· 目标 · 提醒时间（含训练时间）· 导出导入 · 份量速查
