from sqlalchemy import String,Text,JSON,ForeignKey,Double,BigInteger
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class Report(RecordMixin,Base):
 __tablename__="reports"
 review_id:Mapped[str]=mapped_column(ForeignKey("reviews.id"),unique=True)
 title:Mapped[str]=mapped_column(String(180))
 snapshot:Mapped[dict]=mapped_column(JSON)
 version:Mapped[int]=mapped_column(default=1)
 root_id:Mapped[str|None]=mapped_column(ForeignKey("reports.id"),nullable=True)
 predecessor_id:Mapped[str|None]=mapped_column(ForeignKey("reports.id"),nullable=True,unique=True)
