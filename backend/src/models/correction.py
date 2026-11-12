from sqlalchemy import String,Text,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class CorrectionRequest(RecordMixin,Base):
 __tablename__="correction_requests"
 report_id:Mapped[str]=mapped_column(ForeignKey("reports.id"))
 replacement_run_id:Mapped[str]=mapped_column(ForeignKey("runs.id"))
 reason:Mapped[str]=mapped_column(Text)
 state:Mapped[str]=mapped_column(String(20),default="submitted")
 requester:Mapped[str]=mapped_column(String(180),default="")
 reviewer:Mapped[str]=mapped_column(String(180),default="")
 review_note:Mapped[str]=mapped_column(Text,default="")
 successor_report_id:Mapped[str|None]=mapped_column(ForeignKey("reports.id"),nullable=True)
