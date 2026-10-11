# 上市普通股收盤成交值來源

範圍TWSE_ORDINARY_EQUITY_REGULAR_BOARD_LOT_1330_1333_V1：上市普通股的一般整股正常／延後收盤集合競價；排除TPEx、ETF、權證、TDR、零股、盤後及鉅額。不是TAIEX自身成交量，也不是7檔候選和。

已重用本機原保存mis-probe-37730234383.zip（沒有新MIS請求）、universe／raw A/B/C／saved official_close_tse.json。每股使用原freshness及volume_contract gate，兩pre和兩close一致、trade.v=tv=s=累計量差、ts=0、13:30／13:33，官方close一致，張×1000×官方價。無收盤交易不是直接0；需兩post13:33fresh adopted觀察且與pre counters一致才接受0。每碼市場匹配／去重。不能完整驗證的保留missing，不外推全市場。

10/8保存池TWSE1082、可驗證1035、缺47、池內涵蓋95.6562%；部分收盤值合計64,393,939,140元。這是subtotal且完整普通股掛牌範圍亦未完成交叉核對，不能當作整體上市普通股總值；公開首頁全額仍null。證據各股保存immutable SHA檔，raw artifact本身未更動；首次派生資訊為10/11，不冒充10/8盤前或13:35已知。

原saved official MI_INDEX日表note實際寫「含一般、零股、盤後定價，不含鉅額、拍賣、標購」，所以其成交金額不能直接當regular分母。網頁版本有note亦包含鉅額，顯示版本／統計層需逐一驗證，不能硬套。FMTQIK全證券及TAIEX頁市場統計也不適用。免費候選政府11678盤後定價＋交易所盤中／盤後零股表可研究扣除，但本輪尚無完整同日逐股三種排除金額與官方普通股身份核對，不實作猜測扣除。

本機新HTTP robots request timeout；web retrieval部分RWD入口不可取得，不繞過。GitHub hosted isolated CI以robots-first bounded匿名GET進一步實測swagger、10/8MI_INDEX及MI_5MINS，報告official-source-probe.json，不重抓历史MIS。MI_5MINS即使返回也必須核對全證券範圍／13:33，不能取13:25–13:30試撮當成交。

自動累積獨立workflow每日15:05／18:05台北（GitHub延遲可能），讀当日saved artifact及官方日表，寫state/market-closing-volume；source_fail保留舊日／同日資料並寫source-health，每日兩次可重試、來源最多6requests/attempts及10s timeout。只讀API、官方URL，無MIS請求／dispatch／Secrets改動，不延遲13:35。當前可累積partial證據，不能宣稱已取得完整有效20日序列。

官方來源：
https://www.twse.com.tw/zh/trading/historical/mi-index.html
https://www.twse.com.tw/zh/trading/historical/fmtqik.html
https://data.gov.tw/dataset/11678
https://openapi.twse.com.tw/v1/swagger.json
https://investoredu.twse.com.tw/pages/TWSE_InvestmentQA.aspx?ID=14
https://www.twse.com.tw/zh/products/system/trading.html
