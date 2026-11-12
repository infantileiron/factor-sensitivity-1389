from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..utils.auth import current,write_user,admin
from ..schemas.correction import CorrectionCreate,CorrectionDecision
from ..controllers import correction_controller as controller
router=APIRouter(prefix='/corrections',tags=['corrections'])
@router.get('')
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get('/{ident}')
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.post('',status_code=201)
def create(body:CorrectionCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create(db,body,user)
@router.post('/{ident}/approve')
def approve(ident:str,body:CorrectionDecision,db=Depends(get_db),user=Depends(admin)):return controller.approve(db,ident,user,body)
@router.post('/{ident}/reject')
def reject(ident:str,body:CorrectionDecision,db=Depends(get_db),user=Depends(admin)):return controller.reject(db,ident,user,body)
