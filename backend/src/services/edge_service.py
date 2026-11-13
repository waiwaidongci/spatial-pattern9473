from ..models import NeighborEdge
from ..utils.serialize import record
from .survey_service import get_survey

def list_edges(db,sid):get_survey(db,sid);return [record(e) for e in db.query(NeighborEdge).filter_by(survey_id=sid).order_by(NeighborEdge.a,NeighborEdge.b)]
