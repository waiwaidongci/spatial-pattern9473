from sqlalchemy import String,Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class SpatialSurvey(Base):
    __tablename__="spatial_surveys"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    name:Mapped[str]
    period:Mapped[str]
    description:Mapped[str]=mapped_column(Text)
    source:Mapped[str]
    cell_size_m:Mapped[int]=mapped_column(default=250)
