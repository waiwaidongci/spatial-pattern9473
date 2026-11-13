import numpy as np
from .graph_service import centered_values

def global_statistic(z,W):
    z=np.asarray(z,dtype=float);return float(len(z)/W.sum()*(z@(W@z))/(z@z))
def local_statistics(z,W):
    z=np.asarray(z,dtype=float);return z*(W@z)/(z@z/len(z))
def conditional_expectations(z):
    z=np.asarray(z,dtype=float);return -z*z/((len(z)-1)*(z@z/len(z)))
def two_sided_p(observed,null,center):
    null=np.asarray(null,dtype=float)
    # Dimensionless floating-point tie tolerance, not a variance rejection rule.
    tol=64*np.finfo(float).eps*max(1.,abs(observed),abs(center),float(np.max(np.abs(null))))
    extreme=int(np.sum(np.abs(null-center)>=abs(observed-center)-tol))
    return (extreme+1)/(len(null)+1),extreme,tol

def global_permutations(z,W,B,rng):
    observed=global_statistic(z,W);center=-1/(len(z)-1);null=[global_statistic(rng.permutation(z),W) for _ in range(B)];p,k,tol=two_sided_p(observed,null,center)
    return {"I":observed,"expected":center,"p":p,"extreme":k,"null":null,"tie_tolerance":tol,"tail":"双侧，比较|I−E[I]|，E[I]=−1/(n−1)，+1 Monte Carlo校正"}

def local_permutations(z,W,B,streams):
    n=len(z);m2=float(z@z/n);observed=local_statistics(z,W);expected=conditional_expectations(z);lag=W@z;out=[]
    for i in range(n):
        others=np.delete(z,i);degree=int(np.count_nonzero(W[i]));rng=np.random.default_rng(streams[i])
        # All row weights are equal: sample k distinct other labels then take mean.
        null=[float(z[i]*np.mean(rng.choice(others,size=degree,replace=False))/m2) for _ in range(B)]
        p,k,tol=two_sided_p(float(observed[i]),null,float(expected[i]));a,b=float(z[i]/np.sqrt(m2)),float(lag[i]/np.sqrt(m2))
        quadrant='HH' if a>0 and b>0 else 'LL' if a<0 and b<0 else 'HL' if a>0 and b<0 else 'LH' if a<0 and b>0 else 'AXIS'
        out.append({"I":float(observed[i]),"expected":float(expected[i]),"p":p,"extreme":k,"null":null,"tie_tolerance":tol,"z":a,"lag":b,"degree":degree,"quadrant":quadrant,"spawn_key":list(streams[i].spawn_key)})
    return out


def benjamini_hochberg(p_values):
    p=np.asarray(p_values,dtype=float)
    if p.ndim!=1 or len(p)==0 or not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError("BH输入须为非空[0,1]有限p值")
    m=len(p);order=np.argsort(p,kind='stable');adjusted=np.minimum.accumulate((p[order]*m/np.arange(1,m+1))[::-1])[::-1];out=np.empty(m);out[order]=np.clip(adjusted,0,1);return out.tolist()
