from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.edge import EdgeOutput
from ..services.edge_service import list_edges
router=APIRouter(tags=["edges"])
@router.get("/surveys/{sid}/edges",response_model=list[EdgeOutput])
def index(sid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_edges(db,sid)
