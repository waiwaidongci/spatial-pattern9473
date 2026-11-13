from sqlalchemy import String,Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class GridCell(Base):
    __tablename__="grid_cells"
    id:Mapped[int]=mapped_column(primary_key=True)
    __table_args__=(UniqueConstraint("survey_id","code"),)
    survey_id:Mapped[int]=mapped_column(ForeignKey("spatial_surveys.id"))
    code:Mapped[str]
    row:Mapped[int]
    col:Mapped[int]
    value:Mapped[float]=mapped_column(Double)
    note:Mapped[str]=mapped_column(Text)
