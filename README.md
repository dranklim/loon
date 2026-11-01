# Loon 配置与插件

个人维护的 [Loon](https://nsloon.app)（iOS/tvOS 网络代理工具）配置与插件集合。

---

## 📁 配置文件：Loon_Advanced.conf

基于 kelee.one 配置深度修复与增强，适用于 Loon 3.2.5 (789)+

**主要特性：**
- 🔒 **安全**：已移除硬编码 CA 证书私钥（需在 App 内重新生成）；DNS 防泄漏（hijack-dns 劫持 53 端口 + DoH/DoH3 加密 + 纯公共 DNS 上游 + real-ip 例外）
- 🛠️ **修复**：原配置笔误（"XX手动场景"→"XX手动策略"）、截断 URL、重复/失效规则、弃用参数
- ⚡ **策略**：url-test / fallback / select 命名与类型一致；兜底策略 fallback 自动选可用节点，全挂自动落 DIRECT 不断网
- 🇨🇳 **分流**：国内规则全覆盖（ChinaMax/ChinaIPs/ChinaASN + 20+ 应用级直连）；国外按应用分流
- 🚫 **去广告**：完整插件体系（B 站 / 京东 / 淘宝 / 微信小程序 / YouTube 等）

### 一键导入（iOS 上直接点击即可）

[⬇️ 一键导入配置 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?sub=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Fconfig%2FLoon_Advanced.conf)

[⬇️ 一键导入配置 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?sub=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Fconfig%2FLoon_Advanced.conf)

### 导入后必做
1. **MitM 证书**：设置 → MitM → 生成证书 → 安装描述文件 → 设置中信任（配置已移除私钥，必须重新生成）
2. **添加节点订阅**：配置不含订阅（[Remote Proxy] 为空），在 App 内自行添加
3. **可选**：透明代理路由器直连需自行添加 `ssid-trigger`（见配置内注释）

---

## 📁 插件

### 📐 命名与格式规范

- **扩展名统一 `.lpx`** —— Loon 官方标准。官方文档的 `#!source` 校验示例、插件加密器、语法转换器一律以 `.lpx` 为例（转换器输入格式明列 `.lpx · .plugin · .conf · .txt`）。`.plugin` 属传统后缀，Loon 仍能识别，但**本仓库新增插件不再使用**。
- **一律明文，不做加密。** `.lpx` 后缀**不代表**加密 —— 官方「插件加密器」输出的同样是这个后缀，两者后缀相同、内容有别。本仓库所有插件均为可读明文，用任意文本编辑器都能逐行审阅规则，不引入无法审计的黑盒配置。
- **文件名格式 `<目标>_<用途>.lpx`**：`HP_Clean.lpx`（虎扑净化）、`Dongqiudi_remove_ads.lpx`（懂球帝去广告）、`SkipProxy_anti_detect.lpx`（防 VPN 检测）。
- **新增插件必须同步更新**：`README.md` 的说明与导入链接；若上了 `docs/` 页面也要更新该页链接。历史上 `.plugin → .lpx` 是破坏性改名，旧链接会 404。
- **发布前跑一遍隐私扫描**：SSID / Wi-Fi 名称、内网 IP、自有域名、证书私钥（`ca-p12`）、API key、邮箱、手机号，以及 git 历史（提交后仍可回溯）。

### Dongqiudi_remove_ads — 懂球帝去广告

规则层拦截广告服务器（dab.dongdianqiu.com / uranus.jd.com 等）+ 脚本层清理数据广告位（热评伪装广告 / 详情页广告位）。

### 一键导入（iOS 上直接点击即可）

[⬇️ 一键导入懂球帝去广告插件](https://www.nsloon.com/openloon/import?plugin=https://raw.githubusercontent.com/dranklim/loon/main/plugins/Dongqiudi_remove_ads.lpx)

### 要求
- Loon 3.2.5 (789)+
- 需启用 MitM（脚本处理 HTTPS 响应需要）

---

### RiskBlock_IPRewrite — 风控上报 IP 拦截（IP Rewrite）

在 TUN 层拦截 **IP 直连**的风控/上报端点（如平安口袋银行 `45.65.23.16:8443/v3/report`）。用 Loon 3.5.3 新增的 `[IP Rewrite]` 模块实现——它在数据包进入 TUN 后**先于一切规则处理**，因此可以放进插件分发，不受「本地 [Rule] > 插件 > 订阅」优先级和订阅 ChinaIPs DIRECT 抢先的影响（旧机制下插件里的 IP 类 REJECT 会静默失效，只能写进主配置本地 [Rule]）。

默认动作 `drop`（静默丢包）——比 REJECT 的「404 空体 + 毫秒级」响应更不像本地拦截。想快速失败就把该行改成 `reject`。

### 一键导入（iOS 上直接点击即可）

[⬇️ 一键导入风控拦截插件 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Fplugins%2FRiskBlock_IPRewrite.lpx)

[⬇️ 一键导入风控拦截插件 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Fplugins%2FRiskBlock_IPRewrite.lpx)

### 要求
- **Loon 3.5.3 (1007)+**（`[IP Rewrite]` 为 3.5.3 新增模块）
- 无需 MitM（纯 IP 层处理，不经过规则匹配/脚本）

---

## 📁 规则订阅（rules/）

### civitai.list — civitai.red 分流

基于 civitai.red 站点 JS 逆向 + 实测验证（2026-08-18）：civitai.red / civitai.com / image.civitai.com 等走 PROXY。

### civitai_ads.list — civitai.red 去广告

基于同一逆向：Snigel AdNgin 广告引擎（cdn.snigelweb.com）、Google Ad Manager/DoubleClick、AnyClip 视频广告、GTM/GA 埋点整域拦截；自营广告曝光打点（/api/v1/view）URL-REGEX 拦截。

> ⚠️ **远程规则订阅的策略在导入时选择，文件内不写策略**。若用 `?rules=` 导入，导入时策略必须选 **REJECT**；或直接引用：`https://raw.githubusercontent.com/dranklim/loon/main/rules/civitai_ads.list, policy=REJECT, tag=civitai_ads, enabled=true`
>
> ✅ **推荐用插件版**（plugins/Civitai_remove_ads.lpx），REJECT 内置，一键导入即生效，无需选策略。

### 一键导入（iOS 上直接点击即可）

[⬇️ 一键导入 civitai 分流规则 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Frules%2Fcivitai.list)

[⬇️ 一键导入 civitai 分流规则 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Frules%2Fcivitai.list)

[⬇️ 一键导入 civitai 去广告规则 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Frules%2Fcivitai_ads.list)

[⬇️ 一键导入 civitai 去广告规则 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Frules%2Fcivitai_ads.list)

### Civitai_remove_ads.lpx — civitai.red 去广告插件（推荐）

REJECT 策略内置，一键导入即生效，无需手动选策略。

[⬇️ 一键导入去广告插件 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Fplugins%2FCivitai_remove_ads.lpx)

[⬇️ 一键导入去广告插件 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Fplugins%2FCivitai_remove_ads.lpx)

### SkipProxy_anti_detect.lpx — 银行/运营商 App 防 VPN 检测（推荐）

解决银行 App 弹"网络环境存在安全风险"（农业银行实测有效）。核心：REJECT 农行 msmp 风控上报端点（App 检测到 TUN 会向 msmp.abchina.com.cn 上报，切断上报通道即不弹）+ skip-proxy/real-ip 直连白名单（建行/邮储/电信一键登录/交管12123 等）。源自 mieqq/skip-proxy-lists.sgmodule 改写。

[⬇️ 一键导入防检测插件 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Fplugins%2FSkipProxy_anti_detect.lpx)

[⬇️ 一键导入防检测插件 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Fplugins%2FSkipProxy_anti_detect.lpx)

---

### HP_Clean — 虎扑去广告

参考 [ZenmoFeiShi/Qx](https://github.com/ZenmoFeiShi/Qx) 的 `HP.snippet`（QuantumultX）改写为 **Loon Rewrite v2** 语法，10 条规则覆盖：图库入口、未读红点、热门标签/排行榜、搜索热搜、插屏广告、比分 Tab 与位置横幅、首页顶部轮播、预览页横幅、论坛冗余入口（个性换肤/专家预测/邀请好友/版主中心/JRs战术板/草稿箱/58同城 与「我的应用」卡片）、用户页 VIP 卡片。

**相比原片段的改进：**
- 🔧 **修掉写死的版本号**：原片段把两条规则的路径钉死成 `/3/8.0.86/`，App 一升级就失效（比分 Tab 和位置横幅会重新冒出来）。本插件所有规则的版本段统一改为通配 `\d+/[0-9.]+`，升到 9.x / 10.x 都不用改。
- 🎛️ **10 项独立开关**（`[Argument]`）：原片段只能整份启用/停用，删多了没法逐项定位。现在哪一项有问题就单独关掉它。
- 🧩 **请求阶段用 `reject_dict(200)`**：让 App 拿到合法空 JSON `{}`，比 404 或空 body 更不容易触发异常分支。图库那条仍用 `reject(200)` 空体（置空的是「模块入口」而非数据接口）。
- 🛡️ **响应阶段统一 `response.json.*`**：只在 body 是合法 JSON 时才改写，接口返回错误页时自动跳过，不会把响应改坏。

### 一键导入（iOS 上直接点击即可）

[⬇️ 一键导入虎扑净化插件 · jsdelivr 镜像（国内直连）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fdranklim%2Floon%40main%2Fplugins%2FHP_Clean.lpx)

[⬇️ 一键导入虎扑净化插件 · raw 链接（需代理）](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fdranklim%2Floon%2Fmain%2Fplugins%2FHP_Clean.lpx)

### 要求
- **Loon 3.5.1 (978)+**（`[Rewrite]` v2 语法；`[Argument]` 需 Build 733+）
- 需启用 MitM 并信任证书 —— 否则 HTTPS 无法解密，所有规则静默失效

---

## License
MIT
