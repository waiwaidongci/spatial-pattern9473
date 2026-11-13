import json
import numpy as np
from src.config.database import Base,engine,SessionLocal
from src.models import User,SpatialSurvey,GridCell,NeighborEdge,SpatialRun,SamplingNote
from src.utils.security import hash_password
from src.services.run_service import create_snapshot
from src.services.analysis_service import analyze_spatial

def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for role,name in [("admin","秦榆 · 测绘负责人"),("analyst","陆禾 · 空间研究员"),("viewer","徐原 · 补测阅读者")]:
            email=role+'@longge.demo'
            if not db.query(User).filter_by(email=email).first():db.add(User(email=email,name=name,role=role,password_hash=hash_password('Longge2026!')))
        surveys=[]
        for k,(code,name,period) in enumerate([('LG-01','一期 · 聚集暴露观察','2026-11-01'),('LG-02','二期 · 随机对照观察','2026-11-04'),('LG-03','三期 · 恒定边界观察','2026-11-07')]):
            s=db.query(SpatialSurvey).filter_by(code=code).first()
            if not s:s=SpatialSurvey(code=code,name=name,period=period,description="8×8匿名网格，250m格边，rook共享边邻接；数值为合成噪声暴露均值dBA，不表示具体个人或点位。",source='lg-walk-noise-202611-grid.csv',cell_size_m=250);db.add(s);db.flush()
            rng=np.random.default_rng(220+k)
            for row in range(8):
                for col in range(8):
                    value=62+float(rng.normal(0,2.2))
                    if k==0:value+=12 if row<3 and col<3 else -10 if row>=4 and col>=4 else 0
                    if k==2:value=62.
                    cellcode=f'G{row+1:02}-{col+1:02}'
                    if not db.query(GridCell).filter_by(survey_id=s.id,code=cellcode).first():db.add(GridCell(survey_id=s.id,code=cellcode,row=row,col=col,value=value,note="匿名合成格均值；仅供空间关联研究，需独立补测。"))
                    for dr,dc in [(0,1),(1,0)]:
                        if row+dr<8 and col+dc<8:
                            other=f'G{row+dr+1:02}-{col+dc+1:02}';a,b=sorted((cellcode,other))
                            if not db.query(NeighborEdge).filter_by(survey_id=s.id,a=a,b=b).first():db.add(NeighborEdge(survey_id=s.id,a=a,b=b))
            db.flush();surveys.append(s)
        if not db.query(SpatialRun).filter_by(name='一期网格 · 499次聚集观察').first():
            s=surveys[0];snapshot=create_snapshot(db,s);result=analyze_spatial(snapshot,499,2026);run=SpatialRun(name='一期网格 · 499次聚集观察',survey_id=s.id,permutations=499,seed=2026,input_snapshot=snapshot,status='completed',result=result,owner='陆禾 · 空间研究员');db.add(run);db.flush();db.add(SamplingNote(run_id=run.id,title='一期网格补测研究建议',interpretation='符号象限只表示方向，需结合全部64格BH校正q；关联不能说明点位原因。',proposal='对筛选格及相邻边界做独立时段补测，保持250m尺度与匿名汇总口径。',status='approved',owner='陆禾 · 空间研究员',reviewer='秦榆 · 测绘负责人',review_note='批准研究归档；补测属于验证计划，不把空间关联当作因果结论。'))
        db.commit();print(json.dumps({m.__tablename__:db.query(m).count() for m in [User,SpatialSurvey,GridCell,NeighborEdge,SpatialRun,SamplingNote]},ensure_ascii=False))
if __name__=='__main__':seed()
