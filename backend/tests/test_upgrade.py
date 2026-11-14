import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config.database import Base
from src.models import SpatialRun
from src.services.analysis_service import analyze_spatial
import scripts.upgrade_results as upgrade_results
def snapshot():
    cells=[];edges=[]
    for r in range(4):
        for c in range(4):
            cells.append({"code":f"C{r:02}-{c:02}","row":r,"col":c,"value":61.+r*2+c,"note":"x"})
            if r<3:edges.append({"a":f"C{r:02}-{c:02}","b":f"C{r+1:02}-{c:02}"})
            if c<3:edges.append({"a":f"C{r:02}-{c:02}","b":f"C{r:02}-{c+1:02}"})
    return {"survey":{"id":1,"code":"T-1","name":"legacy","period":"2026-01-01"},"cells":cells,"edges":edges}
def legacy_result():
    result=analyze_spatial(snapshot(),499,2026)
    result.pop("sensitivity")
    result["algorithm_version"]="row-moran-conditional-bh-v1"
    return result
@pytest.fixture()
def db(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'u.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as session:
        session.add(SpatialRun(name="v1",survey_id=1,permutations=499,seed=2026,input_snapshot=snapshot(),status="completed",result=legacy_result(),owner="analyst"))
        session.add(SpatialRun(name="failed",survey_id=1,permutations=499,seed=2026,input_snapshot=snapshot(),status="failed",result={},owner="analyst"))
        session.commit()
        yield session
def test_upgrade_appends_disabled_block_and_preserves_base(db):
    before=db.query(SpatialRun).first().result
    changed,skipped=upgrade_results.upgrade(db)
    assert changed==[1]
    after=db.query(SpatialRun).first().result
    assert after["sensitivity"]["enabled"] is False
    assert after["sensitivity"]["base_result_preserved"] is True
    assert after["algorithm_version"]==before["algorithm_version"]
    assert after["input_hash"]==before["input_hash"]
    assert after["global"]==before["global"] and after["local"]==before["local"]
    assert after["sensitivity"]["base_reference"]["global_I"]==before["global"]["I"]
    # Failed runs are untouched, and a second upgrade is a no-op.
    assert db.query(SpatialRun).filter_by(name="failed").first().result=={}
    assert upgrade_results.upgrade(db)[0]==[]
def test_dry_run_reports_without_writing(db):
    changed,_=upgrade_results.upgrade(db,dry_run=True)
    assert changed==[1]
    assert "sensitivity" not in db.query(SpatialRun).first().result
def test_upgrade_is_idempotent_when_requested_cells_already_in_snapshot(db):
    run=db.query(SpatialRun).first();snap=dict(run.input_snapshot);snap["sensitivity"]={"cells":["C01-01"]};run.input_snapshot=snap;db.commit()
    upgrade_results.upgrade(db)
    block=db.query(SpatialRun).first().result["sensitivity"]
    assert block["enabled"] is True and block["requested"]==["C01-01"] and block["plans"]==[]
