# 懂球帝去广告 (Dongqiudi AdBlock)

懂球帝去广告 Loon 插件：规则层拦截广告服务器，脚本层清理数据层广告位。

## 功能

### 规则层（直接拦截广告服务器）
| 规则 | 目标 |
|------|------|
| `DOMAIN-SUFFIX,dab.dongdianqiu.com,REJECT` | 懂球帝广告服务器（track 追踪 / imp 曝光 / click 点击） |
| `DOMAIN-SUFFIX,uranus.jd.com,REJECT` | 京东广告 SDK 日志上报 |
| `URL-REGEX,^https?:\/\/api\.m\.jd\.com\/\?appid=yinliu,REJECT` | 京东引流广告 API |

### 脚本层（清理数据层广告位）
`dqd_ad.js` 按 URL 分发处理：
- **评论接口** `api.dongdianqiu.com/v2/article/{id}/comment`：过滤 `user_list`/`recommend_list` 中 `role="ad_dplus"` 的广告位（如"懂球帝热评小助手"，伪装热评用户跳转 VIP 广告页）
- **详情接口** `detail.dongdianqiu.com/v2/article/detail/{id}`：清空 `dqd_ads` 广告位，强制 `not_show_m_ad=1`、`account.show_ad=0`

## 安装

### 方式一：一键导入（推荐）
```
loon://import?plugin=https://raw.githubusercontent.com/dranklim/loon/main/plugins/Dongqiudi_remove_ads.plugin
```

### 方式二：手动
1. 配置 → 插件 → 添加
2. 填入 `https://raw.githubusercontent.com/dranklim/loon/main/plugins/Dongqiudi_remove_ads.plugin`

## 要求
- Loon 3.2.5 (789)+（规则层脚本依赖）
- 需启用 MitM（[Script] 处理 HTTPS 响应需要）

## License
MIT
