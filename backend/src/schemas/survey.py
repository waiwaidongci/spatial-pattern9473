from pydantic import BaseModel
class SurveyOutput(BaseModel):
    id:int
    code:str
    name:str
    period:str
    description:str
    source:str
    cell_size_m:int
    cell_count:int
    edge_count:int
    supported:bool
    reason:str
