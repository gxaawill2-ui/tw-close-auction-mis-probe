"""Build/reverse review-only patches against fetched main, exclusively in temp."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports/2026-10-16-stage7'
PIN='056dd9757bbce4febd04409858ffa15d239260c9'

def git(*args,cwd=ROOT):return subprocess.check_output(['git',*args],cwd=cwd)
def diff(path,old,new):return ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path if old else '/dev/null',tofile='b/'+path))

def main():
    out=OUT/'proposed';out.mkdir(parents=True,exist_ok=True)
    paths=['probe.py','.github/workflows/twse-mis-probe.yml','docs/index.html']
    original={p:git('show','origin/main:'+p) for p in paths}
    oldpatch=(ROOT/'reports/2026-10-16-stage5/proposed/production-journal.patch').read_text()
    hook=oldpatch.split('--- a/.github/workflows/')[0]
    journal=(ROOT/'reports/2026-10-16-stage5/proposed/stage5_capture_journal.py').read_text().rstrip()+'\n'
    hook+=diff('stage5_capture_journal.py','',journal)
    workflow=original[paths[1]].decode()
    proposed=workflow.replace('  probe:\n    runs-on:', '  probe:\n    environment: stage7-mis-bridge\n    runs-on:')
    proposed=proposed.replace('      TZ: Asia/Taipei\n','      TZ: Asia/Taipei\n      MIS_FAST_JOURNAL_DIR: ${{ vars.STAGE7_JOURNAL_ENABLED == \'true\' && format(\'{0}/stage7-journal\', runner.temp) || \'\' }}\n')
    insertion=f'''      - name: Checkout reviewed isolated write-only bridge
        if: github.event_name != 'push' && env.PROBE_MODE == 'live' && vars.STAGE7_JOURNAL_ENABLED == 'true'
        continue-on-error: true
        uses: actions/checkout@v4
        with:
          ref: {PIN}
          path: .stage7-bridge-code
          persist-credentials: false
      - name: Start isolated write-only bridge; capture remains independent
        if: github.event_name != 'push' && env.PROBE_MODE == 'live' && vars.STAGE7_JOURNAL_ENABLED == 'true'
        continue-on-error: true
        timeout-minutes: 1
        env:
          STAGE5_MIS_BRIDGE_TOKEN: ${{{{ secrets.STAGE5_MIS_BRIDGE_TOKEN }}}}
        run: |
          test -f .stage7-bridge-code/stage6_bridge.py || exit 0
          mkdir -p "$RUNNER_TEMP/stage7-private-bridge"
          chmod 700 "$RUNNER_TEMP/stage7-private-bridge"
          python3 -u .stage7-bridge-code/stage6_bridge.py "$MIS_FAST_JOURNAL_DIR/fast-capture-journal.jsonl" "$GITHUB_WORKSPACE/results/universe.json" "$(TZ=Asia/Taipei date +%F)" "$GITHUB_RUN_ID" "$RUNNER_TEMP/stage7-private-bridge" > "$RUNNER_TEMP/stage7-private-bridge/bridge.log" 2>&1 &
          echo "$!" > "$RUNNER_TEMP/stage7-private-bridge/bridge.pid"
'''
    assert proposed.count('      - name: Run controlled probe\n')==1
    proposed=proposed.replace('      - name: Run controlled probe\n',insertion+'      - name: Run controlled probe\n')
    assert 'FUGLE_API_KEY' not in proposed and 'STAGE5_PUBLISH_TOKEN' not in proposed and 'STAGE5_DECISION_KEY' not in proposed
    bridge=diff(paths[1],workflow,proposed)
    (out/'production-journal-hook.patch').write_text(hook)
    (out/'production-write-only-bridge.patch').write_text(bridge)
    consumer=(ROOT/'reports/2026-10-16-stage6/proposed/independent-consumer.yml.proposed').read_text()
    consumer=consumer.replace('Stage6 independent private journal consumer','Stage7 independent private journal consumer').replace('environment: stage4-fugle-isolated','environment: stage7-tail-consumer').replace('fd08193e4bf99cb5f0642daa9d2a5789487d615b',PIN)
    (out/'independent-consumer.yml.proposed').write_text(consumer)
    site_index=original['docs/index.html'].decode()
    site_index_new=site_index.replace('  <script defer src="status.js', '  <link rel="stylesheet" href="live-tail.css?v=stage7">\n  <script defer src="live-tail.js?v=stage7"></script>\n  <script defer src="status.js')
    site_index_new=site_index_new.replace('  </header>','  </header>\n  <section id="stage7-live" aria-label="即時選股與獨立驗證" hidden></section>',1)
    site_js=(ROOT/'stage3_view.js').read_text()+'\n'+(ROOT/'stage7_site_bootstrap.js').read_text()
    site_css='#stage7-live{margin:24px 0;padding:18px;border:1px solid #32425a;border-radius:14px;background:#111b2d}#stage7-live .stage3-counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}#stage7-live .stage3-counts strong{display:block;font-size:27px}#stage7-live td small{display:block;color:#aabbd0}#stage7-live #stage3-cards{display:none}#stage7-live .stage3-controls{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}@media(max-width:900px){#stage7-live .desktop-wrap{display:none}#stage7-live #stage3-cards{display:grid;gap:12px}#stage7-live{padding:12px}#stage7-live .stage3-counts strong{font-size:24px}}\n'
    config=json.dumps({'enabled':False,'api_base':'https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev','live_released':False},indent=2)+'\n'
    site=diff('docs/index.html',site_index,site_index_new)
    for path,content in [('docs/live-tail.js',site_js),('docs/live-tail.css',site_css),('docs/live-tail-config.json',config)]:
        site+=diff(path,'',content)
        (out/Path(path).name).write_text(content)
    (out/'formal-site-read-only-panel.patch').write_text(site)
    with tempfile.TemporaryDirectory(prefix='stage7-review-only-') as tmp:
        root=Path(tmp)
        for p,raw in original.items():
            target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        for name,patch in [('hook',hook),('bridge',bridge),('site',site)]:
            file=root/(name+'.patch');file.write_text(patch)
            subprocess.run(['git','apply','--check',str(file)],cwd=root,check=True)
            subprocess.run(['git','apply',str(file)],cwd=root,check=True)
        compile((root/'probe.py').read_text(),'isolated-proposal-probe.py','exec')
        compile((root/'stage5_capture_journal.py').read_text(),'isolated-proposal-journal.py','exec')
        # Reverse separately, preserving any unrelated main bytes.
        for name in ('site','bridge','hook'):subprocess.run(['git','apply','--reverse',str(root/(name+'.patch'))],cwd=root,check=True)
        assert all((root/p).read_bytes()==raw for p,raw in original.items())
        assert not (root/'stage5_capture_journal.py').exists()
    report={'scope':'TEMPORARY_COPY_NEW_MINIMAL_PATCHES_APPLY_REVERSE_ONLY',
        'main_commit':git('rev-parse','origin/main').decode().strip(),'production_modified':False,
        'files':{p:{'git_blob':git('rev-parse','origin/main:'+p).decode().strip(),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in original.items()},
        'apply_reverse_original_bytes_restored':True,'new_journal_removed_after_reverse':True,
        'formal_bridge_has_fugle_key':False,'formal_bridge_has_publisher_credentials':False,
        'formal_site_panel_default_enabled':False,'formal_site_verified_release_default':False,'schedules_changed':False,'existing_capture_command_changed':False,
        'environment_admission_and_bridge_cloud_write_verified':False}
    (OUT/'patch-rollback-latest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
