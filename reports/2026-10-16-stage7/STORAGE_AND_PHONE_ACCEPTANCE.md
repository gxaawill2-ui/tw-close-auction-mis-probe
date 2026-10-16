# 長期保存與手機驗收

## 已真正完成的30日保存

Run https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/38892154976

- copy job116943984721：10/16 19:12:06完成60個物件的server-side私有複製。
- recover job116944161032：不同Runner，19:12:32只讀archive恢復60個物件、14組bundle，250,517 raw bytes逐一SHA256核對；來源七日區讀取0、MIS/Fugle請求0。
- manifest SHA256：abde1faab4e298f1c2f2864f9f0b7ae530e882040402faf298025c9fb0f48c68。
- 固定到期：2026-11-15T05:06:22.209Z，即台北11/15 13:06:22.209。來源七日清理不會刪此獨立actor；讀取/重試不續期。真實來源尚未到期，本輪未刪真實來源；來源刪除後仍可恢復的測試是在本機明確標示的合成storage。
- 60物件包括真實回應、bundle manifest、控制及canary，不是60檔股票。公開只有counts、時間與hash；原始行情沒有進公開repo/Artifact/頁面。

沿用同一Worker、binding與原隔離憑證；private-archive讀取須Bearer，寫入須Bearer+HMAC且只允許引用既有已核對原始物件；匿名無權、無CORS、no-store/noindex。每日期600物件、10MB硬上限、固定alarm自動清理。沒有新服務、帳戶、Key或費用方案。

| 方案 | 優點 | 限制與本輪決定 |
| --- | --- | --- |
| A 另匯出持久私有位置 | 可做獨立離線/不同供應商備份 | 本輪未有其他已授權目的地，不自行上傳；擴權/新目的地/付費須同意 |
| B 既有隔離Worker30日獨立封存 | 權限與服務不擴大，免費小容量，可跨Runner復原，自動清理 | 共用供應商，僅30日，不是永久/離線備份；本輪已真實完成複製和獨立恢復 |

10MB/日*30=300MB只是本區硬預算，還需加上七日來源、MIS與帳號其他資料；Free SQLite DO公告5GB。未升級付費，不能把單區預算當整個帳號永遠免費保證。富果條款禁止未授權再散布，本輪未新增接收者；文件未找到30日個人調查保存的明確上限，已在客服草稿要求確認，不宣稱取得官方授權答覆。

安全恢復：用既有隔離Environment的workflow，在私有記憶體讀/private-archive/2026-10-16/index，核對60及上述manifest，再用stage7_archive.recover_snapshot逐一checked/restore_bundle。copy/recover安全Artifact可提供完整hash清單，raw只能從私有API恢復，不能上傳GitHub。即使copy安全Artifact到期，repo保存的manifest digest仍可核對private index，不能因index可讀就省略全部raw hash檢查。

已建立11/12 13:06台北的一次性到期檢查提醒，預留三天。到期前若調查未結束，須取得新私有匯出目的地的最小同意；不得靠讀取無限展延。

## 新版隔離頁外部桌機

同一Worker新版計數已部署，19:26:06在真實外部Chrome讀取既有真實研究結果。共3檔：4609/1235為RESEARCH_ONLY、6228為UNKNOWN，VERIFIED0；5546仍在私有待查核。畫面研究2、UNKNOWN1，三檔同時可見，不再把UNKNOWN重複計入研究數。涵蓋1938/1967、29未知。

操作最後一盤量排序：13/4/1，股票順序4609、1235、6228，箭頭向下；深色顯示正常，公開版本1792129307272000未被此次UI部署覆寫。截圖external-desktop.jpg。

頁面當前版13:41:47的產生/寫入是當日後續逐檔更新，不是第一次發布；首次研究發布仍是13:34:40。19:26是本輪桌機讀取，不是歷史盤中手機時間。前階段1～2秒自動更新是2099合成日期測試，不能當真實端到端耗時。

## 實體iPhone Safari：未通過，等待本人操作

Work無法操作本人實體iPhone，沒有以雲端Chrome、WebKit或手機尺寸模擬冒充。

1. 用iPhone Safari新分頁開 https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev/?date=2026-10-16 。
2. 確認日期10/16、初篩共3（研究2/UNKNOWN1/VERIFIED0）、4609/6228/1235三檔、1938/1967與29未知；介面深色，橫直拿均無遮蔽。
3. 選最後一盤量並切換方向，確認13/4/1及1/4/13；保留頂端日期/計數/瀏覽器讀取時間、版本與股票卡片的截圖。
4. 回傳iPhone型號、iOS版本、截圖，以及「可開啟／有無跑版／排序是否正常」。不用提供任何Key或登入。

穩定版沒有新資料時，讀取時間不會每5秒跳動，不能因此判定刷新失敗。真正自動更新/撤回要另用既有2099合成日期、在本人開頁準備好後安排受控版本輪替；必須把合成更新測試與10/19真實行情分開。本人未回傳前，手機開啟、刷新、快取及實際看到時間均維持未驗收。
