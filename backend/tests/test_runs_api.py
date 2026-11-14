import csv,io,sys
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config.database import Base,get_db
from src.models import User,SpatialSurvey,GridCell,NeighborEdge,SpatialRun,SamplingNote
from src.utils.security import hash_password
import src.services.run_service as run_service
from src.services.analysis_service import analyze_spatial
from src.routes import runs as runs_route
from src.routes import notes as notes_route
@pytest.fixture()
def env(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'test.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);Session=sessionmaker(bind=engine,expire_on_commit=False)
    class FakeQueue:
        def __init__(self):self.jobs=[]
        def rpush(self,key,value):self.jobs.append(value)
    queue=FakeQueue();monkeypatch.setattr(run_service,"queue",queue)
    with Session() as db:
        for role in ("admin","analyst","viewer"):
            db.add(User(email=role+"@x.demo",name=role,role=role,password_hash=hash_password("pw")))
        s=SpatialSurvey(code="T-1",name="test",period="2026-01-01",description="d",source="s.csv",cell_size_m=250);db.add(s);db.flush()
        for r in range(4):
            for c in range(4):
                db.add(GridCell(survey_id=s.id,code=f"C{r:02}-{c:02}",row=r,col=c,value=62.+r*2+c,note="note"))
                if r<3:db.add(NeighborEdge(survey_id=s.id,a=f"C{r:02}-{c:02}",b=f"C{r+1:02}-{c:02}"))
                if c<3:db.add(NeighborEdge(survey_id=s.id,a=f"C{r:02}-{c:02}",b=f"C{r:02}-{c+1:02}"))
        db.commit();sid=s.id
    from fastapi import Depends
    from src.controllers.dependencies import current_user
    app=FastAPI();app.include_router(runs_route.router);app.include_router(notes_route.router)
    def override_db():
        db=Session()
        try:yield db
        finally:db.close()
    def override_analyst(db=Depends(override_db)):
        return db.query(User).filter_by(email="analyst@x.demo").first()
    app.dependency_overrides[get_db]=override_db
    app.dependency_overrides[current_user]=override_analyst
    client=TestClient(app,raise_server_exceptions=False)
    return client,Session,sid,queue
def _run_once(Session,queue):
    with Session() as db:
        rid=queue.jobs.pop(0);run=db.get(SpatialRun,rid)
        run.result=analyze_spatial(run.input_snapshot,run.permutations,run.seed);run.status="completed";db.commit()
    return rid
def test_create_with_sensitivity_list_and_export(env):
    client,Session,sid,queue=env
    response=client.post("/runs",json={"name":"研究","survey_id":sid,"permutations":499,"seed":2026,"sensitivity_cells":["C01-01","C02-02"]})
    assert response.status_code==202,response.text
    body=response.json();assert body["input_snapshot"]["sensitivity"]["cells"]==["C01-01","C02-02"]
    rid=_run_once(Session,queue)
    detail=client.get(f"/runs/{rid}").json()
    assert detail["result"]["sensitivity"]["summary"]["completed"]==2
    assert detail["result"]["sensitivity"]["summary"]["invalid"]==0
    export=client.get(f"/runs/{rid}/export")
    assert export.status_code==403  # no approved note yet
def test_unknown_cell_is_rejected_at_creation(env):
    client,Session,sid,queue=env
    response=client.post("/runs",json={"name":"研究","survey_id":sid,"sensitivity_cells":["NOPE"]})
    assert response.status_code==422 and "不存在" in response.json()["detail"]
def _rows(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
def test_exports_include_sensitivity_columns_after_approval(env):
    client,Session,sid,queue=env
    response=client.post("/runs",json={"name":"研究","survey_id":sid,"sensitivity_cells":["C00-00"]});rid=response.json()["id"]
    _run_once(Session,queue)
    with Session() as db:
        db.add(SamplingNote(run_id=rid,title="建议标题",interpretation="解释说明足够长",proposal="补测方案足够长",status="approved",owner="analyst",reviewer="admin"));db.commit()
    base=client.get(f"/runs/{rid}/export");assert base.status_code==200
    rows=_rows(base)
    assert rows[0][-3:]==["sensitivity_requested","sensitivity_completed","sensitivity_invalid"]
    assert all(r[-3]=="C00-00" for r in rows[1:])
    assert len(rows)-1==16
    sens=client.get(f"/runs/{rid}/export-sensitivity");assert sens.status_code==200
    srows=_rows(sens);header=srows[0]
    assert header[0]=="drop_cell" and srows[1][0]=="C00-00"
    ci=header.index("common_cell");qi=header.index("plan_q");bi=header.index("base_q");change=header.index("change")
    cells=[r[ci] for r in srows[1:]]
    # The dropped cell's own row is excluded; every remaining cell has base/plan q and a change flag.
    assert "C00-00" not in cells and len(set(cells))==15
    assert all(r[change] in {"unchanged","lost","gained"} for r in srows[1:])
    assert all(0<=float(r[qi])<=1 and 0<=float(r[bi])<=1 for r in srows[1:])
def test_legacy_run_upgrade_preserves_base_and_can_attach(env):
    client,Session,sid,queue=env
    with Session() as db:
        run=db.query(SpatialRun).first()
        if run is None:
            snapshot={"survey":{"id":sid,"code":"T-1","name":"test","period":"2026-01-01"},"cells":[{"code":c.code,"row":c.row,"col":c.col,"value":c.value,"note":c.note,"id":c.id,"survey_id":sid} for c in db.query(GridCell).filter_by(survey_id=sid)],"edges":[{"a":e.a,"b":e.b,"id":e.id,"survey_id":sid} for e in db.query(NeighborEdge).filter_by(survey_id=sid)]}
            legacy=analyze_spatial(snapshot,499,2026);legacy.pop("sensitivity")
            legacy["algorithm_version"]="row-moran-conditional-bh-v1"
            db.add(SpatialRun(name="旧版",survey_id=sid,permutations=499,seed=2026,input_snapshot=snapshot,status="completed",result=legacy,owner="analyst"));db.commit()
        rid=db.query(SpatialRun).order_by(SpatialRun.id.desc()).first().id
    before=client.get(f"/runs/{rid}").json()["result"]
    client.post(f"/runs/{rid}/sensitivity",json={"sensitivity_cells":["C01-01"]})
    after=client.get(f"/runs/{rid}").json()["result"]
    assert after["algorithm_version"]==before["algorithm_version"]
    assert after["input_hash"]==before["input_hash"]
    assert after["global"]==before["global"] and after["local"]==before["local"]
    sensitivity=after["sensitivity"]
    assert sensitivity["base_result_preserved"] is True
    assert sensitivity["plans"][0]["drop_cell"]=="C01-01"
    assert sensitivity["plans"][0]["status"]=="completed"
def test_attach_is_rejected_for_invalid_and_unknown(env):
    client,Session,sid,queue=env
    with Session() as db:
        snapshot={"survey":{"id":sid,"code":"T-1","name":"test","period":"2026-01-01"},"cells":[{"code":c.code,"row":c.row,"col":c.col,"value":c.value,"note":c.note,"id":c.id,"survey_id":sid} for c in db.query(GridCell).filter_by(survey_id=sid)],"edges":[{"a":e.a,"b":e.b,"id":e.id,"survey_id":sid} for e in db.query(NeighborEdge).filter_by(survey_id=sid)]}
        db.add(SpatialRun(name="旧版",survey_id=sid,permutations=499,seed=2026,input_snapshot=snapshot,status="completed",result=analyze_spatial(snapshot,499,2026),owner="analyst"));db.commit()
        rid=db.query(SpatialRun).order_by(SpatialRun.id.desc()).first().id
    assert client.post(f"/runs/{rid}/sensitivity",json={"sensitivity_cells":["NOPE"]}).status_code==422
    assert client.post(f"/runs/{rid}/sensitivity",json={"sensitivity_cells":[]}).status_code==422
    assert client.get("/runs/9999/sensitivity",follow_redirects=False).status_code in {404,405}
