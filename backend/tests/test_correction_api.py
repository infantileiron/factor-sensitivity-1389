from tests.conftest import make_study_runs,approve_and_report

def _seed_report(db):
 study,first,second,other=make_study_runs(db,'api')
 report=approve_and_report(db,first,'api-report')
 return report,second

def test_api_full_flow_and_role_permissions(client,db,users,tokens):
 report,second=_seed_report(db)
 # viewer cannot apply
 r=client.post('/corrections',headers={'Authorization':tokens['viewer']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'选错运行，申请改选同研究的完成运行。'})
 assert r.status_code==403
 # unauthenticated rejected
 assert client.post('/corrections',json={'report_id':report.id,'replacement_run_id':second.id,'reason':'选错运行，申请改选同研究的完成运行。'}).status_code==401
 # analyst applies
 r=client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'选错运行，申请改选同研究的完成运行。'})
 assert r.status_code==201
 correction_id=r.json()['id']
 # duplicate application conflicts
 r=client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'再申请一次，补充换运行的依据。'})
 assert r.status_code==409
 # analyst cannot approve
 assert client.post('/corrections/'+correction_id+'/approve',headers={'Authorization':tokens['analyst']},json={'note':''}).status_code==403
 # invalid body rejected
 assert client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'短'}).status_code==422
 # admin approves
 r=client.post('/corrections/'+correction_id+'/approve',headers={'Authorization':tokens['admin']},json={'note':'同意换运行'})
 assert r.status_code==200 and r.json()['state']=='approved'
 # repeated approve conflicts
 assert client.post('/corrections/'+correction_id+'/approve',headers={'Authorization':tokens['admin']},json={'note':''}).status_code==409
 # reports list flags current vs historical and carries chain fields
 rows=client.get('/reports',headers={'Authorization':tokens['viewer']}).json()
 by_id={row['id']:row for row in rows}
 assert by_id[report.id]['is_current'] is False
 successor_id=r.json()['successor_report_id']
 assert by_id[successor_id]['is_current'] is True
 assert by_id[successor_id]['version']==2 and by_id[successor_id]['predecessor_id']==report.id
 assert by_id[report.id]['version']==1 and by_id[report.id]['root_id']==report.id
 assert by_id[successor_id]['backing_run_id']==second.id and by_id[report.id]['backing_run_id']=='api-run-1'
 # versions endpoint returns ordered chain
 chain=client.get('/reports/'+successor_id+'/versions',headers={'Authorization':tokens['viewer']}).json()
 assert [item['version'] for item in chain]==[1,2]
 # old CSV still downloadable and unchanged
 csv_resp=client.get('/reports/'+report.id+'/csv',headers={'Authorization':tokens['viewer']})
 assert csv_resp.status_code==200 and 'input_sha256' in csv_resp.text

def test_api_reject_flow(client,db,users,tokens):
 report,second=_seed_report(db)
 r=client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'归档底稿选错运行，申请更正。'})
 correction_id=r.json()['id']
 r=client.post('/corrections/'+correction_id+'/reject',headers={'Authorization':tokens['admin']},json={'note':'依据不足'})
 assert r.status_code==200 and r.json()['state']=='rejected'
 rows=client.get('/reports',headers={'Authorization':tokens['viewer']}).json()
 assert all(row['is_current']==(row['id']==report.id) for row in rows)
 # original still correctable after rejection
 r=client.post('/corrections',headers={'Authorization':tokens['analyst']},json={'report_id':report.id,'replacement_run_id':second.id,'reason':'补充依据后再次申请。'})
 assert r.status_code==201
