from sqlalchemy import select,or_
from ..models.report import Report
from ..models.correction import CorrectionRequest
from ..models.common import serialize
from ..services import correction_service as service
from .common import require
def list_all(db):return [serialize(row) for row in db.scalars(select(CorrectionRequest).order_by(CorrectionRequest.created_at.desc())).all()]
def detail(db,ident):return serialize(require(db,CorrectionRequest,ident))
def create(db,body,user):return serialize(service.create_request(db,body,user))
def approve(db,ident,user,body):return serialize(service.approve(db,require(db,CorrectionRequest,ident),user,body.note))
def reject(db,ident,user,body):return serialize(service.reject(db,require(db,CorrectionRequest,ident),user,body.note))
