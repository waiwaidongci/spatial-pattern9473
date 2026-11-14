import csv,io
from redis import Redis
from fastapi import HTTPException
from ..models import GridCell,NeighborEdge,SpatialRun,SamplingNote
from ..config.settings import REDIS_URL
from ..utils.serialize import record
from .survey_service import get_survey
from .graph_service import prepare_graph,centered_values
from .analysis_service import analyze_sensitivity,requested_cells,clean_sensitivity_cells,check_budget
from .audit_service import log
queue=Redis.from_url(REDIS_URL,decode_responses=True)
def list_runs(db):return [record(r) for r in db.query(SpatialRun).order_by(SpatialRun.id.desc())]
def get_run(db,rid):
    row=db.get(SpatialRun,rid)
    if not row:raise HTTPException(404,"空间研究不存在")
    return row
def create_snapshot(db,survey):return {"survey":record(survey),"cells":[record(c) for c in db.query(GridCell).filter_by(survey_id=survey.id).order_by(GridCell.code)],"edges":[record(e) for e in db.query(NeighborEdge).filter_by(survey_id=survey.id).order_by(NeighborEdge.a,NeighborEdge.b)]}
def _apply_sensitivity(snapshot,cells):
    snapshot=dict(snapshot)
    snapshot['sensitivity']={"cells":sorted(cells)}
    return snapshot
def _snapshot_codes(snapshot):return {c.get('code') for c in snapshot.get('cells',[]) if isinstance(c,dict)}
def _validate_against_snapshot(snapshot,cells,permutations):
    unknown=[c for c in cells if c not in _snapshot_codes(snapshot)]
    if unknown:raise HTTPException(422,"单格剔除清单引用建单快照中不存在的格点："+"、".join(unknown))
    try:check_budget(len(snapshot['cells']),permutations,len(cells))
    except ValueError as e:raise HTTPException(422,str(e))
def create_run(db,data,user):
    survey=get_survey(db,data.survey_id);snapshot=create_snapshot(db,survey)
    try:requested=clean_sensitivity_cells(data.sensitivity_cells)
    except ValueError as e:raise HTTPException(422,str(e))
    _validate_against_snapshot(snapshot,requested,data.permutations)
    snapshot=_apply_sensitivity(snapshot,requested)
    try:
        cells,_,_=prepare_graph(snapshot['cells'],snapshot['edges']);centered_values([c['value'] for c in cells])
        if len(cells)*data.permutations>64000:raise ValueError("格数×置换次数超额")
        check_budget(len(cells),data.permutations,len(requested))
    except ValueError as e:raise HTTPException(422,str(e))
    payload=data.model_dump();payload.pop('sensitivity_cells',None)
    row=SpatialRun(**payload,input_snapshot=snapshot,owner=user.name);db.add(row);db.flush();log(db,user.email,"spatial.enqueue",row.id);db.commit()
    try:queue.rpush("spatial:jobs",row.id)
    except Exception:row.status="failed";row.error="队列不可用，请重提";db.commit();raise HTTPException(503,row.error)
    return record(row)
def attach_sensitivity(db,rid,data,user):
    row=get_run(db,rid)
    if row.status!="completed" or not row.result:raise HTTPException(409,"仅已完成研究可补充单格剔除敏感性")
    requested=clean_sensitivity_cells(data.sensitivity_cells)
    if not requested:raise HTTPException(422,"请指定至少一个待剔除格点")
    snapshot=row.input_snapshot or {}
    _validate_against_snapshot(snapshot,requested,row.permutations)
    recorded=requested_cells(snapshot)
    merged=sorted(set(recorded)|set(requested))
    if len(merged)>20:raise HTTPException(422,"补充后单格剔除方案不得超过20个")
    snapshot=_apply_sensitivity(snapshot,merged)
    try:block=analyze_sensitivity(snapshot,row.result,row.permutations,row.seed,merged)
    except ValueError as e:raise HTTPException(422,str(e))
    block["base_result_preserved"]=True
    block["upgrade_note"]="旧版结果仅补充敏感性块；基础全局/局部结果、原input_hash与算法版本保持不变。"
    result=dict(row.result);result["sensitivity"]=block
    row.input_snapshot=snapshot;row.result=result
    log(db,user.email,"spatial.sensitivity",row.id);db.commit()
    return record(row)
def _sensitivity_guard(db,rid):
    row=get_run(db,rid)
    if row.status!="completed" or not db.query(SamplingNote).filter_by(run_id=rid,status="approved").first():raise HTTPException(403,"仅获批完成研究可导出")
    return row
def export_run(db,rid):
    row=_sensitivity_guard(db,rid);sensitivity=row.result.get("sensitivity") or {}
    o=io.StringIO();w=csv.writer(o);w.writerow(['cell','row','col','value','z','lag','local_I','conditional_expected','p','BH_q','quadrant','q_le_005','global_I','global_p','permutations','seed','input_hash','sensitivity_requested','sensitivity_completed','sensitivity_invalid'])
    requested=sensitivity.get("requested") or [];summary=sensitivity.get("summary") or {}
    for x in row.result['local']:c=x['cell'];w.writerow([c['code'],c['row'],c['col'],c['value'],x['z'],x['lag'],x['I'],x['expected'],x['p'],x['q'],x['quadrant'],x['evidence'],row.result['global']['I'],row.result['global']['p'],row.permutations,row.seed,row.result['input_hash'],' '.join(requested),summary.get('completed',0),summary.get('invalid',0)])
    return o.getvalue()
def export_sensitivity(db,rid):
    row=_sensitivity_guard(db,rid);sensitivity=row.result.get("sensitivity")
    if not sensitivity:raise HTTPException(409,"该研究尚无单格剔除敏感性结果")
    o=io.StringIO();w=csv.writer(o)
    w.writerow(['drop_cell','status','reason_code','reason','remaining_n','global_I','global_p','base_global_I','base_global_p','delta_I','delta_p','evidence_count','base_evidence_common','plan_evidence_common','delta_evidence_common','common_cell','base_q','plan_q','base_evidence','plan_evidence','change','sensitivity_hash'])
    shash=sensitivity.get("sensitivity_hash","")
    for plan in sensitivity.get("plans",[]):
        g=plan.get("global") or {};comp=plan.get("comparison") or {}
        head=[plan["drop_cell"],plan["status"],plan.get("reason_code",""),plan.get("reason",""),plan.get("remaining_n",0),g.get("I",""),g.get("p",""),g.get("base_I",""),g.get("base_p",""),g.get("delta_I",""),g.get("delta_p",""),plan.get("evidence_count",0),comp.get("base_evidence_count_common",""),comp.get("plan_evidence_count_common",""),comp.get("delta_evidence_count","")]
        if plan["status"]!="completed":w.writerow(head+['','','','','','',shash]);continue
        base_by={x['cell']['code']:x for x in row.result['local'] if x['cell']['code']!=plan['drop_cell']}
        for cell in plan.get("local",[]):
            code=cell['cell']['code'];b=base_by.get(code)
            change='unchanged'
            if b is not None and bool(b['evidence'])!=bool(cell['evidence']):change='lost' if b['evidence'] else 'gained'
            w.writerow(head+[code,b['q'] if b else '',cell['q'],b['evidence'] if b else '',cell['evidence'],change,shash])
    return o.getvalue()
