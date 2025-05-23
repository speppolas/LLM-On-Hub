# from pydantic import BaseModel, Field, validator, ValidationError
# from typing import Optional, List, Dict

# class ClinicalFeatures(BaseModel):
#     age: Optional[int] = Field(None, ge=0, le=120)
#     gender: Optional[str] = Field(None, pattern=r"^(male|female|not mentioned)$")
#     diagnosis: Optional[str] = Field(None, pattern=r"^(NSCLC|SCLC|other|not mentioned)$")
#     stage: Optional[str] = Field(None, pattern=r"^(I|II|III|IV|not mentioned)$")
#     ecog: Optional[str] = Field(None, pattern=r"^(0|1|2|3|4|not mentioned)$")
#     mutations: List[str] = []
#     metastases: List[str] = []
#     previous_treatments: List[str] = []
#     lab_values: Dict[str, str] = {}

#     @validator("gender", "diagnosis", "stage", "ecog", pre=True, always=True)
#     def null_or_valid(cls, v):
#         if v is None or v == "null":
#             return "not mentioned"
#         return v

#     @validator("mutations", "metastases", "previous_treatments", pre=True, always=True)
#     def ensure_list(cls, v):
#         return v if isinstance(v, list) else []

#     @validator("lab_values", pre=True, always=True)
#     def ensure_dict(cls, v):
#         return v if isinstance(v, dict) else {}
from pydantic import BaseModel, Field, validator, ValidationError
from typing import Optional, List, ClassVar

class ClinicalFeatures(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120, description="Age of the patient as an integer or null")
    
    gender: str = Field(
        ...,
        pattern=r"^(male|female|not mentioned)$",
        description="Gender of the patient"
    )
    
    diagnosis: str = Field(
        ...,
        pattern=r"^(NSCLC|SCLC|adenocarcinoma|squamous cell lung cancer|other|not mentioned)$",
        description="Diagnosis of the patient"
    )
    
    stage: str = Field(
        ...,
        pattern=r"^(I|II|III|IV|not mentioned)$",
        description="Cancer stage of the patient"
    )
    
    ecog_ps: str = Field(
        ...,
        pattern=r"^(0|1|2|3|4|not mentioned)$",
        description="ECOG Performance Status"
    )
    
    mutations: List[str] = Field(
        default_factory=list,
        description="List of detected genetic mutations (strictly controlled)"
    )
    
    metastases: List[str] = Field(
        default_factory=list,
        description="List of metastasis locations (strictly controlled)"
    )
    
    previous_treatments: List[str] = Field(
        default_factory=list,
        description="List of previous treatments (strictly controlled)"
    )
    
    PD_L1: str = Field(
        ...,
        pattern=r"^(<1%|1-49%|>50%|not mentioned)$",
        description="PD-L1 expression level"
    )

    # Allowed values as Class Variables (not fields)
    ALLOWED_MUTATIONS: ClassVar[set] = {
        "EGFR", "ALK", "ROS1", "BRAF V600E", "KRAS", "HER2", 
        "PD-L1", "NTRK", "RET", "MET", "not mentioned"
    }
    
    ALLOWED_METASTASES: ClassVar[set] = {
        "brain", "liver", "bone", "lymph nodes", "adrenal", 
        "peritoneal", "pleural", "skin", "not mentioned"
    }
    
    ALLOWED_TREATMENTS: ClassVar[set] = {
        "chemotherapy", "radiation", "surgery", "immunotherapy", 
        "carboplatin", "cisplatin", "paclitaxel", "docetaxel", 
        "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", 
        "osimertinib", "erlotinib", "gefitinib", "crizotinib", 
        "alectinib", "not mentioned"
    }

    @validator("mutations", pre=True, always=True)
    def validate_mutations(cls, value):
        if not isinstance(value, list):
            raise ValueError("Mutations must be a list.")
        for mutation in value:
            if mutation not in cls.ALLOWED_MUTATIONS:
                raise ValueError(f"Invalid mutation: {mutation}. Allowed values are: {cls.ALLOWED_MUTATIONS}")
        return value if value else ["not mentioned"]

    @validator("metastases", pre=True, always=True)
    def validate_metastases(cls, value):
        if not isinstance(value, list):
            raise ValueError("Metastases must be a list.")
        for metastasis in value:
            if metastasis not in cls.ALLOWED_METASTASES:
                raise ValueError(f"Invalid metastasis: {metastasis}. Allowed values are: {cls.ALLOWED_METASTASES}")
        return value if value else ["not mentioned"]

    @validator("previous_treatments", pre=True, always=True)
    def validate_treatments(cls, value):
        if not isinstance(value, list):
            raise ValueError("Previous treatments must be a list.")
        for treatment in value:
            if treatment not in cls.ALLOWED_TREATMENTS:
                raise ValueError(f"Invalid treatment: {treatment}. Allowed values are: {cls.ALLOWED_TREATMENTS}")
        return value if value else ["not mentioned"]

