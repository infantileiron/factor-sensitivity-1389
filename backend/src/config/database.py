from sqlalchemy import create_engine,inspect,text
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .settings import DATABASE_URL
class Base(DeclarativeBase):pass
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
Session=sessionmaker(engine,expire_on_commit=False)
def get_db():
 with Session() as db:yield db
def _upgrade_reports():
 inspector=inspect(engine)
 if 'reports' not in inspector.get_table_names():return
 columns={column['name'] for column in inspector.get_columns('reports')}
 with engine.begin() as conn:
  if 'version' not in columns:
   conn.execute(text("ALTER TABLE reports ADD COLUMN version INTEGER DEFAULT 1"))
   conn.execute(text("ALTER TABLE reports ADD COLUMN root_id VARCHAR(36) NULL"))
   conn.execute(text("ALTER TABLE reports ADD COLUMN predecessor_id VARCHAR(36) NULL"))
   if engine.dialect.name=='mysql':
    conn.execute(text("ALTER TABLE reports ADD CONSTRAINT fk_reports_root FOREIGN KEY(root_id) REFERENCES reports(id)"))
    conn.execute(text("ALTER TABLE reports ADD CONSTRAINT fk_reports_predecessor FOREIGN KEY(predecessor_id) REFERENCES reports(id)"))
   conn.execute(text("CREATE UNIQUE INDEX uq_reports_predecessor_id ON reports(predecessor_id)"))
  conn.execute(text("UPDATE reports SET version=1 WHERE version IS NULL"))
  conn.execute(text("UPDATE reports SET root_id=id WHERE root_id IS NULL"))
def initialize():
 from .. import models
 Base.metadata.create_all(engine)
 _upgrade_reports()
