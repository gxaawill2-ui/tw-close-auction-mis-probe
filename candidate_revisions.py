"""Same-day MIS result revisions. No transport or credentials are owned here."""
import base64,copy,hashlib,json,time,urllib.error,re
import freshness as f

PROTOCOL='MIS_REVISIONS_V2'


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def content(payload):
    fields=('ex','code','name','market','P_before','P_close','P_before_trade_time','P_close_trade_time','tail_return_pct',
      'P_before_convergence_type','P_close_convergence_type','confidence_level','volume_status','volume_unit',
      'closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct','selection_status')
    return {'trade_date':payload['trade_date'],'capture_run_id':payload['capture_run_id'],'coverage':payload['coverage'],
      'candidates':[{k:r.get(k) for k in fields} for r in payload['candidate_list']],
      'unknown':payload.get('unknown_candidate_list',[]),'unresolved':payload.get('unresolved_symbols',[]),
      'source_evidence_count':payload['source_evidence_count'],'source_evidence_hash':payload['source_evidence_hash'],
      'source_last_received_at':payload['source_last_received_at']}


def prepare(payload,report,snapshots,probes,date,generated):
    result=copy.deepcopy(payload);confirmed=[];unknown={}
    for row in result['candidate_list']:
        # Existing volume contract requires two actual pre and close observations.
        proof=row.get('volume_evidence',{});pair=proof.get('close_observations') or []
        if row['volume_status']=='MIS_EVIDENCE_CONFIRMED' and len(pair)==2:
            row.update(selection_status='MIS_CONFIRMED',selection_label='MIS 多次確認通過');confirmed.append(row)
        else:unknown[(row['ex'],row['code'])]={'ex':row['ex'],'code':row['code'],'reason':'NEEDS_MULTIPLE_MIS_AND_VOLUME_EVIDENCE'}
    for row in report['securities']:
        if row['research_calculable']:continue
        pre=f.decimal_value(row.get('p_before'));last=(row.get('close_research_evidence') or {}).get('selected') or {}
        price=f.decimal_value(last.get('trade_z'))
        if pre and price and pre>0 and last.get('trade_t') in ('13:30:00','13:33:00') and abs(price/pre-1)>=f.Decimal('.03'):
            unknown[(row['ex'],row['code'])]={'ex':row['ex'],'code':row['code'],'reason':'DELAYED_OR_INCONSISTENT_CLOSE_NEEDS_CONFIRMATION'}
    records=[r for shot in snapshots for r in shot['records']]+list(probes)
    identities=sorted({digest(r) for r in records})
    last=max((r['received_at'] for r in records if f.parsed_time(r.get('received_at'))),default=None)
    result.update(revision_protocol=PROTOCOL,candidate_list=confirmed,candidate_count=len(confirmed),
      unknown_candidate_list=sorted(unknown.values(),key=lambda r:(r['ex'],r['code'])),
      unresolved_symbols=[{'ex':r['ex'],'code':r['code']} for r in report['securities'] if not r['research_calculable']],
      source_evidence_count=len(identities),source_evidence_hash=digest(identities),source_last_received_at=last,
      price_limitation='MIS 多次確認；官方盤後核對另列，未宣稱獨立逐筆驗證。')
    result['content_hash']=digest(content(result))
    return result


def validate(payload):
    if payload.get('revision_protocol')!=PROTOCOL:raise ValueError('REVISION_PROTOCOL_REQUIRED')
    if type(payload.get('source_evidence_count')) is not int or payload['source_evidence_count']<1:raise ValueError('INVALID_SOURCE_EVIDENCE_COUNT')
    if any(not isinstance(payload.get(k),str) or not re.fullmatch(r'[0-9a-f]{64}',payload[k]) for k in ('source_evidence_hash','content_hash')):raise ValueError('INVALID_REVISION_DIGEST')
    stamp=f.parsed_time(payload.get('source_last_received_at'));generated=f.parsed_time(payload.get('generated_at'))
    if not stamp or not generated or stamp>generated or stamp.astimezone(f.TZ).date().isoformat()!=payload['trade_date']:raise ValueError('INVALID_EVIDENCE_CLOCK')
    if payload.get('content_hash')!=digest(content(payload)):raise ValueError('REVISION_CONTENT_HASH_MISMATCH')
    if any(r.get('selection_status')!='MIS_CONFIRMED' or r.get('volume_status')!='MIS_EVIDENCE_CONFIRMED' for r in payload['candidate_list']):raise ValueError('UNCONFIRMED_PUBLIC_CANDIDATE')
    keys=set()
    for row in payload.get('unknown_candidate_list',[]):
        key=row.get('ex'),row.get('code')
        if key in keys or row.get('ex') not in ('tse','otc') or not isinstance(row.get('code'),str) or len(row['code'])!=4 or not row['code'].isdigit():raise ValueError('INVALID_UNKNOWN_LIST')
        keys.add(key)
    if keys & {(r['ex'],r['code']) for r in payload['candidate_list']}:raise ValueError('CONFLICTING_CANDIDATE_STATES')


