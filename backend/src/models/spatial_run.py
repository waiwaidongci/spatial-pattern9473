from sqlalchemy import String,Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class SpatialRun(Base):
    __tablename__="spatial_runs"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]
    survey_id:Mapped[int]=mapped_column(ForeignKey("spatial_surveys.id"))
    permutations:Mapped[int]
    seed:Mapped[int]
    input_snapshot:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(default="queued")
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str]=mapped_column(Text,default="")
    owner:Mapped[str]
    created_at:Mapped[str]=mapped_column(default=now)
