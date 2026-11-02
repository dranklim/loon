#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qx2loon.py — 把 ZenmoFeiShi/Qx 仓库下的 QuantumultX snippet 批量转换成 Loon 插件（.lpx）

版本: 1.2.0

改动记录（本脚本已纳入本仓库 scripts/qx2loon.py，与 loon 插件同源维护）
    1.2.0  2026-11-02  可用性保障（上游更新不再能悄悄搞坏插件）
                       · --fetch 曾跳过已存在文件 → 上游改过的 snippet/js 永远拉不到新版，
                         --build 静默产出旧插件。改为无条件重下（临时文件 + os.replace，
                         失败时保留旧文件）
                       · PLUGIN_JQ_AUGMENTS：上游缺失的增强（KuAn 开屏清除）以**追加**
                         方式拼到上游 jq 末尾。手改生成物 .lpx 会被 --build 整条静默覆盖
                       · append 与 relax 分开计数。曾共用 hit：relax（api\\d* 放宽）在任何
                         规则上都能命中，会把 append 失配完全掩盖
                       · append 失配时不再写增强说明注释（注释声称已做开屏清除、实际没做）
                       · verify_plugins()：构建后校验 —— 空插件 / [Mitm] 空 hostname /
                         URL 正则编译失败 / 增强指纹缺失（must_contain）全部阻断，退出码 1
                       · 与已发布版本做内容级对比：区分「已修改 / 新增 / 消失 / 条目减少」，
                         同一条规则改了 action 不再误报成一删一增
                       · jq 语法校验（编译错误码 3，区别于运行时错误 5）
    1.1.0  2026-11-01  缓存与输出迁出 /tmp
                       原因: /tmp 被清理后 --build 不报错、静默产出 0 个文件
                       CACHE: /tmp/qx      → ~/.hermes/cache/qx
                       OUT:   /tmp/qx_lpx  → ~/.hermes/cache/qx_lpx
    1.0.0  2026-10-31  首版，27 个 snippet 全量转换
                       · 16 种 QX 语法映射
                       · PLUGIN_ARGS 参数化（把与去广告无关的规则做成默认关闭的开关）
                       · EXTERNAL_JS 凭据隔离（含上游 token/邮箱的 JS 不镜像）

用法：
    python3 qx2loon.py --fetch                # 拉取全部 snippet 与配套 JS 到本地缓存
    python3 qx2loon.py --build                # 生成全部 lpx 到 out/
    python3 qx2loon.py --build --only MT,WB   # 只生成指定插件
    python3 qx2loon.py --report               # 打印每个插件的转换统计与告警

语法映射（QX → Loon）
    host, a.com, reject                  → [Rule]    DOMAIN,a.com,REJECT
    host-suffix, a.com, reject           → [Rule]    DOMAIN-SUFFIX,a.com,REJECT
    host-wildcard, *.a.com, reject       → [Rule]    DOMAIN-WILDCARD,*.a.com,REJECT   (Loon 1008+)
    ip-cidr, 1.2.3.4/32, reject          → [Rule]    IP-CIDR,1.2.3.4/32,REJECT
    ip6-cidr, ::1/128, reject            → [Rule]    IP-CIDR6,::1/128,REJECT
    ^re url reject                       → [Rewrite] request if ... then reject(404)
    ^re url reject-200                   → [Rewrite] request if ... then reject(200)
    ^re url reject-dict                  → [Rewrite] request if ... then reject_dict(200)
    ^re url reject-img                   → [Rewrite] request if ... then reject_img(200)
    ^re url jsonjq-response-body 'JQ'    → [Rewrite] response if ... then response.json.jq(`JQ`)
    ^re url 302 <target>                 → [Rewrite] request if ... then redirect("<target>")
    ^re url request-header ...           → [Rewrite] request if ... then request.header.set(...)
    ^re url script-response-body <js>    → [Script]  response if ... then script("<js>") with requires_body=true
    ^re url script-request-body <js>     → [Script]  request  if ... then script("<js>") with requires_body=true
    ^re url script-request-header <js>   → [Script]  request  if ... then script("<js>")
    ^re url script-echo-response <js>    → [Script]  response if ... then script("<js>") with requires_body=true
    hostname = a, b                      → [Mitm]    hostname = a, b

设计取舍：
    · JS 一律镜像到本仓库 scripts/qx/ 并通过 jsdelivr 引用 —— 原地址是 raw.githubusercontent，
      国内直连常失败，且依赖原作者不删文件；镜像我方可控，监控脚本同时盯 JS 变化。
    · 严格保留上游规则顺序；仅对「同 phase + 同 action + 同参数」的 URL 规则做合并。
    · 转不了的语法不猜，进 warnings 并在插件里留注释，避免静默丢规则。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "ZenmoFeiShi/Qx"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
TREE_API = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"

# 缓存与输出放在持久目录，不放 /tmp：
# /tmp 会被系统或人工清理，清掉后 --build 会因缓存为空生成 0 个插件。
# 放在 ~/.hermes/cache/ 下与其他缓存统一管理，也让 --fetch 的下载成果可复用。
CACHE = os.path.expanduser("~/.hermes/cache/qx")        # 上游 snippet + js 原文
OUT = os.path.expanduser("~/.hermes/cache/qx_lpx")      # 生成的 lpx
MIRROR_BASE = "https://raw.githubusercontent.com/dranklim/loon/main/scripts/qx"   # 统一 raw，不用 jsdelivr
ICON_BASE = "https://raw.githubusercontent.com/dranklim/loon/main/assets"   # 统一 raw，不用 jsdelivr

