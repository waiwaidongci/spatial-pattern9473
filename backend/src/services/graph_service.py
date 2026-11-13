"""Validate an undirected simple graph and row-standardize binary adjacency."""
import numpy as np

def prepare_graph(cells,edges):
    if not isinstance(cells,list) or not isinstance(edges,list):raise ValueError("网格和边须为列表")
    if any(not isinstance(c,dict) or not isinstance(c.get('code'),str) or not c['code'] for c in cells):raise ValueError("网格须包含非空字符串编号")
    if not 4<=len(cells)<=100:raise ValueError("要求4–100个有效格")
    ordered=sorted(cells,key=lambda c:c['code']);codes=[c['code'] for c in ordered]
    if len(set(codes))!=len(codes):raise ValueError("网格编号重复")
    index={c:i for i,c in enumerate(codes)};adj=np.zeros((len(codes),len(codes)));seen=set()
    for e in edges:
        if not isinstance(e,dict) or not isinstance(e.get('a'),str) or not isinstance(e.get('b'),str):raise ValueError("邻接边须包含字符串端点a和b")
        a,b=e['a'],e['b']
        if a not in index or b not in index:raise ValueError("邻接边引用未知网格")
        if a==b:raise ValueError("邻接图禁止自环")
        pair=tuple(sorted((a,b)))
        if pair in seen:raise ValueError("无向邻接边重复")
        seen.add(pair);i,j=index[a],index[b];adj[i,j]=adj[j,i]=1.
    degree=adj.sum(axis=1)
    if np.any(degree==0):raise ValueError("存在孤点；本研究不定义孤点的空间滞后")
    W=adj/degree[:,None]
    return ordered,W,{"n":len(codes),"edges":len(seen),"S0":float(W.sum()),"min_degree":int(degree.min()),"max_degree":int(degree.max()),"weight_rule":"无向二元邻接，按每一行邻居数标准化；W通常不再对称。"}

def centered_values(values):
    try:x=np.asarray(values,dtype=float)
    except (TypeError,ValueError,OverflowError):raise ValueError("观测须为有限数值")
    if x.ndim!=1 or len(x)<4 or not np.isfinite(x).all() or np.max(np.abs(x))>1e9:raise ValueError("观测须为至少4个有限数值，绝对值不超过1e9")
    # Translation followed by normalization avoids an absolute variance threshold.
    shifted=x-x[0];scale=float(np.max(np.abs(shifted)))
    if scale==0:raise ValueError("观测恒定，Moran统计量未定义")
    unit=shifted/scale;mean_unit=float(np.mean(unit));z=unit-mean_unit;m2=float(z@z/len(z))
    if not m2>0:raise ValueError("观测在浮点精度下不可分辨，方差为零")
    return z,m2,{"mean":float(x[0]+scale*mean_unit),"value_scale":scale,"center_note":"先相对首值平移并按最大差缩放，避免绝对小方差阈值；统计量对平移和正比例不变。"}
