/**
 * 懂球帝 去广告脚本（dqd_ad.js）
 *
 * 处理逻辑:
 *   1. 评论接口 api.dongdianqiu.com/v2/article/{id}/comment
 *      data.user_list 中存在 role="ad_dplus" 的广告位（伪装成热评用户）
 *   2. 详情接口 detail.dongdianqiu.com/v2/article/detail/{id}
 *      data.dqd_ads 广告位字段 + not_show_m_ad（允许广告开关）
 *
 * 处理: 按 URL 分发 —— 评论接口过滤 ad_dplus 广告位；详情接口清空广告位。
 *
 * Loon 配置:
 *   [Script]
 *   http-response ^https?:\/\/(api\.dongdianqiu\.com\/v2\/article\/\d+\/comment|detail\.dongdianqiu\.com\/v2\/article\/detail\/\d+) script-path=dqd_ad.js, requires-body=true, timeout=60, tag=dqd_ad
 */

let url = $request.url;
let body = $response.body;

if (!body) {
  $done({});
} else {
  try {
    let obj = JSON.parse(body);

    if (url.indexOf("/comment") !== -1) {
      // ===== 评论接口：过滤 ad_dplus 广告位 =====
      if (obj && obj.data) {
        if (Array.isArray(obj.data.user_list)) {
          obj.data.user_list = obj.data.user_list.filter(
            (u) => !(u && u.role === "ad_dplus")
          );
        }
        if (Array.isArray(obj.data.recommend_list)) {
          obj.data.recommend_list = obj.data.recommend_list.filter(
            (u) => !(u && u.role === "ad_dplus")
          );
        }
      }
    } else if (url.indexOf("/article/detail") !== -1) {
      // ===== 详情接口：清空广告位，禁止展示广告 =====
      if (obj && obj.data) {
        obj.data.dqd_ads = [];
        obj.data.not_show_m_ad = 1;
        if (
          obj.data.account &&
          typeof obj.data.account.show_ad !== "undefined"
        ) {
          obj.data.account.show_ad = 0;
        }
      }
    }

    $done({ body: JSON.stringify(obj) });
  } catch (e) {
    // 解析失败时保持原响应不变
    $done({});
  }
}
