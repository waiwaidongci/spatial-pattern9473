from pydantic import BaseModel,Field,field_validator
from ..services.analysis_service import clean_sensitivity_cells
class RunInput(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    survey_id:int
    permutations:int=Field(default=499,ge=499,le=999,strict=True)
    seed:int=Field(default=2026,ge=0,le=2147483647,strict=True)
    sensitivity_cells:list[str]=Field(default_factory=list,max_length=20)
    @field_validator('sensitivity_cells')
    @classmethod
    def valid_cells(cls,cells):return clean_sensitivity_cells(cells)
class SensitivityInput(BaseModel):
    sensitivity_cells:list[str]=Field(default_factory=list,max_length=20)
    @field_validator('sensitivity_cells')
    @classmethod
    def valid_cells(cls,cells):return clean_sensitivity_cells(cells)
