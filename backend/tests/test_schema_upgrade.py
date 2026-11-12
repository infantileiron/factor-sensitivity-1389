import sqlalchemy as sa
from sqlalchemy import inspect
from src.config import database as db_module
from src.config.database import engine
from src.models.common import now
from src.models.report import Report
from src.models.correction import CorrectionRequest
from src.models.common import serialize

def test_initialize_upgrades_legacy_reports_and_backfills_chain():
 # Fresh isolated in-memory database for the upgrade scenario.
 url='sqlite+pysqlite:///:memory:'
 local_engine=sa.create_engine(url,connect_args={'check_same_thread':False},poolclass=sa.pool.StaticPool)
 legacy=sa.Table('reports',sa.MetaData(),
  sa.Column('id',sa.String(36),primary_key=True),
  sa.Column('created_at',sa.DateTime),
  sa.Column('review_id',sa.String(36)),
  sa.Column('title',sa.String(180)),
  sa.Column('snapshot',sa.JSON))
 legacy.create(local_engine)
 with local_engine.begin() as conn:
  conn.execute(legacy.insert().values(id='legacy-1',created_at=now(),review_id='rv1',title='旧版底稿',snapshot={'result':{}}))
 assert 'version' not in {c['name'] for c in inspect(local_engine).get_columns('reports')}
 previous_engine=db_module.engine
 db_module.engine=local_engine
 try:
  db_module.initialize()
 finally:
  db_module.engine=previous_engine
 columns={c['name'] for c in inspect(local_engine).get_columns('reports')}
 assert {'version','root_id','predecessor_id'}<=columns
 with sa.orm.sessionmaker(local_engine)() as session:
  row=session.get(Report,'legacy-1')
  assert row.version==1 and row.root_id=='legacy-1' and row.predecessor_id is None
  assert serialize(row)['version']==1
 assert inspect(local_engine).has_table('correction_requests')
 local_engine.dispose()

def test_initialize_is_idempotent(db):
 db_module.initialize()
 db_module.initialize()
 columns={c['name'] for c in inspect(engine).get_columns('reports')}
 assert {'version','root_id','predecessor_id'}<=columns
