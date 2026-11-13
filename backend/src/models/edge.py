from sqlalchemy import String,Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class NeighborEdge(Base):
    __tablename__="neighbor_edges"
    id:Mapped[int]=mapped_column(primary_key=True)
    __table_args__=(UniqueConstraint("survey_id","a","b"),)
    survey_id:Mapped[int]=mapped_column(ForeignKey("spatial_surveys.id"))
    a:Mapped[str]
    b:Mapped[str]
