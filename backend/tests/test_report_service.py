from src.models.report import Report
from src.models.review import FactorReview
from src.services import report_service
from tests.conftest import make_study_runs

class _Body:
 def __init__(self,review_id,title):self.review_id=review_id;self.title=title

def test_new_report_is_self_rooted_version_one(db):
 study,first,second,other=make_study_runs(db,'root')
 review=FactorReview(id='root-review',run_id=first.id,action='初始复核',state='approved',reviewer='admin@test.local')
 db.add(review);db.commit()
 row=report_service.create(db,_Body(review.id,'新底稿'))
 assert row.version==1 and row.root_id==row.id and row.predecessor_id is None
 # idempotent: repeated create for the same review returns the same row, no duplicate
 again=report_service.create(db,_Body(review.id,'新底稿'))
 assert again.id==row.id
 assert db.query(Report).filter(Report.review_id==review.id).count()==1
