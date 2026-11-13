from pydantic import BaseModel
class EdgeOutput(BaseModel):
    id:int
    survey_id:int
    a:str
    b:str