# ── 可参数化规则 ──────────────────────────────────────────────
# 上游某些规则与「去广告」无关（如伪造个人资料），不应默认生效。
# 这里把它们挂到 [Argument] 开关后面：默认关闭，用户可在 Loon 里单独打开。
# 结构: {插件名: [ {id, default, tag, desc, match(URL 子串，用于定位规则)} ]}
PLUGIN_ARGS = {
    "KuAn": [
        dict(id="fakeProfile", default="false", tag="伪造个人资料",
             desc="把等级改20/粉丝99999/经验94575543，与去广告无关，默认关闭",
             match="user\\/profile"),   # 规则里 URL 已转义，需带反斜杠
    ],
}

# ── 上游缺失、但实测必需的增强规则 ────────────────────────────
# 手改生成物 .lpx 会在下一次 --build 被静默覆盖（生成物看着正常，只是增强没了），
# 所以任何手写增强都必须回灌到这张表里。
# 结构: {插件名: [ {match(定位含该子串的 jq 规则), append(追加到该 jq 末尾),
#                   relax((旧串,新串) 放宽 URL 正则), mitm_add([补 Mitm 主机]),
#                   note([段外说明行])} ]}
# append 语义是「追加」而非「替换」：上游 jq 逻辑变化时增强不受影响。
PLUGIN_JQ_AUGMENTS = {
    "KuAn": [
        dict(
            match="main\\/init",
            append=(
                ' | .data |= map(select(.entityTemplate != "imageCard"))'
                ' | .data |= map(if (.entityId|tostring) == "6390" and .extraDataArr != null then'
                ' (.extraDataArr["SplashAd.Type"] = "")'
                ' | (.extraDataArr["SplashAd.hType"] = "")'
                ' | (.extraDataArr["SplashAd.resumeType"] = "")'
                ' | (.extraDataArr["SplashAd.timeout"] = "0")'
                ' | (.extraDataArr["SplashAd.Expires"] = "2147483647")'
                ' | (.extraDataArr["SplashAd.resumeExpires"] = "2147483647")'
                ' | (.extraDataArr["SplashAd.onResume"] = "0")'
                ' | (.extraDataArr["Ad.SPLASH_RETRY_PERIOD"] = "2147483647")'
                ' | (.extraDataArr["Ad.PRELOAD"] = "0")'
                ' | (.extraDataArr["Ad.SPLASH_DOWNLOAD_POPUP"] = "0")'
                ' else . end)'
            ),
            relax=("api\\.coolapk\\.com", "api\\d*\\.coolapk\\.com"),
            mitm_add=["api2.coolapk.com"],
            # 独立校验指纹：verify 只认生成物里真实出现的字符，不依赖 append 的命中计数
            must_contain=[
                "SplashAd.Type", "SplashAd.hType", "SplashAd.resumeType",
                "Ad.SPLASH_RETRY_PERIOD", "imageCard",
                "api\\d*\\.coolapk\\.com", "api2.coolapk.com",
            ],
            note=[
                "# ★ 开屏广告清除（本仓库增强，上游 snippet 没有）",
                "#   实测依据：2026-11-01 真机冷启动抓包，酷安 16.7.1（x-app-code 2610291）。",
                "#   /v6/main/init 的 data 只有 configCard，没有 imageCard；开屏由「首页」配置卡",
                "#   entityId=6390 的 extraDataArr 下发，实测值：",
                '#     SplashAd.Type = "GM_SPLASH | 5156243 | 102140761"（广点通开屏）',
                "#     SplashAd.Expires = 900   ← 15 分钟，这就是「划掉后台过一会重开又弹」的根源",
                "#     Ad.SPLASH_RETRY_PERIOD = 300 / onResume=1 / resumeExpires=60 / timeout=4000",
                "#   → 所有 SplashAd.* 类型清空、超时归零、周期拉满、onResume 关掉、关预加载；",
                "#     imageCard 一并删（本版没有，兼容其他版本与安卓端）",
                "#   → 规则正则放宽到 api\\d* 并补 Mitm api2（部分接口走 api2）",
            ],
        ),
    ],
}

# snippet 名 → (中文名, App Store 图标文件名 or None, 补充说明)
META = {
    "Cwkj":                 ("菜鸟裹裹", "cainiao", "play.wo1wan.com"),
    "Didichuxing":          ("滴滴出行", "didi", None),
    "HP":                   ("虎扑", "hupu", None),
    "Keep":                 ("Keep", "keep", None),
    "KuAn":                 ("酷安", "coolapk", None),
    "MT":                   ("美团", "meituan", None),
    "Pinduoduo":            ("拼多多", "pinduoduo", None),
    "SF":                   ("顺丰速运", "sf", None),
    "Smzdm":                ("什么值得买", "smzdm", None),
    "Soul":                 ("Soul", "soul", None),
    "T3":                   ("T3出行", "t3", None),
    "TB":                   ("百度贴吧", "tieba", None),
    "TH":                   ("途虎养车", "tuhu", None),
    "TilingSales_ad_remove": ("TilingSales", "tilingsales", None),
    "TxvideoAD":            ("腾讯视频", "txvideo", None),
    "txsports-ad-clean":    ("腾讯体育", "txsports", None),
    "WB":                   ("微博", "weibo", None),
    "WxPureDominion":       ("微信净化", "wechat", None),
    "Youtube":              ("YouTube", "youtube", None),
    "Yt-zh":                ("YouTube 字幕", "youtube", None),
    "bili_view_ad_rewrite":  ("哔哩哔哩", "bilibili", None),
    "helloobike":           ("哈啰", "hellobike", None),
    "hlwxx_remove_ads":     ("黑料网净化", "hlwxx", None),
    "mgtv_vip":             ("芒果TV", "mgtv", None),
    "migu_vip_share":       ("咪咕视频", "migu", None),
    "xTerm256":             ("iTunes 净化", "xterm256", None),
    "xhey-ad-clean":        ("小红书", "xiaohongshu", None),
    "xzimu-unlock":          ("字幕解锁", "xzimu", None),
}

