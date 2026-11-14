"""Upgrade stored v1 runs to v2 without touching the original base results.

Legacy runs keep algorithm_version, input_hash, global and local untouched. The
sensitivity block is appended as disabled so the existing pages render exactly as
before; a researcher can then POST /runs/{id}/sensitivity to fill it in using the
stored snapshot and the original seed.
"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config.database import SessionLocal
from src.models import SpatialRun
from src.services.analysis_service import requested_cells
from src.constants.analysis import SENSITIVITY_SCOPE,SENSITIVITY_STREAM,SENSITIVITY_NULL_NOTE,SENSITIVITY_DROP_NOTE,SENSITIVITY_UPGRADE_NOTE
VERSION="row-moran-conditional-bh-v1"
def disabled_block(run):
    result=run.result or {};base=result.get("global") or {};local=result.get("local") or []
    requested=requested_cells(run.input_snapshot or {})
    return {"enabled":bool(requested),"requested":requested,"scope":SENSITIVITY_SCOPE,"plans":[],"summary":{"requested":len(requested),"completed":0,"invalid":0,"invalid_cells":[]},"base_reference":{"n":(result.get("graph") or {}).get("n",len(local)),"global_I":base.get("I"),"global_p":base.get("p"),"evidence_count":result.get("evidence_count",sum(bool(x.get("evidence")) for x in local)),"evidence_threshold":.05},"stream_note":SENSITIVITY_STREAM,"null_note":SENSITIVITY_NULL_NOTE,"drop_note":SENSITIVITY_DROP_NOTE,"base_result_preserved":True,"upgrade_note":SENSITIVITY_UPGRADE_NOTE}
def upgrade(db,dry_run=False):
    changed=[];skipped=[]
    for run in db.query(SpatialRun).filter(SpatialRun.status=="completed").order_by(SpatialRun.id):
        result=run.result or {}
        if not result.get("global") or not result.get("local"):skipped.append((run.id,"缺少基础结果"));continue
        if "sensitivity" in result:skipped.append((run.id,"已含敏感性块"));continue
        changed.append(run.id)
        if not dry_run:
            updated=dict(result);updated["sensitivity"]=disabled_block(run);run.result=updated
    if not dry_run:db.commit()
    return changed,skipped
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--dry-run",action="store_true");args=parser.parse_args()
    with SessionLocal() as db:
        changed,skipped=upgrade(db,args.dry_run)
    print("upgraded:",changed);[print("skipped",i,why) for i,why in skipped]
