from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class UploadAgreementResponse(BaseModel):
    agreement_id: str
    stored_filename: str


class UploadStandardResponse(BaseModel):
    batch_id: str
    stored_filenames: List[str]


class UploadCombinedResponse(BaseModel):
    agreement_id: str
    agreement_stored_filename: str
    batch_id: str
    standard_stored_filenames: List[str]


class GenerateLoaderRequest(BaseModel):
    agreement_id: str = Field(..., min_length=1)
    batch_id: str = Field(..., min_length=1)
    model: str = Field(default="gpt-4.1-mini", min_length=1)


class LoaderMapping(BaseModel):
    clause_id: str
    clause_text: str
    matched_standard: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    loader_fields: Dict[str, Any] = Field(default_factory=dict)


class ExcelOutputPlan(BaseModel):
    direction: Literal["TI", "TO"]
    client_tadig: str = Field(..., min_length=1)
    partner_tadig: str = Field(..., min_length=1)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency: str = Field(..., min_length=1)
    sms_mo_rate: float = Field(..., ge=0.0)
    sms_mt_rate: float = Field(..., ge=0.0)
    is_discount: bool = True
    filename: str = Field(..., min_length=1)


class LoaderOutput(BaseModel):
    agreement_name: str
    standards_used: List[str]
    mappings: List[LoaderMapping]
    missing_fields: List[str] = Field(default_factory=list)
    notes: str = ""
    excel_outputs: List[ExcelOutputPlan] = Field(default_factory=list)


class GenerateLoaderResponse(BaseModel):
    output_dir: str
    loader_json_path: str
    loader_txt_path: Optional[str] = None
    loader_excel_paths: List[str] = Field(default_factory=list)
    meta_json_path: str
    summary: Dict[str, Any]
