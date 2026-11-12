from tests.conftest import make_study_runs,approve_and_report

def test_end_to_end_apply_approve_version_chain_reject(client,db,users,tokens):
 study,first,second,other=make_study_runs(db,'e2e')
 report=approve_and_report(db,first,'e2e-report')
 ah={'Authorization':tokens['analyst']}; mh={'Authorization':tokens['admin']}; vh={'Authorization':tokens['viewer']}
 # 1. analyst applies; original stays effective while pending
 r=client.post('/corrections',headers=ah,json={'report_id':report.id,'replacement_run_id':second.id,'reason':'归档时选错运行，改选同一研究的另一已完成运行作为更正。'})
 assert r.status_code==201
 cid=r.json()['id']
 pending={x['id']:x for x in client.get('/reports',headers=vh).json()}
 assert pending[report.id]['is_current'] is True
 # 2. admin approves: successor published, original becomes historical
 assert client.post('/corrections/'+cid+'/approve',headers=mh,json={'note':'同意换运行'}).status_code==200
 rows={x['id']:x for x in client.get('/reports',headers=vh).json()}
 old=rows[report.id]
 successor=[x for x in rows.values() if x['predecessor_id']==report.id][0]
 assert old['is_current'] is False and old['version']==1
 assert successor['is_current'] is True and successor['version']==2
 assert successor['backing_run_id']==second.id and old['backing_run_id']==first.id
 assert successor['root_id']==report.id
 # 3. traceable chain in both directions, ordered by version
 chain=client.get('/reports/'+successor['id']+'/versions',headers=vh).json()
 assert [item['version'] for item in chain]==[1,2]
 assert chain[1]['snapshot']['correction']['predecessor_report_id']==report.id
 assert chain[1]['snapshot']['correction']['replacement_run_id']==second.id
 # 4. historical report can no longer receive a new application
 assert client.post('/corrections',headers=ah,json={'report_id':report.id,'replacement_run_id':second.id,'reason':'对历史版再申请更正，应当被拒绝受理。'}).status_code==409
 # 5. another correction on the current version: first approval wins, duplicate approval blocked
 r2=client.post('/corrections',headers=ah,json={'report_id':successor['id'],'replacement_run_id':first.id,'reason':'对当前版再发起一次更正申请用于并发验证。'})
 assert r2.status_code==201
 cid2=r2.json()['id']
 assert client.post('/corrections/'+cid2+'/approve',headers=mh,json={'note':''}).status_code==200
 assert client.post('/corrections/'+cid2+'/approve',headers=mh,json={'note':''}).status_code==409
 final_reports=client.get('/reports',headers=vh).json()
 assert sum(1 for x in final_reports if x['predecessor_id']==successor['id'])==1
 # 6. old and new CSV both downloadable; same-study deterministic reruns may share values,
 #    but the old report's CSV bytes stay immutable while backing runs differ.
 from src.services.report_service import export
 from src.models.report import Report
 csv_old_before=export(db.get(Report,report.id))
 csv_old=client.get('/reports/'+report.id+'/csv',headers=vh).text
 csv_v3=client.get('/reports/'+successor['id']+'/csv',headers=vh).text
 assert 'input_sha256' in csv_old and 'input_sha256' in csv_v3
 assert csv_old==csv_old_before and old['backing_run_id']!=successor['backing_run_id']
 # 7. rejection path leaves the current version effective and permits re-application
 current=[x for x in final_reports if x['is_current']][0]
 r3=client.post('/corrections',headers=ah,json={'report_id':current['id'],'replacement_run_id':second.id,'reason':'再试一次驳回路径，原因描述足够长。'})
 cid3=r3.json()['id']
 assert client.post('/corrections/'+cid3+'/reject',headers=mh,json={'note':'依据不足，驳回'}).status_code==200
 assert [x for x in client.get('/reports',headers=vh).json() if x['id']==current['id']][0]['is_current'] is True
 states=sorted(x['state'] for x in client.get('/corrections',headers=vh).json())
 assert states==['approved','approved','rejected']

def test_existing_archived_report_is_directly_correctable(client,db,users,tokens):
 # An already-approved legacy-style report (no correction metadata beyond version 1) can enter the workflow.
 study,first,second,other=make_study_runs(db,'leg')
 report=approve_and_report(db,first,'leg-report')
 r=client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'已归档底稿选错运行，现直接纳入更正流程，原因说明足够长。'})
 assert r.status_code==201
