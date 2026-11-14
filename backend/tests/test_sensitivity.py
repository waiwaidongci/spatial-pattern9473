import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.analysis_service import analyze_spatial,analyze_sensitivity,clean_sensitivity_cells,run_hash,sensitivity_hash,MAX_SENSITIVITY_PLANS
from src.services.moran_algorithm import benjamini_hochberg
def grid(n=6,m=6,base=60.,step=1.):
    cells=[];edges=[]
    for r in range(n):
        for c in range(m):
            cells.append({"code":f"C{r:02}-{c:02}","row":r,"col":c,"value":base+step*(r*m+c),"note":"synthetic"})
            for dr,dc in [(0,1),(1,0)]:
                if r+dr<n and c+dc<m:edges.append({"a":f"C{r:02}-{c:02}","b":f"C{r+dr:02}-{c+dc:02}"})
    return {"survey":{"id":1,"code":"T-1","name":"test","period":"2026-01-01"},"cells":cells,"edges":edges}
def island():
    # Six-cell chain: removing B or E isolates a leaf; removing A or D keeps a valid graph.
    codes=["A","B","C","D","E","F"]
    return {"survey":{"id":2,"code":"T-2","name":"island","period":"2026-01-01"},
            "cells":[{"code":c,"row":0,"col":i,"value":61.+i,"note":"x"} for i,c in enumerate(codes)],
            "edges":[{"a":"A","b":"B"},{"a":"B","b":"C"},{"a":"C","b":"D"},{"a":"D","b":"E"},{"a":"E","b":"F"}]}
def with_sensitivity(snap,codes):
    out=dict(snap);out["sensitivity"]={"cells":codes};return out
def test_base_results_do_not_depend_on_sensitivity_list():
    snap=grid()
    base=analyze_spatial(snap,499,2026)
    tagged=analyze_spatial(with_sensitivity(snap,["C00-00","C05-05"]),499,2026)
    assert base["global"]["I"]==tagged["global"]["I"]
    assert base["global"]["p"]==tagged["global"]["p"]
    assert [x["p"] for x in base["local"]]==[x["p"] for x in tagged["local"]]
    assert base["local"][0]["null"]==tagged["local"][0]["null"]
    assert base["input_hash"]==tagged["input_hash"]
    assert base["sensitivity"]["sensitivity_hash"]!=tagged["sensitivity"]["sensitivity_hash"]
def test_sensitivity_plan_rebuilds_graph_and_bh_over_remaining_cells():
    snap=with_sensitivity(grid(),["C02-03"])
    plan=analyze_spatial(snap,499,2026)["sensitivity"]["plans"][0]
    assert plan["status"]=="completed"
    assert plan["remaining_n"]==35
    assert plan["graph"]["n"]==35 and plan["graph"]["S0"]==35
    assert all(x["cell"]["code"]!="C02-03" for x in plan["local"])
    assert len(plan["local"])==35
    assert plan["evidence_count"]==sum(x["evidence"] for x in plan["local"])
    q=benjamini_hochberg([x["p"] for x in plan["local"]])
    assert [round(x,12) for x in q]==[round(x["q"],12) for x in plan["local"]]
    assert plan["comparison"]["common_cells"]==35
    assert plan["graph"]["edges"]<112
def test_dropped_cell_never_counts_as_lost_evidence():
    snap=grid();base=analyze_spatial(snap,499,2026)
    drop=next((x["cell"]["code"] for x in base["local"] if x["evidence"]),"C02-02")
    plan=analyze_spatial(with_sensitivity(snap,[drop]),499,2026)["sensitivity"]["plans"][0]
    assert plan["status"]=="completed"
    assert drop not in plan["comparison"]["lost_evidence"]
    assert drop not in plan["comparison"]["gained_evidence"]
    assert drop not in plan["comparison"]["changed_cells"]
    assert plan["comparison"]["dropped_cell_excluded"] is True
    assert plan["comparison"]["common_cells"]==35
    # The dropped cell's own evidence status is reported separately, not as a loss.
    assert plan["comparison"]["dropped_cell_is_evidence"]==next(x["evidence"] for x in base["local"] if x["cell"]["code"]==drop)
def test_isolated_result_is_reported_without_stopping_other_plans():
    res=analyze_spatial(with_sensitivity(island(),["B","E","A"]),499,2026)
    by={p["drop_cell"]:p for p in res["sensitivity"]["plans"]}
    assert by["B"]["status"]=="invalid" and by["B"]["reason_code"]=="isolated_cell"
    assert by["E"]["status"]=="invalid" and by["E"]["reason_code"]=="isolated_cell"
    assert by["A"]["status"]=="completed" and len(by["A"]["local"])==5
    assert res["sensitivity"]["summary"]=={"requested":3,"completed":1,"invalid":2,"invalid_cells":["B","E"]}
