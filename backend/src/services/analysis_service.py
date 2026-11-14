import hashlib
import numpy as np
from .graph_service import prepare_graph,centered_values
from .moran_algorithm import global_permutations,local_permutations,benjamini_hochberg
from ..utils.fingerprint import fingerprint
from ..constants.analysis import VERSION,SENSITIVITY_SCOPE,SENSITIVITY_STREAM,SENSITIVITY_NULL_NOTE,SENSITIVITY_DROP_NOTE
SENSITIVITY_BUDGET=12000000
EVIDENCE_THRESHOLD=.05
MAX_SENSITIVITY_PLANS=20
MIN_CELLS=4
def requested_cells(snapshot):
    raw=snapshot.get('sensitivity') if isinstance(snapshot,dict) else None
    if isinstance(raw,dict):raw=raw.get('cells')
    if not isinstance(raw,list):return []
    return sorted({c for c in raw if isinstance(c,str) and c})
def _clean_cells(cells):
    if not isinstance(cells,list):raise ValueError("单格剔除清单须为字符串列表")
    if any(not isinstance(c,str) or not c.strip() for c in cells):raise ValueError("单格剔除清单包含空值或非字符串")
    cleaned=sorted({c.strip() for c in cells})
    if len(cleaned)>MAX_SENSITIVITY_PLANS:raise ValueError(f"单格剔除方案不得超过{MAX_SENSITIVITY_PLANS}个")
    return cleaned
def clean_sensitivity_cells(cells):return _clean_cells(cells)
def check_budget(n,permutations,plans):
    if (1+plans)*n*permutations>SENSITIVITY_BUDGET:raise ValueError("格数×置换次数×(1+单格剔除方案数)不得超过12000000")
def canonical_snapshot(snapshot):
    return {"survey":snapshot['survey'],"cells":sorted(snapshot['cells'],key=lambda c:c['code']),"edges":sorted([{"a":min(e['a'],e['b']),"b":max(e['a'],e['b'])} for e in snapshot['edges']],key=lambda e:(e['a'],e['b']))}
def run_hash(snapshot,permutations,seed):
    # Base-input fingerprint: canonical snapshot, B and seed. Row order and edge orientation
    # are normalized away. The exclusion list is deliberately not included, so appending or
    # changing a sensitivity plan never invalidates the stored base input_hash; it is covered
    # by sensitivity_hash below.
    return fingerprint({"version":VERSION,"snapshot":canonical_snapshot(snapshot),"B":permutations,"seed":seed})
def sensitivity_hash(snapshot,permutations,seed):
    # Covers base inputs plus the sorted exclusion list, so the per-plan recomputation is
    # checkable independently of input_hash.
    return fingerprint({"version":VERSION,"part":"sensitivity","snapshot":canonical_snapshot(snapshot),"B":permutations,"seed":seed,"sensitivity":requested_cells(snapshot)})
def _remaining(cells,edges,drop):
    return [c for c in cells if c['code']!=drop],[e for e in edges if e['a']!=drop and e['b']!=drop]
def _isolated_codes(cells,edges):
    degree={c['code']:0 for c in cells}
    for e in edges:
        if e['a'] in degree:degree[e['a']]+=1
        if e['b'] in degree:degree[e['b']]+=1
    return sorted(c for c,d in degree.items() if d==0)
def _invalid_plan(code,reason_code,reason,remaining_n=0):
    return {"drop_cell":code,"status":"invalid","reason_code":reason_code,"reason":reason,"remaining_n":remaining_n,"graph":None,"centering":None,"global":None,"local":[],"evidence_count":0,"comparison":None}
