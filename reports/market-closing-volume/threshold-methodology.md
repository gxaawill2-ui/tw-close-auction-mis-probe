# Closing share candidate v1

PROVISIONAL、未校準。候選：同範圍完整closing_turnover_share_pct>=20 且相對之前20個有效日median>=1.5。20/25/30門檻尚無正常日與實質事件日的可比样本，不選正式最佳門檻。CALIBRATED需独立校準證據；現有production常數永遠PROVISIONAL，正式is_closing_volume_spike null。

歷史只取trade_date<當日、generated_at<=asof的同範圍完整官方核對樣本；每交易日最多一個，保存更正前版本並按as-of選最新版本，後來失效的最新版本不能用舊成功版本補位。20日median、60日median、60日線性插值P90分別須足額；不以今天/未来日資料當基準。0分母、非有限數、missing股、範圍不符、錯日期、盤前、來源觀察在asof後均UNKNOWN；不足不判沒有。歷史median0不能除以0。研究candidate result與正式boolean分開。

閾值與樣本可供後續研究，不是買賣訊號。事件日與實際量能獨立，未來樣本按交易日聚類，不按同日多ETF重複計樣本。
