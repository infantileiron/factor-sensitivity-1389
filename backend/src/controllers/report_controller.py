from sqlalchemy import select
from ..models.report import Report
from ..models.review import FactorReview
from ..models.run import SensitivityRun
from ..models.common import serialize
from ..services import report_service as service
from .common import require
def _with_version_fields(db,row):
 payload=serialize(row)
 payload['is_current']=db.scalar(select(Report.id).where(Report.predecessor_id==row.id).limit(1)) is None
 review=db.get(FactorReview,row.review_id)
 payload['backing_run_id']=review.run_id if review else None
 if review:
  run=db.get(SensitivityRun,review.run_id)
  payload['study_id']=run.study_id if run else None
 payload['root_id']=row.root_id or row.id
 return payload
def list_all(db):
 rows=db.scalars(select(Report).order_by(Report.created_at.desc())).all()
 return [_with_version_fields(db,row) for row in rows]
def detail(db,ident):return _with_version_fields(db,require(db,Report,ident))
def create(db,body):return _with_version_fields(db,service.create(db,body))
def versions(db,ident):
 row=require(db,Report,ident)
 root_id=row.root_id or row.id
 chain=db.scalars(select(Report).where((Report.root_id==root_id)|(Report.id==root_id)).order_by(Report.version.asc())).all()
 return [_with_version_fields(db,item) for item in chain]