def _common_comparison(base_local,plan_local,drop,drop_is_evidence):
    # Both sides exclude the dropped cell by construction, so it can never count as lost evidence.
    common=[x['cell']['code'] for x in plan_local if x['cell']['code']!=drop]
    base_by_code={x['cell']['code']:x for x in base_local if x['cell']['code']!=drop}
    plan_by_code={x['cell']['code']:x for x in plan_local if x['cell']['code']!=drop}
    lost=[c for c in common if bool(base_by_code[c]['evidence']) and not bool(plan_by_code[c]['evidence'])]
    gained=[c for c in common if bool(plan_by_code[c]['evidence']) and not bool(base_by_code[c]['evidence'])]
    base_evidence=sum(bool(base_by_code[c]['evidence']) for c in common)
    plan_evidence=sum(bool(plan_by_code[c]['evidence']) for c in common)
    return {"common_cells":len(common),"base_evidence_count_common":base_evidence,"plan_evidence_count_common":plan_evidence,"delta_evidence_count":plan_evidence-base_evidence,"lost_evidence":lost,"gained_evidence":gained,"changed_cells":[c for c in common if bool(base_by_code[c]['evidence'])!=bool(plan_by_code[c]['evidence'])],"unchanged_evidence":len(common)-len(lost)-len(gained),"dropped_cell_excluded":True,"dropped_cell_is_evidence":drop_is_evidence,"note":"共同格仅指剔除后仍存在的格；剔除格本身不计入失去证据。"}
def _plan(snapshot_cells,snapshot_edges,drop,permutations,streams,base_global,base_local):
    if drop not in {c['code'] for c in snapshot_cells}:return _invalid_plan(drop,"unknown_cell","指定格不在建单快照中",len(snapshot_cells))
    sub_cells,sub_edges=_remaining(snapshot_cells,snapshot_edges,drop)
    remaining_n=len(sub_cells)
    if remaining_n<MIN_CELLS:return _invalid_plan(drop,"too_few_cells",f"剔除后剩余格少于{MIN_CELLS}个，无法定义局部检验",remaining_n)
    isolated=_isolated_codes(sub_cells,sub_edges)
    if isolated:return _invalid_plan(drop,"isolated_cell","剔除后剩余图存在孤点（"+"、".join(isolated)+"），空间滞后未定义",remaining_n)
    try:ordered,sub_W,sub_graph=prepare_graph(sub_cells,sub_edges)
    except ValueError as e:return _invalid_plan(drop,"graph_invalid","剔除后邻接图无效："+str(e),remaining_n)
    try:z,m2,centering=centered_values([c['value'] for c in ordered])
    except ValueError as e:
        constant=len({float(c['value']) for c in ordered})==1
        return _invalid_plan(drop,"constant_values" if constant else "unresolvable_values",("剔除后剩余观测恒定，Moran统计量未定义" if constant else "剔除后剩余观测不可分辨："+str(e)),remaining_n)
    global_result=global_permutations(z,sub_W,permutations,np.random.default_rng(streams[0]),keep_null=False)
    local=local_permutations(z,sub_W,permutations,streams[1:],keep_null=False)
    q=benjamini_hochberg([x['p'] for x in local])
    for cell,res,adjusted in zip(ordered,local,q):
        res.update({"cell":{"code":cell['code'],"row":cell.get('row'),"col":cell.get('col'),"value":cell.get('value')},"q":adjusted,"evidence":adjusted<=EVIDENCE_THRESHOLD})
    comparison=_common_comparison(base_local,local,drop,any(x['cell']['code']==drop and x['evidence'] for x in base_local))
    global_result.update({"base_I":base_global['I'],"base_p":base_global['p'],"delta_I":global_result['I']-base_global['I'],"delta_p":global_result['p']-base_global['p'],"null_included":False})
    return {"drop_cell":drop,"status":"completed","reason_code":"","reason":"","remaining_n":remaining_n,"graph":sub_graph,"centering":centering,"global":global_result,"local":local,"evidence_count":sum(x['evidence'] for x in local),"comparison":comparison}
def plan_streams(seed,code,n):
    # Stable per-cell derivation: a plan's streams depend only on the root seed and its code,
    # so adding/removing other requested plans never changes an existing plan's draws.
    digest=int.from_bytes(hashlib.sha256(code.encode()).digest()[:8],"big")
    return np.random.SeedSequence([seed,digest]).spawn(n+1)
