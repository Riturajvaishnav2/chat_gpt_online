from __future__ import annotations

import io
import logging
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.models.schemas import (
    GenerateLoaderRequest,
    UploadCombinedResponse,
    UploadAgreementResponse,
    UploadStandardResponse,
)
from app.services.loader_generator import generate_loader_artifacts
from app.utils.files import (
    BASE_DIR,
    AGREEMENTS_DIR,
    OUTPUT_DIR,
    STANDARDS_DIR,
    ensure_dir,
    find_file_by_id_prefix,
    generate_ulid_like_id,
    save_multipart_upload,
)

logger = logging.getLogger("loader_app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_dotenv()
    ensure_dir(AGREEMENTS_DIR)
    ensure_dir(STANDARDS_DIR)
    ensure_dir(OUTPUT_DIR)
    yield


app = FastAPI(title="DCH Tariff Automation API", version="1.0.0", lifespan=lifespan)


async def _store_agreement_upload(agreement_file: UploadFile) -> UploadAgreementResponse:
    agreement_id = generate_ulid_like_id()
    stored_filename = await save_multipart_upload(
        upload_file=agreement_file,
        dest_dir=AGREEMENTS_DIR,
        id_prefix=agreement_id,
    )
    return UploadAgreementResponse(agreement_id=agreement_id, stored_filename=stored_filename)


async def _store_standard_uploads(standard_files: List[UploadFile]) -> UploadStandardResponse:
    if not standard_files:
        raise HTTPException(status_code=400, detail="No files provided for 'standard_files'.")

    batch_id = generate_ulid_like_id()
    batch_dir = STANDARDS_DIR / batch_id
    ensure_dir(batch_dir)

    stored: list[str] = []
    for upload in standard_files:
        stored_filename = await save_multipart_upload(
            upload_file=upload,
            dest_dir=batch_dir,
            id_prefix=None,
        )
        stored.append(stored_filename)

    return UploadStandardResponse(batch_id=batch_id, stored_filenames=stored)


@app.post("/upload/agreement/file", response_model=UploadCombinedResponse)
async def upload_agreement_and_standards(
    agreement_file: UploadFile = File(...),
    standard_files: List[UploadFile] = File(...),
) -> UploadCombinedResponse:
    agreement_resp = await _store_agreement_upload(agreement_file)
    standards_resp = await _store_standard_uploads(standard_files)
    return UploadCombinedResponse(
        agreement_id=agreement_resp.agreement_id,
        agreement_stored_filename=agreement_resp.stored_filename,
        batch_id=standards_resp.batch_id,
        standard_stored_filenames=standards_resp.stored_filenames,
    )


@app.post("/generate-loader")
async def generate_loader(payload: GenerateLoaderRequest):
    agreement_path = find_file_by_id_prefix(AGREEMENTS_DIR, payload.agreement_id)

    standards_batch_dir = STANDARDS_DIR / payload.batch_id
    if not standards_batch_dir.exists() or not standards_batch_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Unknown batch_id: {payload.batch_id}")

    standard_paths = sorted([p for p in standards_batch_dir.iterdir() if p.is_file()])
    if not standard_paths:
        raise HTTPException(status_code=400, detail="No standard files found in the provided batch.")

    result = await generate_loader_artifacts(
        agreement_path=agreement_path,
        standard_paths=standard_paths,
        agreement_id=payload.agreement_id,
        batch_id=payload.batch_id,
        model=payload.model,
    )
    excel_paths = result.loader_excel_paths
    if not excel_paths:
        raise HTTPException(status_code=500, detail="No Excel outputs were generated.")

    abs_paths = []
    for p in excel_paths:
        path_obj = BASE_DIR / p if not Path(p).is_absolute() else Path(p)
        abs_paths.append(path_obj)

    if len(abs_paths) == 1:
        file_path = abs_paths[0]
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Generated Excel file not found on disk.")
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=file_path.name,
        )

    # If multiple files, package into a zip for download.
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in abs_paths:
            if p.exists():
                zf.write(p, arcname=p.name)
    zip_buf.seek(0)
    zip_name = f"{payload.agreement_id}_{payload.batch_id}_loader_outputs.zip"
    headers = {"Content-Disposition": f'attachment; filename="{zip_name}"'}
    return StreamingResponse(zip_buf, media_type="application/zip", headers=headers)
