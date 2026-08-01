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

### 一键导入（Loon 内打开链接）

**raw 链接（需代理）：**
```
loon://import?url=https://raw.githubusercontent.com/dranklim/loon/main/config/Loon_Advanced.conf
```

**jsdelivr 镜像（国内直连，无需代理）：**
```
loon://import?url=https://gcore.jsdelivr.net/gh/dranklim/loon@main/config/Loon_Advanced.conf
```

### 导入后必做
1. **MitM 证书**：设置 → MitM → 生成证书 → 安装描述文件 → 设置中信任（配置已移除私钥，必须重新生成）
2. **添加节点订阅**：配置不含订阅（[Remote Proxy] 为空），在 App 内自行添加
3. **可选**：透明代理路由器直连需自行添加 `ssid-trigger`（见配置内注释）

---

## 📁 插件

### Dongqiudi_remove_ads — 懂球帝去广告

规则层拦截广告服务器（dab.dongdianqiu.com / uranus.jd.com 等）+ 脚本层清理数据广告位（热评伪装广告 / 详情页广告位）。

### 一键导入（Loon 内打开链接）

```
loon://import?plugin=https://raw.githubusercontent.com/dranklim/loon/main/plugins/Dongqiudi_remove_ads.plugin
```

### 要求
- Loon 3.2.5 (789)+
- 需启用 MitM（脚本处理 HTTPS 响应需要）

---

## License
MIT
