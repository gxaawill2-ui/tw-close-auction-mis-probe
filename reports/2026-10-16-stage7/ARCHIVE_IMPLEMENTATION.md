# 第七階段私有保存實作

沿用既有隔離 Worker、SELECTION binding、publisher/decision Secret；不建立新服務或更改正式服務。

`/private-archive/date/hash` 只允許既有 Bearer + HMAC 寫入「來源物件參照」，server 從現有七日私有區核對 event 與 raw SHA256 後複製至獨立 actor。不能上傳替代 raw。讀取須 Bearer、無公開 CORS、no-store/noindex。每個日期最多600物件、10MB；到期固定為來源 namespace 第一筆 private_written_at +30天，重試與讀取不延長；到期回410並由 alarm 刪除。七日來源與正式/公開選股資料不變。

雙 job：copy 以來源index建立完整雜湊清單；recover 是另一個 Runner，只讀 archive 重新核對全部原始 bytes 雜湊、manifest 和 bundle，不讀七日來源、也不呼叫富果/MIS。只上傳安全的counts/hashes/diagnostics，raw留在私有Worker與記憶體。

本機428項Python與121項Node通過；新增實際workerd測試auth、HMAC、immutable、固定期限，另以本機storage刪除來源測試仍可恢復封存。真實雲端結果待獨立run完成後補入，不以本機合成測試冒充真實備份。

30日封存不是永久備份；需在11月到期前按條款匯出或刪除。未建立新付費服務。Free SQLite公開額度5GB；本區硬上限每天10MB*30=300MB，帳號共用量仍應監看。未將私有保存等同對外再散布授權。