def sensitivity_analysis(snapshot,cells,base_global,base_local,permutations,seed,n,requested=None):
    requested=requested_cells(snapshot) if requested is None else sorted(set(requested))
    plans=[_plan(cells,snapshot['edges'],drop,permutations,plan_streams(seed,drop,n),base_global,base_local) for drop in requested]
    block={"enabled":bool(requested),"requested":requested,"scope":SENSITIVITY_SCOPE,"plans":plans,"summary":{"requested":len(requested),"completed":sum(p['status']=='completed' for p in plans),"invalid":sum(p['status']=='invalid' for p in plans),"invalid_cells":[p['drop_cell'] for p in plans if p['status']=='invalid']},"base_reference":{"n":n,"global_I":base_global['I'],"global_p":base_global['p'],"evidence_count":sum(bool(x['evidence']) for x in base_local),"evidence_threshold":EVIDENCE_THRESHOLD},"stream_note":SENSITIVITY_STREAM,"null_note":SENSITIVITY_NULL_NOTE,"drop_note":SENSITIVITY_DROP_NOTE}
    if seed is not None:block["sensitivity_hash"]=sensitivity_hash(snapshot,permutations,seed)
    return block
def analyze_sensitivity(snapshot,result,permutations,seed,requested=None):
    # Recomputes only the sensitivity block from the stored snapshot, original seed and original B.
    cells,_,_=prepare_graph(snapshot['cells'],snapshot['edges'])
    requested=requested_cells(snapshot) if requested is None else sorted(set(requested))
    check_budget(len(cells),permutations,len(requested))
    return sensitivity_analysis(snapshot,cells,result['global'],result['local'],permutations,seed,len(cells),requested)
def analyze_spatial(snapshot,permutations=499,seed=2026):
    if type(permutations) is not int or not 499<=permutations<=999:raise ValueError("置换次数须为499–999整数")
    if type(seed) is not int or not 0<=seed<=2147483647:raise ValueError("种子须为0–2147483647整数")
    cells,W,graph=prepare_graph(snapshot['cells'],snapshot['edges'])
    if len(cells)*permutations>64000:raise ValueError("格数×置换次数不得超过64000")
    requested=requested_cells(snapshot)
    if len(requested)>MAX_SENSITIVITY_PLANS:raise ValueError(f"单格剔除方案不得超过{MAX_SENSITIVITY_PLANS}个")
    check_budget(len(cells),permutations,len(requested))
    z,m2,centering=centered_values([c['value'] for c in cells]);n=len(cells)
    # Base streams keep the v1 layout: first n+1 children of the root seed.
    base_streams=np.random.SeedSequence(seed).spawn(n+1)
    global_result=global_permutations(z,W,permutations,np.random.default_rng(base_streams[0]));local=local_permutations(z,W,permutations,base_streams[1:]);q=benjamini_hochberg([x['p'] for x in local])
    for cell,res,adjusted in zip(cells,local,q):res.update({"cell":cell,"q":adjusted,"evidence":adjusted<=EVIDENCE_THRESHOLD})
    sensitivity=sensitivity_analysis(snapshot,cells,global_result,local,permutations,seed,n,requested)
    return {"algorithm_version":VERSION,"survey":snapshot['survey'],"graph":graph,"centering":centering,"global":global_result,"local":local,"permutations":permutations,"seed":seed,"resolution":1/(permutations+1),"evidence_count":sum(x['evidence'] for x in local),"sensitivity":sensitivity,"input_snapshot":canonical_snapshot(snapshot),"input_hash":run_hash(snapshot,permutations,seed),"assumptions":"全局标签在给定图上可交换；局部固定自身值，从其余n−1个值无放回抽取邻居。邻接定义和分析尺度影响结果。仅为空间关联，不能推断点位因果或保证行动效果。","bh_note":"BH覆盖全部有效格，q≤0.05作探索筛选；空间依赖下标准BH的FDR保证不普遍成立。HH/LL/HL/LH只表示符号象限，不能单独作为显著聚集证据。"}