def put(payload,api,now,legacy_validate,*,attempts=3):
    date=payload['trade_date'];legacy_validate(payload,date);validate(payload)
    actual=f.parsed_time(now())
    if not actual or actual.astimezone(f.TZ).date().isoformat()!=date or f.parsed_time(payload['generated_at'])>actual:raise ValueError('INVALID_PUBLICATION_CLOCK')
    path='state/candidates/'+date+'.json'
    last=None
    for attempt in range(attempts):
        try:
            stored=api('contents/'+path+'?ref=main')
            old=json.loads(base64.b64decode(stored['content'])) if stored else None
            result=copy.deepcopy(payload);same=False
            if old:
                legacy_validate(old,date)
                if str(old['capture_run_id'])!=str(result['capture_run_id']):raise ValueError('REVISION_SOURCE_RUN_CONFLICT')
                if f.parsed_time(result['generated_at'])<f.parsed_time(old['generated_at']):raise ValueError('STALE_REVISION_CLOCK')
                if old.get('revision_protocol')==PROTOCOL:
                    validate(old)
                    same=old['content_hash']==result['content_hash']
                    if not same and (result['source_evidence_count']<=old['source_evidence_count'] or result['source_last_received_at']<old['source_last_received_at']):raise ValueError('STALE_OR_CONFLICTING_EVIDENCE')
                    result['revision']=old['revision']+(0 if same else 1)
                    result['evidence_sequence']=old['evidence_sequence']+(0 if same else 1)
                else:result.update(revision=1,evidence_sequence=1)
                # Same-price annotations survive a later revision; a reprice must
                # return to PENDING until that actual revised close is checked.
                prior={(r['ex'],r['code']):r for r in old['candidate_list']}
                for row in result['candidate_list']:
                    before=prior.get((row['ex'],row['code']))
                    if before and all(before.get(k)==row.get(k) for k in ('P_before','P_close','P_before_trade_time','P_close_trade_time')) and (before.get('postmarket_verified_at') or '')>(row.get('postmarket_verified_at') or ''):
                        for key in ('official_price_result','official_close','postmarket_verified_at'):
                            if key in before:row[key]=before[key]
                        for key in ('official_daily_shares','official_daily_volume_scope'):
                            if key in before.get('volume_evidence',{}):row['volume_evidence'][key]=before['volume_evidence'][key]
                if (old.get('postmarket_verified_at') or '')>(result.get('postmarket_verified_at') or ''):
                    for key in ('postmarket_verified_at','official_validation_run_id'):
                        if key in old:result[key]=old[key]
                active={(r['ex'],r['code']) for r in result['candidate_list']}
                withdrawn=[r for r in old.get('withdrawals',[]) if (r['ex'],r['code']) not in active]
                pending={(r['ex'],r['code']) for r in result['unknown_candidate_list']} | {(r['ex'],r['code']) for r in result.get('unresolved_symbols',[])}
                for key,row in prior.items():
                    if key not in active and key not in {(r['ex'],r['code']) for r in withdrawn}:
                        withdrawn.append({'ex':key[0],'code':key[1],'at':result['generated_at'],'reason':'UNKNOWN' if key in pending else 'NO_LONGER_QUALIFIES'})
                result['withdrawals']=withdrawn[-100:]
                result['previous_price_fingerprint']=old['price_fingerprint']
                result['published_at']=old.get('published_at')
                ignore={'updated_at','published_at','publication_mode','publication_code_sha','source_artifact_sha256','previous_price_fingerprint'}
                if same and canonical({k:v for k,v in old.items() if k not in ignore})==canonical({k:v for k,v in result.items() if k not in ignore}):
                    return {'status':'PUBLISHED','idempotent':True,'path':path,'revision':old['revision'],'published_at':old.get('published_at')}
            else:result.update(revision=1,evidence_sequence=1,withdrawals=[],published_at=now())
            result['updated_at']=now();legacy_validate(result,date);validate(result)
            body={'message':'Publish MIS result revision '+date,'branch':'main','content':base64.b64encode((canonical(result)+'\n').encode()).decode()}
            if stored:body['sha']=stored['sha']
            ack=api('contents/'+path,'PUT',body)
            commit=(ack.get('commit') or {}).get('sha') if isinstance(ack,dict) else None
            if not isinstance(commit,str) or not commit:raise RuntimeError('PUBLICATION_ACK_MISSING')
            return {'status':'PUBLISHED','idempotent':False,'path':path,'revision':result['revision'],'published_at':result['published_at'],'commit_sha':commit}
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            if isinstance(exc,urllib.error.HTTPError) and exc.code not in (409,422,429,500,502,503,504):raise
            last=exc
            if attempt+1<attempts:time.sleep(.3*(2**attempt))
    raise RuntimeError('CANDIDATE_PUBLICATION_FAILED:'+type(last).__name__)
