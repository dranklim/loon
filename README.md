# Loon 配置与插件集

个人维护的 [Loon](https://nsloon.app) (iOS/tvOS 网络代理工具) 配置与插件集合。

## 📁 config/ — 进阶配置

`Loon_Advanced.conf` — 基于 kelee.one 配置深度修复与增强，适用于 Loon 3.2.5 (789)+

**主要特性：**
- 🔒 **安全**：移除硬编码 CA 证书私钥（需自行在 App 内重新生成）；DNS 防泄漏（hijack-dns 劫持 53 端口 + DoH/DoH3 加密 + 纯公共 DNS 上游 + real-ip 例外）
- 🛠️ **修复**：原配置笔误、截断 URL、重复/失效规则、弃用参数
- ⚡ **策略**：url-test / fallback / select 命名与类型一致；兜底策略 fallback 自动选可用节点，全挂自动落 DIRECT 不断网
- 🇨🇳 **分流**：国内规则全覆盖（ChinaMax/ChinaIPs/ChinaASN + 20+ 应用级直连）；国外按应用分流
- 🚫 **去广告**：完整插件体系（B 站/京东/淘宝/微信小程序/YouTube 等）

### 使用方法
1. 复制配置文件到 Loon：配置 → 从 URL 下载配置
   ```
   https://raw.githubusercontent.com/dranklim/loon/main/config/Loon_Advanced.conf
   ```
2. **必须**在 Loon App 内：设置 → MitM → 生成证书 → 安装描述文件 → 设置中信任
3. 自行添加节点订阅（配置不含订阅，[Remote Proxy] 为空）
4. 可选：透明代理路由器直连需自行添加 `ssid-trigger`（见配置内注释）

## 📁 plugins/ — 插件

| 插件 | 说明 |
|------|------|
| `Dongqiudi_remove_ads.plugin` | 懂球帝去广告：规则层拦截广告服务器 + 脚本层清理数据广告位 |

### 一键导入（Loon 内打开）
```
loon://import?plugin=https://raw.githubusercontent.com/dranklim/loon/main/plugins/Dongqiudi_remove_ads.plugin
```

## License
MIT
