from fastapi import HTTPException
from ..models import GridCell
from ..utils.serialize import record
from .survey_service import get_survey
from .audit_service import log

def list_cells(db,sid):get_survey(db,sid);return [record(c) for c in db.query(GridCell).filter_by(survey_id=sid).order_by(GridCell.code)]
def annotate(db,cid,data,user):
    row=db.get(GridCell,cid)
    if not row:raise HTTPException(404,"网格不存在")
    row.note=data.note;log(db,user.email,"cell.annotate",cid);db.commit();return record(row)
