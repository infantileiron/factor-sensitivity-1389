from pydantic import BaseModel,ConfigDict,Field
class CorrectionCreate(BaseModel):
 model_config=ConfigDict(extra='forbid')
 report_id:str
 replacement_run_id:str
 reason:str=Field(min_length=8,max_length=4000)
class CorrectionDecision(BaseModel):
 model_config=ConfigDict(extra='forbid')
 note:str=Field(default='',max_length=4000)
