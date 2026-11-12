import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models.report import Report
from src.models.run import SensitivityRun
from src.models.correction import CorrectionRequest
from src.services import correction_service as service
from tests.conftest import make_study_runs,approve_and_report

class B:
 def __init__(self,email,role='analyst'):self.email=email;self.role=role

def _request_body(report,run,reason='归档时选错运行，改选同研究已完成运行。'):
 class Body:pass
 b=Body();b.report_id=report.id;b.replacement_run_id=run.id;b.reason=reason
 return b

def test_full_correction_workflow_replaces_current_and_keeps_chain(db,users):
 study,first,second,other=make_study_runs(db,'w')
 report=approve_and_report(db,first,'w-report')
 req=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 assert req.state=='submitted' and req.successor_report_id is None
 assert service.is_current(db,report) is True
 approved=service.approve(db,req,B('admin@test.local',role='admin'),'批准换运行')
 assert approved.state=='approved' and approved.successor_report_id
 successor=db.get(Report,approved.successor_report_id)
 assert successor.version==2 and successor.root_id==report.id and successor.predecessor_id==report.id
 assert service.is_current(db,report) is False and service.is_current(db,successor) is True
 assert successor.snapshot['correction']['replacement_run_id']==second.id
 assert successor.snapshot['correction']['predecessor_run_id']==first.id
 assert db.get(Report,report.id).snapshot['result']['input_sha256']==first.result['input_sha256']
 chain=sorted(db.scalars(select(Report).where((Report.root_id==report.id)|(Report.id==report.id))).all(),key=lambda r:r.version)
 assert [r.version for r in chain]==[1,2]

def test_pending_request_blocks_second_application(db,users):
 study,first,second,other=make_study_runs(db,'p')
 report=approve_and_report(db,first,'p-report')
 service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 with pytest.raises(HTTPException) as exc:
  service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 assert exc.value.status_code==409

def test_duplicate_approve_publishes_single_successor(db,users):
 study,first,second,other=make_study_runs(db,'d')
 report=approve_and_report(db,first,'d-report')
 req=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 service.approve(db,req,B('admin@test.local',role='admin'),'first')
 with pytest.raises(HTTPException) as exc:
  service.approve(db,req,B('admin@test.local',role='admin'),'duplicate')
 assert exc.value.status_code==409
 assert db.scalar(select(Report.id).where(Report.predecessor_id==report.id).limit(1)) is not None
 assert len(db.scalars(select(Report).where(Report.predecessor_id==report.id)).all())==1

def test_reject_keeps_original_effective_and_allows_reapply(db,users):
 study,first,second,other=make_study_runs(db,'r')
 report=approve_and_report(db,first,'r-report')
 req=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 service.reject(db,req,B('admin@test.local',role='admin'),'原因不充分')
 assert req.state=='rejected' and service.is_current(db,report) is True
 again=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 assert again.state=='submitted'

def test_replacement_run_validation_rules(db,users):
 study,first,second,other=make_study_runs(db,'v')
 report=approve_and_report(db,first,'v-report')
 with pytest.raises(HTTPException) as exc:
  service.create_request(db,_request_body(report,other),B('analyst@test.local'))
 assert exc.value.status_code==409 and '已完成' in exc.value.detail
 with pytest.raises(HTTPException) as exc:
  service.create_request(db,_request_body(report,first),B('analyst@test.local'))
 assert exc.value.status_code==409 and '相同' in exc.value.detail
 make_study_runs(db,'v2')
 foreign=db.get(SensitivityRun,'v2-run-2')
 with pytest.raises(HTTPException) as exc:
  service.create_request(db,_request_body(report,foreign),B('analyst@test.local'))
 assert exc.value.status_code==409 and '同一研究' in exc.value.detail

def test_correction_on_historical_report_rejected(db,users):
 study,first,second,other=make_study_runs(db,'h')
 report=approve_and_report(db,first,'h-report')
 req=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 service.approve(db,req,B('admin@test.local',role='admin'),'ok')
 with pytest.raises(HTTPException) as exc:
  service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 assert exc.value.status_code==409 and '后继版本' in exc.value.detail

def test_concurrent_approvals_create_at_most_one_successor(db,users):
 study,first,second,other=make_study_runs(db,'c')
 report=approve_and_report(db,first,'c-report')
 req1=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 req2=CorrectionRequest(id='c-req-2',report_id=report.id,replacement_run_id=second.id,reason='并发的另一张申请',state='submitted',requester='analyst2@test.local',reviewer='',review_note='',successor_report_id=None)
 db.add(req2);db.commit()
 service.approve(db,req1,B('admin@test.local',role='admin'),'one')
 with pytest.raises(HTTPException) as exc:
  service.approve(db,req2,B('admin@test.local',role='admin'),'two')
 assert exc.value.status_code==409
 successors=db.scalars(select(Report).where(Report.predecessor_id==report.id)).all()
 assert len(successors)==1
 assert db.get(CorrectionRequest,req2.id).state=='submitted'

def test_database_unique_constraint_blocks_second_successor(db,users):
 study,first,second,other=make_study_runs(db,'u')
 report=approve_and_report(db,first,'u-report')
 from src.models.review import FactorReview
 second_review=FactorReview(id='u-review-2',run_id=second.id,action='另一条批准',state='approved',reviewer='admin@test.local')
 db.add(second_review);db.flush()
 db.add(Report(id='u-successor-1',review_id=second_review.id,title='后继1',version=2,root_id=report.id,predecessor_id=report.id,snapshot={}))
 db.commit()
 third_review=FactorReview(id='u-review-3',run_id=second.id,action='重复批准',state='approved',reviewer='admin@test.local')
 db.add(third_review);db.flush()
 db.add(Report(id='u-successor-2',review_id=third_review.id,title='后继2',version=3,root_id=report.id,predecessor_id=report.id,snapshot={}))
 with pytest.raises(IntegrityError):db.commit()
 db.rollback()
 assert len(db.scalars(select(Report).where(Report.predecessor_id==report.id)).all())==1

def test_old_report_csv_bytes_unchanged_after_correction(db,users):
 from src.services.report_service import export
 study,first,second,other=make_study_runs(db,'csv')
 report=approve_and_report(db,first,'csv-report')
 before=export(report)
 req=service.create_request(db,_request_body(report,second),B('analyst@test.local'))
 service.approve(db,req,B('admin@test.local',role='admin'),'ok')
 after=export(db.get(Report,report.id))
 assert before==after
