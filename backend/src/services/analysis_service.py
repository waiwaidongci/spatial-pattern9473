import numpy as np
from .graph_service import prepare_graph,centered_values
from .moran_algorithm import global_permutations,local_permutations
from .moran_algorithm import benjamini_hochberg
from ..utils.fingerprint import fingerprint
VERSION="row-moran-conditional-bh-v1"
def analyze_spatial(snapshot,permutations=499,seed=2026):
    if type(permutations) is not int or not 499<=permutations<=999:raise ValueError("置换次数须为499–999整数")
    if type(seed) is not int or not 0<=seed<=2147483647:raise ValueError("种子须为0–2147483647整数")
    cells,W,graph=prepare_graph(snapshot['cells'],snapshot['edges'])
    if len(cells)*permutations>64000:raise ValueError("格数×置换次数不得超过64000")
    z,m2,centering=centered_values([c['value'] for c in cells]);streams=np.random.SeedSequence(seed).spawn(len(cells)+1)
    global_result=global_permutations(z,W,permutations,np.random.default_rng(streams[0]));local=local_permutations(z,W,permutations,streams[1:]);q=benjamini_hochberg([x['p'] for x in local])
    for cell,res,adjusted in zip(cells,local,q):res.update({"cell":cell,"q":adjusted,"evidence":adjusted<=.05})
    canonical={"survey":snapshot['survey'],"cells":cells,"edges":sorted([{"a":min(e['a'],e['b']),"b":max(e['a'],e['b'])} for e in snapshot['edges']],key=lambda e:(e['a'],e['b']))}
    return {"algorithm_version":VERSION,"survey":snapshot['survey'],"graph":graph,"centering":centering,"global":global_result,"local":local,"permutations":permutations,"seed":seed,"resolution":1/(permutations+1),"evidence_count":sum(x['evidence'] for x in local),"input_snapshot":canonical,"input_hash":fingerprint({"version":VERSION,"snapshot":canonical,"B":permutations,"seed":seed}),"assumptions":"全局标签在给定图上可交换；局部固定自身值，从其余n−1个值无放回抽取邻居。邻接定义和分析尺度影响结果。仅为空间关联，不能推断点位因果或保证行动效果。","bh_note":"BH覆盖全部有效格，q≤0.05作探索筛选；空间依赖下标准BH的FDR保证不普遍成立。HH/LL/HL/LH只表示符号象限，不能单独作为显著聚集证据。"}
