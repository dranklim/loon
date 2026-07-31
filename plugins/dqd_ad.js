/**
 * 懂球帝 去广告脚本（dqd_ad.js）
 *
 * 处理逻辑:
 *   1. 评论接口 api.dongdianqiu.com/v2/article/{id}/comment
 *      data.user_list 中存在 role="ad_dplus" 的广告位（伪装成热评用户）
 *   2. 详情接口 detail.dongdianqiu.com/v2/article/detail/{id}
 *      data.dqd_ads 广告位字段 + not_show_m_ad（允许广告开关）
 *   3. 信息流列表接口 api.dongdianqiu.com/v3/archive/app/tabs/getlists
 *      articles 中存在 is_business_ad=1 的广告文章（如剑南春），过滤后框体消失
 *
 * 处理: 按 URL 分发 —— 评论过滤 ad_dplus；详情清空广告位；列表过滤广告文章。
 *
 * Loon 配置:
 *   [Script]
 *   http-response ^https?:\/\/(api\.dongdianqiu\.com\/(v2\/article\/\d+\/comment|v3\/archive\/app\/tabs\/getlists)|detail\.dongdianqiu\.com\/v2\/article\/detail\/\d+) script-path=https://raw.githubusercontent.com/dranklim/loon/main/plugins/dqd_ad.js, requires-body=true, timeout=60, tag=dqd_ad
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
    } else if (url.indexOf("getlists") !== -1) {
      // ===== 信息流列表：过滤 is_business_ad=1 的广告文章（如剑南春）=====
      const lists = [];
      if (obj && Array.isArray(obj.articles)) lists.push(obj.articles);
      if (obj && obj.data && Array.isArray(obj.data.articles)) {
        lists.push(obj.data.articles);
      }
      for (const list of lists) {
        for (let i = list.length - 1; i >= 0; i--) {
          const a = list[i];
          if (a && Number(a.is_business_ad) === 1) {
            list.splice(i, 1);
          }
        }
      }
    }

    $done({ body: JSON.stringify(obj) });
  } catch (e) {
    // 解析失败时保持原响应不变
    $done({});
  }
}