def test_constant_after_removal_is_invalid():
    # Six cells: five constant 62 dBA plus one 70 dBA. Dropping the 70 leaves a constant grid,
    # which has an undefined Moran statistic even though the graph is still connected.
    snap={"survey":{"id":3,"code":"T-3","name":"const","period":"2026-01-01"},
          "cells":[{"code":c,"row":i//3,"col":i%3,"value":70. if c=="F" else 62.,"note":"x"} for i,c in enumerate("ABCDEF")],
          "edges":[{"a":"A","b":"B"},{"a":"A","b":"C"},{"a":"B","b":"D"},{"a":"C","b":"D"},{"a":"C","b":"E"},{"a":"B","b":"E"},{"a":"D","b":"F"},{"a":"E","b":"F"}]}
    res=analyze_spatial(with_sensitivity(snap,["F"]),499,2026)
    plan=res["sensitivity"]["plans"][0]
    assert plan["status"]=="invalid" and plan["reason_code"]=="constant_values"
    assert "恒定" in plan["reason"]
    assert plan["local"]==[] and plan["global"] is None
def test_too_few_cells_after_removal_is_invalid():
    snap={"survey":{"id":4,"code":"T-4","name":"four","period":"2026-01-01"},
          "cells":[{"code":c,"row":0,"col":i,"value":61.+i,"note":"x"} for i,c in enumerate("ABCD")],
          "edges":[{"a":"A","b":"B"},{"a":"A","b":"C"},{"a":"B","b":"D"},{"a":"C","b":"D"}]}
    plan=analyze_spatial(with_sensitivity(snap,["A"]),499,2026)["sensitivity"]["plans"][0]
    assert plan["status"]=="invalid" and plan["reason_code"]=="too_few_cells"
def test_input_order_and_edge_orientation_do_not_change_results_or_hash():
    snap=grid();shuffled=dict(snap)
    rng=np.random.default_rng(7)
    cells=list(snap["cells"]);rng.shuffle(cells)
    edges=[{"a":e["b"],"b":e["a"]} for e in snap["edges"]];rng.shuffle(edges)
    shuffled["cells"]=cells;shuffled["edges"]=edges
    a=analyze_spatial(snap,499,2026);b=analyze_spatial(shuffled,499,2026)
    assert a["input_hash"]==b["input_hash"]
    assert a["global"]["I"]==b["global"]["I"]
    assert [x["cell"]["code"] for x in a["local"]]==[x["cell"]["code"] for x in b["local"]]
    assert [x["p"] for x in a["local"]]==[x["p"] for x in b["local"]]
    c=analyze_spatial(with_sensitivity(snap,["C01-01","C04-04"]),499,2026)
    d=analyze_spatial(with_sensitivity(shuffled,["C04-04","C01-01"]),499,2026)
    assert c["input_hash"]==d["input_hash"] and c["sensitivity"]==d["sensitivity"]
def test_plan_streams_are_independent_of_other_requested_plans():
    snap=grid()
    one=analyze_spatial(with_sensitivity(snap,["C01-01"]),499,2026)["sensitivity"]["plans"]
    many=analyze_spatial(with_sensitivity(snap,["C00-05","C01-01","C04-02"]),499,2026)["sensitivity"]["plans"]
    by={p["drop_cell"]:p for p in many}
    assert [p["drop_cell"] for p in many]==["C00-05","C01-01","C04-02"]
    assert by["C01-01"]==one[0]
def test_invalid_plan_does_not_change_neighbours():
    first=analyze_spatial(with_sensitivity(island(),["A","B","D"]),499,2026)["sensitivity"]["plans"]
    second=analyze_spatial(with_sensitivity(island(),["A","D"]),499,2026)["sensitivity"]["plans"]
    by_first={p["drop_cell"]:p for p in first};by_second={p["drop_cell"]:p for p in second}
    assert by_first["B"]["status"]=="invalid"
    assert by_first["A"]==by_second["A"] and by_first["D"]==by_second["D"]
def test_recompute_from_stored_result_reproduces_sensitivity_block():
    snap=grid();res=analyze_spatial(snap,499,2026)
    stored=dict(res);stored["sensitivity"]={"enabled":False,"plans":[]}
    tag=with_sensitivity(snap,["C02-02"])
    recomputed=analyze_sensitivity(tag,stored,499,2026,["C02-02"])
    fresh=analyze_spatial(tag,499,2026)["sensitivity"]
    assert recomputed["plans"][0]["global"]==fresh["plans"][0]["global"]
    assert [x["q"] for x in recomputed["plans"][0]["local"]]==[x["q"] for x in fresh["plans"][0]["local"]]
    assert recomputed["sensitivity_hash"]==fresh["sensitivity_hash"]
    assert stored["global"]==res["global"] and stored["input_hash"]==res["input_hash"]
def test_unknown_cells_and_cleanup_validation():
    plan=analyze_spatial(with_sensitivity(grid(),["NOPE"]),499,2026)["sensitivity"]["plans"][0]
    assert plan["status"]=="invalid" and plan["reason_code"]=="unknown_cell"
    assert clean_sensitivity_cells(["B","A","A"])==["A","B"]
    with pytest.raises(ValueError):clean_sensitivity_cells([""])
    with pytest.raises(ValueError):clean_sensitivity_cells([f"Z{i}" for i in range(MAX_SENSITIVITY_PLANS+1)])
def test_hash_is_order_insensitive_and_sensitivity_sensitive():
    snap=grid();a=dict(snap);a["cells"]=list(reversed(snap["cells"]))
    assert run_hash(snap,499,2026)==run_hash(a,499,2026)
    # input_hash covers the base snapshot only; sensitivity_hash covers the exclusion list.
    assert run_hash(with_sensitivity(snap,["C01-01"]),499,2026)==run_hash(snap,499,2026)
    assert sensitivity_hash(with_sensitivity(snap,["C01-01"]),499,2026)!=sensitivity_hash(snap,499,2026)
    tagged=analyze_spatial(with_sensitivity(snap,["C01-01","C02-02"]),499,2026)
    assert tagged["input_hash"]==analyze_spatial(snap,499,2026)["input_hash"]
    assert tagged["sensitivity"]["requested"]==["C01-01","C02-02"]
def test_zero_sensitivity_request_keeps_block_disabled():
    res=analyze_spatial(grid(),499,2026)
    assert res["sensitivity"]["enabled"] is False and res["sensitivity"]["plans"]==[]
