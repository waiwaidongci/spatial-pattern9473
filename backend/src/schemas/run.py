from pydantic import BaseModel,Field
class RunInput(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    survey_id:int
    permutations:int=Field(default=499,ge=499,le=999,strict=True)
    seed:int=Field(default=2026,ge=0,le=2147483647,strict=True)
