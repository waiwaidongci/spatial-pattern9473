from fastapi import HTTPException
from ..models import SpatialSurvey,GridCell,NeighborEdge
from ..utils.serialize import record
from .graph_service import prepare_graph,centered_values

def get_survey(db,sid):
    row=db.get(SpatialSurvey,sid)
    if not row:raise HTTPException(404,"观测期不存在")
    return row
def list_surveys(db):
    out=[]
    for s in db.query(SpatialSurvey).order_by(SpatialSurvey.code):
        cells=db.query(GridCell).filter_by(survey_id=s.id).all();edges=db.query(NeighborEdge).filter_by(survey_id=s.id).all();supported=True;reason="图无孤点、观测可分辨，支持置换分析"
        try:prepare_graph([record(c) for c in cells],[record(e) for e in edges]);centered_values([c.value for c in cells])
        except ValueError as e:supported=False;reason=str(e)
        out.append({**record(s),"cell_count":len(cells),"edge_count":len(edges),"supported":supported,"reason":reason})
    return out
