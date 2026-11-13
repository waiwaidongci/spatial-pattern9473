from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.cell import CellOutput,CellAnnotation
from ..services.cell_service import list_cells,annotate
router=APIRouter(tags=["cells"])
@router.get("/surveys/{sid}/cells",response_model=list[CellOutput])
def index(sid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_cells(db,sid)
@router.patch("/cells/{cid}")
def update(cid:int,data:CellAnnotation,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):return annotate(db,cid,data,user)
