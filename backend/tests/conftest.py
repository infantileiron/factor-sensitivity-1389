import os
os.environ.setdefault('DATABASE_URL','sqlite+pysqlite:///:memory:')
os.environ.setdefault('REDIS_URL','redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET','test-secret')
os.environ.setdefault('SEED_DEMO','false')
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from src.config.database import Base
from src.config import database as db_module
from src.models.user import User
from src.models.response_model import ResponseModel
from src.models.model_factor import ModelFactor
from src.models.space import FactorSpace
from src.models.factor_range import FactorRange
from src.models.study import SensitivityStudy
from src.models.run import SensitivityRun
from src.utils.security import hash_password,issue
from src.services.run_service import compute

engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
TestSession=sessionmaker(engine,expire_on_commit=False)

@pytest.fixture()
def db():
 Base.metadata.create_all(engine)
 with TestSession() as session:
  yield session
 Base.metadata.drop_all(engine)

@pytest.fixture()
def users(db):
 out={}
 for role in ['admin','analyst','viewer']:
  row=User(id='u-'+role,email=role+'@test.local',password_hash=hash_password('pw123456'),role=role)
  db.add(row);out[role]=row
 db.commit()
 return out

@pytest.fixture()
def tokens(users):
 return {role:'Bearer '+issue(user) for role,user in users.items()}

@pytest.fixture()
def client(monkeypatch):
 from fastapi.testclient import TestClient
 from src.main import app
 def override_get_db():
  with TestSession() as session:yield session
 app.dependency_overrides[db_module.get_db]=override_get_db
 monkeypatch.setattr(db_module,'engine',engine)
 with TestClient(app) as test_client:
  yield test_client
 app.dependency_overrides.clear()

def make_study_runs(db,prefix='t'):
 model=ResponseModel(id=prefix+'-model',name='手算线性模型 '+prefix,description='',intercept=0,response_unit='kWh')
 db.add(model);db.flush()
 db.add(ModelFactor(id=prefix+'-fx',model_id=model.id,factor_id='x',name='因子x',unit='1',linear=1,quadratic=0))
 db.add(ModelFactor(id=prefix+'-fy',model_id=model.id,factor_id='y',name='因子y',unit='1',linear=2,quadratic=0))
 space=FactorSpace(id=prefix+'-space',name='两因子范围 '+prefix,model_id=model.id,description='')
 db.add(space);db.flush()
 db.add(FactorRange(id=prefix+'-rx',space_id=space.id,factor_id='x',low=0,high=1))
 db.add(FactorRange(id=prefix+'-ry',space_id=space.id,factor_id='y',low=0,high=1))
 study=SensitivityStudy(id=prefix+'-study',name='研究 '+prefix,model_id=model.id,space_id=space.id,trajectories=8,levels=6,power=4,seed=20261112)
 db.add(study);db.flush()
 first=SensitivityRun(id=prefix+'-run-1',study_id=study.id,status='queued',result={},error='')
 second=SensitivityRun(id=prefix+'-run-2',study_id=study.id,status='queued',result={},error='')
 other=SensitivityRun(id=prefix+'-run-other',study_id=study.id,status='failed',result={},error='boom')
 db.add_all([first,second,other]);db.commit()
 compute(db,first.id);compute(db,second.id);db.commit()
 return study,first,second,other

def approve_and_report(db,run,report_id,title='测试底稿'):
 from src.models.review import FactorReview
 from src.models.report import Report
 review=FactorReview(id=report_id+'-review',run_id=run.id,action='初始归档复核说明',state='approved',reviewer='admin@test.local')
 db.add(review);db.flush()
 report=Report(id=report_id,review_id=review.id,title=title,version=1,root_id=report_id,predecessor_id=None,snapshot={'result':run.result,'action':review.action,'reviewer':review.reviewer})
 db.add(report);db.commit()
 return report