# 每个插件实际去掉的内容 —— 写进 #!desc 和插件内的「去除内容」块。
# 使用者关心的是「去掉了哪些广告」，不是「源文件是什么格式、转了几条语法」，
# 所以描述里不出现 QX / 转换 / 语法 这类字眼。
# 结构：{插件名: (desc 用的短句, [配置块内逐条展开的内容])}
ADS = {
    "Cwkj": ("内嵌游戏中心的等级与 VIP 标识",
             ["菜鸟裹裹内嵌游戏中心（play.wo1wan.com）的等级与 VIP 字段改为满级"]),
    "Didichuxing": ("活动弹窗、信息流与广告追踪域名",
                    ["活动弹窗与运营位（resapi/activity）",
                     "首页信息流推广（ct/agent/v3/feeds）",
                     "广告追踪域名（gwp.xiaojukeji.com）与上报 IP 段"]),
    "HP": ("开屏与信息流广告",
           ["广告接口（goblin.hupu.com/interfaceAd）",
            "首页 / 画廊推荐模块（getmod2）",
            "板块列表、评论与搜索中的推广位"]),
    "Keep": ("广告接口与搜索热词",
             ["广告请求（op-engine-webapp/v1/ad、kad.gotokeep.com）",
              "搜索热词、热门课程与话题推荐",
              "消息中心里的推广会话"]),
    "KuAn": ("开屏、信息流与搜索热搜",
             ["启动开屏广告（SplashAd 全套开关：类型、超时、重试周期、切回前台）",
              "首页与列表信息流广告卡片",
              "搜索页热搜推荐词",
              "「伪造个人资料」为独立开关，默认关闭"]),
    "MT": ("广告追踪域名与上报地址",
           ["广告与埋点域名（shark-*.meituan.com / shark-*.sankuai.com / shark.dianping.com）",
            "HTTPDNS 多活解析接口",
            "广告上报 IP 段与 QUIC 变体域名"]),
    "Pinduoduo": ("首页推荐、搜索推广与活动弹窗",
                  ["首页推荐位与广告插槽（alexa/homepage）",
                   "搜索结果中的推广商品",
                   "个人中心营销模块",
                   "活动弹窗与运营下发（caterham / oak / engels）"]),
    "SF": ("信息流广告、推荐与积分商城商品",
           ["信息流广告（base/app/ad/queryInfoFlow）",
            "推荐内容（bms/queryRecommend）",
            "视频页推荐标签、积分商城商品推荐"]),
    "Smzdm": ("开屏 loading、横幅广告与推荐模块",
              ["开屏 loading 数据（util/loading）",
               "首页横幅与挂件广告（banner_v2 / widget）",
               "好价列表中的广告行",
               "详情页第三方与百科相关推荐模块"]),
    "Soul": ("广场推荐、聊天引导与开屏运营位",
             ["广场推荐与广告位（ssp/api/q）",
              "聊天页快捷菜单、引导语与入口推荐",
              "直播星球推荐列表",
              "开屏与活动运营配置"]),
    "T3": ("活动弹窗与广告位",
           ["广告接口（passenger-activity-api/api/ad）",
            "实时弹窗与运营位（open-app-api/api/intime）",
            "活动中心推广与无 token 接口下发"]),
    "TB": ("广告域名、搜索发现与直播 feed 推广",
           ["百度广告域名（afd / mobads.baidu.com）",
            "搜索发现与吧引导推荐（search/discover、forumGuide）",
            "直播 feed 中的横幅与侧栏推广",
            "聊天页订阅推广"]),
    "TH": ("营销弹窗、横幅、超级会员与搜索热词",
           ["营销弹窗与活动方案（mkt-scene-marketing-service）",
            "首页 banner 与门店 Tab 横幅",
            "超级会员推广配置（getAutoSuperConfig）",
            "圈子推荐、搜索热词与商品推荐位"]),
    "TilingSales_ad_remove": ("开屏、浮窗、插屏与横幅广告",
                              ["开屏广告（App/Ad/splashInfo）",
                               "首页浮窗与横幅（homeFloatAd / bannerInfo）",
                               "插屏与短剧广告（skitAdInfo）",
                               "弹窗计数、公告位与广告配置下发"]),
    "TxvideoAD": ("广告 SDK 配置编排",
                  ["广告 SDK 配置接口（rdelivery.qq.com/v1/sdkconfig），"
                   "阻断后客户端拿不到广告编排",
                   "会员入口与会员专区模块（vip_entrance）"]),
    "txsports-ad-clean": ("开屏、首页广告与底部会员 tab",
                          ["开屏广告编排（app.sports.qq.com/init/config）",
                           "首页推荐位与广告（homePageV2）",
                           "广告 SDK 配置（k.ssp.qq.com/getsdkconfig）",
                           "底部会员 tab 与首页展示优化"]),
    "WB": ("信息流广告、搜索推广与推送运营",
           ["信息流广告卡片（container_detail / container_timeline）",
            "搜索页推广内容（search/container_timeline）",
            "推送运营消息（push/active）",
            "个人资料页与未读容器中的推广位"]),
    "WxPureDominion": ("小程序内的营销弹窗与会员推广",
                       ["小桔充电小程序的活动页、资源位与会员推广",
                        "云快充城市配置与企业微信配置推广",
                        "同程（wx.17u.cn）首页聚合推荐与 banner",
                        "各小程序营销弹窗与跳转引导"]),
    "Youtube": ("视频广告、首页 Shorts 与内嵌推荐卡",
                ["视频前贴片与中插广告（googlevideo / oad）",
                 "广告统计上报（stats/ads、pagead、qoe）",
                 "首页 Shorts 区块",
                 "播放页内嵌的购物与商品推荐卡"]),
    "Yt-zh": ("字幕接口解锁",
              ["解锁 YouTube 字幕接口（timedtext）的中文字幕请求"]),
    "bili_view_ad_rewrite": ("开屏、播放器广告、搜索热词与动态推广",
                             ["开屏与播放页广告（View/View、PlayViewUnite）",
                              "搜索默认词与热词推荐（Search/DefaultWords）",
                              "热门页与动态页推广卡片（Popular/Index、DynAll）",
                              "广告转化与投放统计（cm.bilibili.com）"]),
    "helloobike": ("开屏素材配置与广告密钥",
                   ["开屏广告素材配置 JSON（resource.51downapp.cn）",
                    "广告密钥下发接口（api.hellobike.com/secretkey）"]),
    "hlwxx_remove_ads": ("网页浮窗、弹窗广告与统计上报",
                         ["页面浮窗广告脚本（adfloat.js）",
                          "底部广告轮询脚本（bottom_ad_poll.js）",
                          "弹窗 feed 数据（popup-feed.json）",
                          "广告统计与事件上报域名"]),
    "mgtv_vip": ("会员视频源解锁",
                 ["解锁会员视频源（mobile-stream.api.mgtv.com/v1/video/source）"]),
    "migu_vip_share": ("会员播放源解锁",
                       ["解锁会员播放源（*.miguvideo.com 播放接口）",
                        "修正 passport / 推送等接口的请求头"]),
    "xTerm256": ("内购收据校验拦截",
                 ["拦截 iTunes 收据校验（verifyReceipt），使应用按已购买处理"]),
    "xhey-ad-clean": ("开屏、第三方广告 SDK 与竞价请求",
                      ["开屏与推广广告（ad.xhey.top/next）",
                       "今日水印相机的全局广告开关（abtest 下发）",
                       "TopOn / AnyThink 广告 SDK（anythinktech、toponadss）",
                       "百度 mobads、快手广告（open.e.kuaishou）",
                       "第三方 ADX 竞价（1rtb、statisticslinks）"]),
    "xzimu-unlock": ("字幕任务会员校验解除",
                     ["解除字幕识别任务的会员状态校验（updateStatus）",
                      "绕过任务离线限制与分段识别接口鉴权"]),
}

