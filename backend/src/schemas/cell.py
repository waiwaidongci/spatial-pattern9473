from pydantic import BaseModel,Field
class CellOutput(BaseModel):
    id:int
    survey_id:int
    code:str
    row:int
    col:int
    value:float
    note:str
class CellAnnotation(BaseModel):
    note:str=Field(min_length=8,max_length=1500)
