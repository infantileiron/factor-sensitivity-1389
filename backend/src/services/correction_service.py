from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from ..models.run import SensitivityRun
from ..models.review import FactorReview
from ..models.report import Report
from ..models.correction import CorrectionRequest
def backing_run(db,report:Report)->SensitivityRun:
 review=db.get(FactorReview,report.review_id)
 if review is None:raise HTTPException(409,'底稿缺少对应复核记录')
 run=db.get(SensitivityRun,review.run_id)
 if run is None:raise HTTPException(409,'底稿对应的运行记录缺失')
 return run
def is_current(db,report:Report)->bool:
 return db.scalar(select(Report.id).where(Report.predecessor_id==report.id).limit(1)) is None
def _pending_request(db,report_id:str)->CorrectionRequest|None:
 return db.scalar(select(CorrectionRequest).where(CorrectionRequest.report_id==report_id,CorrectionRequest.state=='submitted').limit(1))
def create_request(db,body,user):
 report=db.get(Report,body.report_id)
 if report is None:raise HTTPException(404,'底稿不存在')
 if not is_current(db,report):raise HTTPException(409,'该底稿已被后继版本取代，请对当前版申请更正')
 if _pending_request(db,report.id):raise HTTPException(409,'该底稿已有待审更正申请，请等待主管处理')
 target=db.get(SensitivityRun,body.replacement_run_id)
 if target is None:raise HTTPException(404,'替换运行不存在')
 if target.status!='completed':raise HTTPException(409,'仅已完成运行可用于更正')
 current_run=backing_run(db,report)
 if target.study_id!=current_run.study_id:raise HTTPException(409,'替换运行必须与当前底稿属于同一研究')
 if target.id==current_run.id:raise HTTPException(409,'替换运行与当前底稿运行相同，无需更正')
 row=CorrectionRequest(id=str(uuid4()),report_id=report.id,replacement_run_id=target.id,reason=body.reason,state='submitted',requester=user.email,reviewer='',review_note='',successor_report_id=None)
 db.add(row);db.commit();return row
def approve(db,row:CorrectionRequest,user,note:str):
 locked=db.get(CorrectionRequest,row.id,with_for_update=True)
 if locked is None:raise HTTPException(404,'更正申请不存在')
 if locked.state!='submitted':raise HTTPException(409,'更正申请已处理，不能重复批准')
 predecessor=db.get(Report,locked.report_id,with_for_update=True)
 if predecessor is None:raise HTTPException(404,'待更正底稿不存在')
 if not is_current(db,predecessor):
  db.rollback();raise HTTPException(409,'当前版底稿已发布后继版本，本次批准不再生效')
 target=db.get(SensitivityRun,locked.replacement_run_id,with_for_update=True)
 if target is None or target.status!='completed':
  db.rollback();raise HTTPException(409,'替换运行不可用或未完成，无法发布更正版本')
 review=FactorReview(id=str(uuid4()),run_id=target.id,action='底稿更正批准：'+locked.reason,state='approved',reviewer=user.email)
 db.add(review);db.flush()
 root_id=predecessor.root_id or predecessor.id
 successor=Report(id=str(uuid4()),review_id=review.id,title=predecessor.title+'（更正第'+str(predecessor.version)+'版）',version=predecessor.version+1,root_id=root_id,predecessor_id=predecessor.id,snapshot={'result':target.result,'action':review.action,'reviewer':user.email,'correction':{'request_id':locked.id,'reason':locked.reason,'requester':locked.requester,'predecessor_report_id':predecessor.id,'predecessor_run_id':backing_run(db,predecessor).id,'replacement_run_id':target.id,'version':predecessor.version+1}})
 db.add(successor)
 try:
  db.flush()
 except IntegrityError:
  db.rollback();raise HTTPException(409,'该底稿已发布后继版本，重复或并发批准最多保留一个版本')
 locked.state='approved';locked.reviewer=user.email;locked.review_note=note or '主管批准换运行更正';locked.successor_report_id=successor.id
 db.commit();return locked
def reject(db,row:CorrectionRequest,user,note:str):
 locked=db.get(CorrectionRequest,row.id,with_for_update=True)
 if locked is None:raise HTTPException(404,'更正申请不存在')
 if locked.state!='submitted':raise HTTPException(409,'更正申请已处理')
 locked.state='rejected';locked.reviewer=user.email;locked.review_note=note or '主管驳回更正申请'
 db.commit();return locked