# 含上游作者的有效凭据 / 联系方式，不镜像到本仓库（避免扩散），改为直接引用上游地址。
# 代价：国内首次加载可能较慢（走 raw.githubusercontent），但脚本会被 Loon 缓存。
EXTERNAL_JS = {"migu_vip.js", "easybike-ad.js"}

REJECT_MAP = {
    "reject":        "reject(404)",        # QX 裸 reject = 404 空响应
    "reject-200":    "reject(200)",
    "reject-dict":   "reject_dict(200)",
    "reject-array":  "reject_array(200)",
    "reject-img":    "reject_img(200)",
    "reject-video":  "reject_video(200)",
}


def http_get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "qx2loon/1.0"})
    data = urllib.request.urlopen(req, timeout=40).read()
    return data if raw else data.decode("utf-8", "ignore")


def cmd_fetch():
    os.makedirs(CACHE, exist_ok=True)
    tree = json.loads(http_get(TREE_API))
    files = [t["path"] for t in tree["tree"] if t["type"] == "blob"]
    want = [f for f in files if f.endswith((".snippet", ".js"))]
    ok = 0
    for f in want:
        dst = os.path.join(CACHE, f)
        # 必须无条件重下：上游改过的文件若沿用旧缓存，--build 会静默产出旧版插件
        try:
            data = http_get(f"{RAW}/{f}", raw=True)
            tmp = dst + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
            ok += 1
        except Exception as e:
            print(f"  ❌ {f}: {e}")
    print(f"已缓存 {ok}/{len(want)} 个文件 → {CACHE}")


def classify(line):
    """返回 (kind, payload)"""
    s = line.strip()
    low = s.lower()
    for t in ("host-wildcard", "host-suffix", "host-keyword", "host", "ip6-cidr", "ip-cidr", "ip-asn", "geoip"):
        if low.startswith(t + ","):
            return "rule:" + t, s
    m = re.match(r'^(\S+)\s+url\s+(\S+)(?:\s+(.*))?$', s)
    if m:
        return "url:" + m.group(2), (m.group(1), m.group(2), (m.group(3) or "").strip())
    return "unknown", s


def build_rule_line(qx_line):
    """host / ip-cidr 类 → Loon [Rule] 行"""
    parts = [p.strip() for p in qx_line.split(",")]
    if len(parts) < 3:
        return None, f"规则格式异常: {qx_line[:80]}"
    typ, target, policy = parts[0].lower(), parts[1], parts[2]
    if policy.lower() not in ("reject", "reject-200", "reject-dict", "reject-img", "reject-no-drop"):
        return None, f"非 REJECT 策略暂不转换: {qx_line[:80]}"
    ltype = {
        "host": "DOMAIN", "host-suffix": "DOMAIN-SUFFIX",
        "host-wildcard": "DOMAIN-WILDCARD", "host-keyword": "DOMAIN-KEYWORD",
        "ip-cidr": "IP-CIDR", "ip6-cidr": "IP-CIDR6", "ip-asn": "IP-ASN", "geoip": "GEOIP",
    }.get(typ)
    if not ltype:
        return None, f"未知规则类型 {typ}"
    return f"{ltype},{target},REJECT", None


