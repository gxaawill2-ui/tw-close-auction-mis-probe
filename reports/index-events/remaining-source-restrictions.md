# 三項剩餘限制與實測

|來源／資料|匿名實測|自動取得／重新發布|實施日與內容|
|---|---|---|---|
|MSCI review頁|HTTP200、robots允許|頁可閱讀；公開異動PDF附授權限制，RESTRICTED|Standard/Small Cap名單有TAIWAN區及收盤實施日；無本地股票代號，官方公告時間只日|
|MSCI Standard公開新增刪除PDF|HTTP200，15440 bytes|不重新發布股票名單、不加入自動名單擷取|Geneva2026/08/12，as of close2026/08/31；歷史指數事實不是ETF實際委託|
|MSCI Small Cap公開PDF|HTTP200，23104 bytes|同上；與完整licensed成分庫／權重另分類|公開新增刪除不等於完整權重與自由流通量|
|FTSE完整Technical Releases|原公開入口登入限制|RESTRICTED，保留TWSE／issuer公開日期與TIP允許摘要替代|未新增可靠免費逐檔完整權重，未猜基金下單|
|TPEx OpenAPI quotes|HTTP200，4782391 bytes，12221證券行|政府資料11370免費Open Government Data License 1.0；已整合|118個ETF-format代號觀察，資料日10/8；非完整主檔、當日現在掛牌／下市／追蹤指數未知|
|TPEx完整ETF主檔／月報AUM|swagger無完整ETF基金主檔endpoint|PARTIAL；不從報價消失判下市，不將月報作每日AUM|官方issuer可補index，但目前沒有足夠交叉證據批次確認全部基金|
|元大PCF0050/0051/0056|各HTTP200、robots允許|已整合官方AUM，VERIFIED_AUTOMATIC|提供淨資產／NAV資料日，沒有基金實際換股委託時點|

MSCI公開PDFURL：https://www.msci.com/eqb/gimi/stdindex/MSCI_Aug26_STPublicList.pdf 、https://www.msci.com/eqb/gimi/smallcap/MSCI_Aug26_SCPublicList.pdf 。PDF對資訊使用／重製附限制；匿名可讀不是可自由再散布。本輪只保留官方URL、日期與法律限制研究摘要，不保存或重發成分名單。

TPEx API：https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes ；schema：https://www.tpex.org.tw/openapi/swagger.json ；授權：https://data.gov.tw/dataset/11370 。發行股數Capitals不是AUM。上櫃市場觀察明確as-of，不能聲稱118檔現在持續掛牌。

未來MSCI11/30為EXPECTED_CLOSE_WATCH_DATE，公告來源日期11/11，生效12/1；FTSE50/Mid10012/18為規則預估、12/21生效；0056推估五日12/21,22,23,24,28。仍沒有新找到未來官方ETF實際單一收盤委託時間。TIP既有9筆歷史指數實施證據保留，不冒稱ETF基金交易。來源狀態維持PARTIAL。

實際研究／更新時間：2026-10-10T07:28:34+08:00
