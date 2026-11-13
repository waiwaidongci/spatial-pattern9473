import csv,io
from redis import Redis
from fastapi import HTTPException
from ..models import GridCell,NeighborEdge,SpatialRun,SamplingNote
from ..config.settings import REDIS_URL
from ..utils.serialize import record
from .survey_service import get_survey
from .graph_service import prepare_graph,centered_values
from .audit_service import log
queue=Redis.from_url(REDIS_URL,decode_responses=True)
def list_runs(db):return [record(r) for r in db.query(SpatialRun).order_by(SpatialRun.id.desc())]
def get_run(db,rid):
    row=db.get(SpatialRun,rid)
    if not row:raise HTTPException(404,"空间研究不存在")
    return row
def create_snapshot(db,survey):return {"survey":record(survey),"cells":[record(c) for c in db.query(GridCell).filter_by(survey_id=survey.id).order_by(GridCell.code)],"edges":[record(e) for e in db.query(NeighborEdge).filter_by(survey_id=survey.id).order_by(NeighborEdge.a,NeighborEdge.b)]}
def create_run(db,data,user):
    survey=get_survey(db,data.survey_id);snapshot=create_snapshot(db,survey)
    try:
        cells,_,_=prepare_graph(snapshot['cells'],snapshot['edges']);centered_values([c['value'] for c in cells])
        if len(cells)*data.permutations>64000:raise ValueError("格数×置换次数超额")
    except ValueError as e:raise HTTPException(422,str(e))
    row=SpatialRun(**data.model_dump(),input_snapshot=snapshot,owner=user.name);db.add(row);db.flush();log(db,user.email,"spatial.enqueue",row.id);db.commit()
    try:queue.rpush("spatial:jobs",row.id)
    except Exception:row.status="failed";row.error="队列不可用，请重提";db.commit();raise HTTPException(503,row.error)
    return record(row)
def export_run(db,rid):
    row=get_run(db,rid)
    if row.status!="completed" or not db.query(SamplingNote).filter_by(run_id=rid,status="approved").first():raise HTTPException(403,"仅获批完成研究可导出")
    o=io.StringIO();w=csv.writer(o);w.writerow(['cell','row','col','value','z','lag','local_I','conditional_expected','p','BH_q','quadrant','q_le_005','global_I','global_p','permutations','seed','input_hash'])
    for x in row.result['local']:c=x['cell'];w.writerow([c['code'],c['row'],c['col'],c['value'],x['z'],x['lag'],x['I'],x['expected'],x['p'],x['q'],x['quadrant'],x['evidence'],row.result['global']['I'],row.result['global']['p'],row.permutations,row.seed,row.result['input_hash']])
    return o.getvalue()
