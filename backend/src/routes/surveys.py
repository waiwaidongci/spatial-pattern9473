from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user
from ..schemas.survey import SurveyOutput
from ..services.survey_service import list_surveys
router=APIRouter(prefix="/surveys",tags=["surveys"])
@router.get("",response_model=list[SurveyOutput])
def index(db:Session=Depends(get_db),user=Depends(current_user)):return list_surveys(db)