def qx_regex_to_loon(rx):
    """QX 正则里 ^ 可选；Loon 要求锚定开头。其余转义保持原样。"""
    return rx if rx.startswith("^") else "^" + rx


def build_url_line(phase_action, regex, arg, js_map, warns, ctx):
    """URL 类规则 → Loon [Rewrite]/[Script] 行"""
    act = phase_action
    rx = qx_regex_to_loon(regex)

    if act in REJECT_MAP:
        return "request", rx, REJECT_MAP[act]

    if act == "jsonjq-response-body":
        jq = arg.strip()
        if (jq.startswith("'") and jq.endswith("'")) or (jq.startswith('"') and jq.endswith('"')):
            jq = jq[1:-1]
        mdel = re.fullmatch(r'del\(\.([A-Za-z0-9_.\-]+)\)', jq)
        if mdel:
            return "response", rx, 'response.json.delete("%s")' % mdel.group(1)
        if "`" in jq:
            warns.append(f"jq 含反引号，改用双引号: {jq[:50]}")
            return "response", rx, 'response.json.jq("%s")' % jq.replace('"', r'\"')
        return "response", rx, "response.json.jq(`%s`)" % jq

    if act == "302":
        # Loon 签名是 redirect(Number, String)；且 $n 不能跨 Action 用，
        # 需在条件里 as 命名捕获，再把 $1 → ${m.1}
        target = arg.strip()
        cap = ""
        if re.search(r'\$\d', target):
            target = re.sub(r'\$(\d)', r'${m.\1}', target)
            cap = "as m"
        return "request", rx, 'redirect(302, "%s")' % target, cap

    if act == "request-header":
        # 形如: (\r\n)Header:.+(\r\n) request-header $1Header: value$2
        m = re.search(r'request-header\s+(.*)$', arg)
        seg = m.group(1) if m else arg
        seg = re.sub(r'\$\d', '', seg).strip()
        if ":" in seg:
            name, val = seg.split(":", 1)
            return "request", rx, 'request.header.set("%s", "%s")' % (name.strip(), val.strip())
        warns.append(f"request-header 无法解析: {seg[:70]}")
        return None

    if act in ("script-response-body", "script-request-body",
               "script-request-header", "script-echo-response"):
        url = arg.strip()
        fname = os.path.basename(url.split("?")[0])
        mirror = f"{MIRROR_BASE}/{fname}"
        if fname not in js_map:
            # 上游 snippet 引用了仓库里根本不存在的 JS —— 保留规则只会让 Loon 每次 404，
            # 因此注释掉并留下原文，等上游补上文件后重新生成即可恢复
            warns.append(f"上游缺失脚本 {fname}，该规则已注释保留")
            return ("comment", rx,
                    f'# ↑ 原规则调用 {fname}，但上游仓库无此文件，已注释（原 action: {act}）')
        if fname in EXTERNAL_JS:
            # 直接用上游地址，不在本仓库留副本
            ext = f"{RAW}/{fname}"
            if act == "script-request-header":
                return "request", rx, 'script("%s")' % ext
            if act == "script-request-body":
                return "request", rx, 'script("%s") with requires_body=true' % ext
            return "response", rx, 'script("%s") with requires_body=true' % ext
        if act == "script-request-header":
            return "request", rx, 'script("%s")' % mirror
        if act == "script-request-body":
            return "request", rx, 'script("%s") with requires_body=true' % mirror
        return "response", rx, 'script("%s") with requires_body=true' % mirror

    warns.append(f"未支持的 url action: {act}（{rx[:60]}）")
    return None


def validate_jq(body):
    """校验生成物里每条 response.json.jq(`...`) 的语法。

    Loon 的 jq 出错是**静默**的：规则语法合法但结果不对，插件看起来装好了却毫无效果。
    上游改了 jq 结构后，本地 append 的增强可能拼成非法表达式 —— 必须在构建期挡住。
    jq 语法错误退出码是 3，运行时错误是 5，两者要分开（拿 {} 当输入时运行时错误很正常）。
    返回 [(表达式片段, 错误摘要)]。
    """
    try:
        subprocess.run(["jq", "--version"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []          # 本机没有 jq 就跳过，不阻断构建
    bad = []
    for m in re.finditer(r"response\.json\.jq\(`([^`]*)`\)", body):
        expr = m.group(1)
        try:
            r = subprocess.run(["jq", "-c", expr], input="{}", capture_output=True,
                               text=True, timeout=15)
        except subprocess.SubprocessError:
            continue
        if r.returncode == 3:      # 3 = 编译/语法错误；5 = 运行时错误（可忽略）
            bad.append((expr[:70], r.stderr.strip().splitlines()[-1][:120] if r.stderr else ""))
    return bad


def render_plugin(name, qx_text, js_files):
    """生成 lpx 文本"""
    cn, icon, note = META.get(name, (name, None, None))
    warns, rule_lines, rw_lines, sc_lines = [], [], [], []
    pending_comments = []      # 上游缺脚本等需注释保留的规则
    hostname = ""

    for line in qx_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        if s.lower().startswith("hostname"):
            hostname = s.split("=", 1)[1].strip() if "=" in s else ""
            continue
        kind, payload = classify(s)

        if kind.startswith("rule:"):
            ln, w = build_rule_line(payload)
            if ln: rule_lines.append(ln)
            if w: warns.append(w)
        elif kind.startswith("url:"):
            regex, act, arg = payload
            res = build_url_line(act, regex, arg, js_files, warns, name)
            if res:
                if res[0] == "comment":
                    pending_comments.append(res[2])
                    continue
                if len(res) == 4:
                    ph, rx, action, cap = res
                else:
                    ph, rx, action = res
                    cap = ""
                cond = "${url} ~= /%s/" % rx + (" " + cap if cap else "")
                line_out = f"{ph} if {cond} then {action}"
                (sc_lines if action.startswith("script(") else rw_lines).append(line_out)
        else:
            warns.append(f"未识别行: {s[:90]}")

    # ── 参数化：把无关规则挂到 [Argument] 开关后面（默认关闭）──────
    arg_defs = PLUGIN_ARGS.get(name, [])
    for a in arg_defs:
        hit = 0
        for i, line in enumerate(rw_lines):
            if a["match"] in line and "if ${url}" in line:
                rw_lines[i] = line.replace(
                    "if ${url}", f"if ${{{a['id']}}} == true && ${{url}}", 1)
                hit += 1
        if not hit:
            warns.append(f"参数 {a['id']} 未匹配到任何规则（match={a['match']}）")

    # ── jq 增强：上游缺失的规则（开屏等），只追加不改上游逻辑 ──────
    aug_notes = []
    for aug in PLUGIN_JQ_AUGMENTS.get(name, []):
        append_hit = 0
        relax_hit = 0
        if aug.get("append"):
            for i, line in enumerate(rw_lines):
                if aug["match"] not in line or "response.json.jq(`" not in line:
                    continue
                new = re.sub(
                    r"(response\.json\.jq\(`)([^`]*)(`\))",
                    lambda m, sfx=aug["append"]: m.group(1) + m.group(2) + sfx + m.group(3),
                    line, count=1)
                if new != line:
                    rw_lines[i] = new
                    append_hit += 1
        if aug.get("relax"):
            src, dst = aug["relax"]
            for i, line in enumerate(rw_lines):
                if src in line:
                    rw_lines[i] = line.replace(src, dst)
                    relax_hit += 1
        # append 与 relax 必须**各自**成功：曾经共用 hit 计数，relax 在别的规则上命中
        # 会把 append 失配掩盖掉（上游改了接口路径，增强静默丢失且退出码仍是 0）
        if aug.get("append") and not append_hit:
            warns.append(f"!FATAL! 增强 append 未匹配到任何规则（match={aug['match']}）："
                         f"上游可能改了接口路径或删了该规则")
        if aug.get("relax") and not relax_hit:
            warns.append(f"!FATAL! 增强 relax 未命中任何规则（源串 {aug['relax'][0]}）")
        if append_hit:
            # 只有 append 真正落地才写增强说明 —— 失配时写进去等于骗人（注释说有开屏清除，实际没做）
            aug_notes.extend(aug.get("note", []))
        if hostname:
            for h in aug.get("mitm_add", []):
                if h not in [x.strip() for x in hostname.split(",")]:
                    hostname = hostname.rstrip() + ", " + h

    # 上游自己补了开屏处理时，本地 append 会与它重叠 —— 语义上通常仍正确（幂等覆盖），
    # 但值可能冲突，必须人工看一眼再发
    if PLUGIN_JQ_AUGMENTS.get(name) and re.search(r"SplashAd|imageCard", qx_text or ""):
        warns.append("!FATAL! 上游 snippet 已出现开屏关键字（SplashAd/imageCard），"
                     "本地增强可能与之重叠或冲突，需人工核对后再发布")

    # ── 组装插件 ───────────────────────────────────────────
    out = []
    # 名字里不出现「QX 迁移」字样 —— 来源信息放在 desc 与来源声明块里
    # 工具类 / 名字本身已含「净化」「解锁」「字幕」的不再追加「去广告」，避免语义重复
    TOOLISH = ("mgtv", "migu", "xzimu", "Yt-zh", "xTerm")
    NO_SUFFIX = ("净化", "解锁", "字幕")
    cn_disp = cn.replace(" ", "")          # 插件名内一律不留空格
    if name.startswith(TOOLISH) or any(k in cn for k in NO_SUFFIX):
        out.append(f"#!name = {cn_disp}")   # 名字已含净化/解锁/字幕，不重复追加
    else:
        out.append(f"#!name = {cn_disp}净化")
    ads_short, ads_items = ADS.get(name, ("上游规则涉及的广告与推广位", []))
    if name not in ADS:
        warns.append(f"插件 {name} 未在 ADS 表登记「去除内容」，desc 会退化成占位文本")
    # 描述讲「去掉了哪些广告」，不提源格式与转换过程
    out.append(f"#!desc = 参考 ZenmoFeiShi 的去广告脚本：{ads_short}")
    # 多作者用逗号紧接，不能有空格：Loon 会把 "@ " 后的前导空格算进作者名，
    # 显示成 "@ ZenmoFeiShi"（别的单作者插件不会出现这个问题，容易看不出是格式错的）
    out.append("#!author = dranklim,ZenmoFeiShi")
    out.append("#!homepage = https://github.com/dranklim/loon")
    if icon:
        out.append(f"#!icon = {ICON_BASE}/{icon}.png")
    out.append("#!system = iOS,iPadOS")
    out.append("#!loon_version = 3.5.1(983)")
    out.append("#!tag = 去广告,净化")
    out.append("#!type = normal")
    out.append("")
    # 使用者先看到「去掉了什么」，署名放在后面；通篇不提「转换」
    out.append("# " + "=" * 74)
    out.append("# 本插件去除的内容")
    for item in ads_items:
        out.append(f"#   · {item}")
    out.append("# " + "=" * 74)
    out.append("")
    out.append("# " + "=" * 74)
    out.append("# 来源声明 / Attribution")
    out.append(f"#   去广告思路与规则参考开源项目 ZenmoFeiShi/Qx 的 {name}.snippet")
    out.append(f"#   https://github.com/{REPO}/blob/{BRANCH}/{name}.snippet")
    out.append("#   原作者：TG@ZenMoFiShi、怎么肥事、walala（以 snippet 头部 #!author 为准）")
    out.append("#   上游未声明 LICENSE，版权归原作者所有；原作者有异议即行撤下。")
    out.append("#   同步：cron 任务 qx-suite-sync 每日比对上游构建日期与脚本 sha256")
    out.append("# " + "=" * 74)
    out.append("")
    if aug_notes:
        # 增强说明一律写在 [Rewrite] 段外（段内注释不保证被解析器容忍）
        out.append("# " + "=" * 74)
        out.extend(aug_notes)
        out.append("# " + "=" * 74)
        out.append("")

    if arg_defs:
        out.append("# 参数开关（Loon 界面自动生成，默认值见下）")
        out.append("# 关掉 = 对应规则不执行，接口恢复原样")
        out.append("[Argument]")
        for a in arg_defs:
            out.append(f"{a['id']} = switch,{a['default']},tag={a['tag']},desc={a['desc']}")
        out.append("")

    if rule_lines:
        out.append("# 域名 / IP 层拦截（来自 QX host / ip-cidr 规则）")
        out.append("[Rule]")
        out.extend(rule_lines)
        out.append("")

    if rw_lines:
        out.append("# URL 重写（来自 QX url reject-* / jsonjq-response-body）")
        out.append("[Rewrite]")
        out.extend(rw_lines)
        out.append("")

    if pending_comments:
        out.append("# 以下规则因上游缺失对应脚本文件而注释保留（不是本插件出错）")
        out.extend(pending_comments)
        out.append("")

    if sc_lines:
        out.append("# 脚本处理（来自 QX url script-*，JS 已镜像至本仓库 scripts/qx/）")
        out.append("[Script]")
        out.extend(sc_lines)
        out.append("")

    if hostname:
        out.append("[Mitm]")
        out.append(f"hostname = {hostname}")
        out.append("")

    if warns:
        out.append("# ===== 已知限制（部分内容未能启用）=====")
        for w in warns:
            out.append("#   ! " + w)
    return "\n".join(out) + "\n", warns, dict(rules=len(rule_lines), rewrite=len(rw_lines), script=len(sc_lines))


PUBLISHED_DIR = os.environ.get(
    "QX_PUBLISHED_DIR", os.path.expanduser("~/loon_repo/plugins/qx"))   # 已发布版本目录，用作基线对比
# 已知不发布的插件：仓库用的是手写增强版 HP_Clean.lpx，这里的 HP.lpx 只作参考
# ——「全部一致 + 它一个差异」是健康状态，不该每轮都报成噪音
UNPUBLISHED = {"HP"}


def _section_counts(body):
    """按段统计条目数（跳过注释与空行），用于可用性与基线对比。"""
    counts = {"Rule": 0, "Rewrite": 0, "Script": 0, "Argument": 0}
    sec = None
    for ln in body.splitlines():
        s = ln.strip()
        m = re.fullmatch(r"\[(Rule|Rewrite|Script|Argument)\]", s)
        if m:
            sec = m.group(1)
            continue
        if not s or s.startswith("#"):
            continue
        if sec:
            counts[sec] += 1
    return counts


def _substance_lines(body):
    """提取实质规则行（带所属段前缀，跳过注释与段头），用于内容级对比。"""
    out = []
    sec = ""
    for ln in body.splitlines():
        s = ln.strip()
        m = re.fullmatch(r"\[([A-Za-z ]+)\]", s)
        if m:
            sec = m.group(1)
            continue
        if not s or s.startswith("#"):
            continue
        out.append(f"{sec}|{s}")
    return out


def _rule_key(line):
    """规则身份键：phase + URL pattern（去掉 then 之后的 action）。

    同一条规则被上游改了 action（jq 内容微调）时，set diff 会显示成一删一增，
    容易被误读成「规则被删了」。用这个键把两边配对，识别成「已修改」。
    """
    seg = line.split("|", 1)[1] if "|" in line else line
    return seg.split(" then ", 1)[0].strip()


def verify_plugins(only=None):
    """构建后可用性校验：确保上游更新不会让插件悄悄失效。

    致命项（阻断发布，返回非空）：
      1. 缺 #!name；既无规则也无重写也无脚本（空插件）
      2. 有 [Mitm] 但 hostname 为空
      3. 任一 URL 正则编译失败
      4. 声明了 must_contain 的插件，增强指纹在生成物中找不到
    提示项（不阻断，需人工复核）：与已发布版本的条目数增减 / 内容变化 / 新插件
    """
    problems, notes = [], []
    if not os.path.isdir(OUT):
        return ["OUT 目录不存在，构建未产出任何文件"], notes
    for f in sorted(x for x in os.listdir(OUT) if x.endswith(".lpx")):
        name = f[:-4]
        if only and name not in only:
            continue
        body = open(os.path.join(OUT, f), encoding="utf-8").read()
        counts = _section_counts(body)

        if "#!name" not in body:
            problems.append(f"{name}: 缺 #!name")
        if counts["Rule"] + counts["Rewrite"] + counts["Script"] == 0:
            problems.append(f"{name}: 空插件（规则/重写/脚本全为 0），上游可能改版")

        if "[Mitm]" in body:
            m = re.search(r"^hostname\s*=\s*(.*)$", body, re.M)
            if not m or not m.group(1).strip():
                problems.append(f"{name}: [Mitm] 段 hostname 为空")

        for rx in re.findall(r"~= /((?:[^/\\]|\\.)*)/", body):
            try:
                re.compile(rx)
            except re.error as exc:
                problems.append(f"{name}: URL 正则无法编译 → {rx[:50]} ({exc})")

        for aug in PLUGIN_JQ_AUGMENTS.get(name, []):
            for token in aug.get("must_contain", []):
                if token not in body:
                    problems.append(f"{name}: 增强指纹缺失 → {token!r}"
                                    f"（上游改动后本地增强可能已挂不上）")

        pub = os.path.join(PUBLISHED_DIR, f)
        if name in UNPUBLISHED:
            continue                      # 已知不发布，跳过基线对比
        if not os.path.exists(pub):
            notes.append(f"{name}: 新插件（仓库中尚不存在）")
        else:
            old_body = open(pub, encoding="utf-8").read()
            if old_body != body:
                oc = _section_counts(old_body)
                parts = []
                for k in ("Rule", "Rewrite", "Script"):
                    if oc[k] != counts[k]:
                        arrow = "↑" if counts[k] > oc[k] else "↓"
                        parts.append(f"{k} {oc[k]}→{counts[k]}{arrow}")
                        if counts[k] < oc[k]:
                            notes.append(f"⚠️ {name}: {k} 条目减少 {oc[k]}→{counts[k]}，"
                                         f"上游可能删了规则，复核是否功能缺失")
                # 内容级对比：哪几条规则真的变了（这是「上游更新了什么」的答案）
                new_set = set(_substance_lines(body))
                old_set = set(_substance_lines(old_body))
                added = sorted(new_set - old_set)
                removed = sorted(old_set - new_set)
                if not added and not removed:
                    notes.append(f"{name}: 仅注释/格式变化（规则内容未变）")
                    continue
                # 把「同一条规则改了 action」从新增/删除里摘出来，单列成「已修改」
                added_keys = {_rule_key(a) for a in added}
                removed_keys = {_rule_key(r) for r in removed}
                paired = added_keys & removed_keys
                real_added = [a for a in added if _rule_key(a) not in paired]
                real_removed = [r for r in removed if _rule_key(r) not in paired]
                if paired:
                    show = " ; ".join(k.split("/")[-1][:40] or k[:40] for k in sorted(paired)[:3])
                    more = f" 等 {len(paired)} 条" if len(paired) > 3 else ""
                    notes.append(f"{name}: 已修改[{len(paired)}] {show}{more}（规则保留，action 变了）")
                if real_added:
                    show = " ; ".join(a.split("|", 1)[1][:80] for a in real_added[:3])
                    more = f" 等 {len(real_added)} 项" if len(real_added) > 3 else ""
                    notes.append(f"{name}: 新增[{len(real_added)}] {show}{more}")
                if real_removed:
                    show = " ; ".join(r.split("|", 1)[1][:80] for r in real_removed[:3])
                    more = f" 等 {len(real_removed)} 项" if len(real_removed) > 3 else ""
                    notes.append(f"⚠️ {name}: 消失[{len(real_removed)}] {show}{more}")
    return problems, notes


def cmd_build(only=None):
    os.makedirs(OUT, exist_ok=True)
    js_files = {f for f in os.listdir(CACHE) if f.endswith(".js")} if os.path.isdir(CACHE) else set()
    snippets = sorted(f for f in os.listdir(CACHE) if f.endswith(".snippet"))
    total = dict(files=0, rules=0, rewrite=0, script=0)
    all_warns = {}
    for f in snippets:
        name = f[:-8]
        if only and name not in only:
            continue
        txt = open(os.path.join(CACHE, f), encoding="utf-8", errors="ignore").read()
        body, warns, stat = render_plugin(name, txt, js_files)
        # 生成后立刻校验 jq 语法（Loon 对 jq 错误是静默失效的）
        for bad_expr, err in validate_jq(body):
            warns.append(f"!FATAL! jq 语法错误: {bad_expr} → {err}")
        dst = os.path.join(OUT, f"{name}.lpx")
        open(dst, "w", encoding="utf-8").write(body)
        total["files"] += 1
        for k in ("rules", "rewrite", "script"):
            total[k] += stat[k]
        if warns:
            all_warns[name] = warns
        print(f"  ✅ {name:<24} 规则 {stat['rules']:>3} 重写 {stat['rewrite']:>2} 脚本 {stat['script']:>2}"
              f"  {'⚠️ ' + str(len(warns)) + ' 告警' if warns else ''}")
    print(f"\n合计 {total['files']} 个插件 | Rule {total['rules']} | Rewrite {total['rewrite']} | Script {total['script']}")
    if all_warns:
        print("\n=== 需人工复核 ===")
        for n, ws in all_warns.items():
            for w in ws:
                print(f"  [{n}] {w}")
    # ── 可用性校验：确保上游更新不会让插件悄悄失效 ──
    problems, notes = verify_plugins(only)
    if notes:
        print("\n=== 与已发布版本的差异（需人工复核）===")
        for x in notes:
            print(f"  · {x}")
    if problems:
        print("\n=== 可用性问题（阻断发布）===")
        for x in problems:
            print(f"  ❌ {x}")

    fatal = [w for ws in all_warns.values() for w in ws if w.startswith("!FATAL!")]
    if fatal or problems:
        print(f"\n❌ {len(fatal)} 条致命告警 / {len(problems)} 条可用性问题："
              f"生成物看起来正常，但增强或语法可能已失效，不要直接发布")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        cmd_fetch()
    if a.build:
        only = {s.strip() for s in a.only.split(",") if s.strip()} or None
        return cmd_build(only)
    if a.report:
        return cmd_build(None)
    if not any([a.fetch, a.build, a.report]):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
