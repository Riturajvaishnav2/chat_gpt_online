# Agreement vs Standard IOT Loader Generator (FastAPI + OpenAI)

Uploads one Agreement file and a batch of Standard IOT files, extracts text (txt/docx/pdf), calls the OpenAI ChatGPT API to generate a structured "loader" mapping, and writes outputs under `./output/`.

## Requirements

- Python 3.11+
- An OpenAI API key

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file (or export env vars) with:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload
```

Server defaults to `http://127.0.0.1:8000`.

## API Usage (curl)

### Upload Agreement + Standards Together (single call)

```bash
curl -sS -X POST "http://127.0.0.1:8000/upload/all" \
  -F "agreement_file=@./path/to/agreement.pdf" \
  -F "standard_files=@./path/to/standard1.docx" \
  -F "standard_files=@./path/to/standard2.pdf"
```

Response includes `agreement_id`, `agreement_stored_filename`, `batch_id`, and `standard_stored_filenames`. Use these IDs with `/generate-loader`.

### Upload Agreement (separate call)

```bash
curl -sS -X POST "http://127.0.0.1:8000/upload/agreement" \
  -F "agreement_file=@./path/to/agreement.pdf"
```

Response includes `agreement_id` and `stored_filename`.

### Upload Multiple Standard IOT Files (separate call)

```bash
curl -sS -X POST "http://127.0.0.1:8000/upload/standard" \
  -F "standard_files=@./path/to/standard1.docx" \
  -F "standard_files=@./path/to/standard2.pdf" \
  -F "standard_files=@./path/to/standard3.txt"
```

Response includes `batch_id` and `stored_filenames`.

### Generate Loader

```bash
curl -sS -X POST "http://127.0.0.1:8000/generate-loader" \
  -H "Content-Type: application/json" \
  -d '{
    "agreement_id": "YOUR_AGREEMENT_ID",
    "batch_id": "YOUR_BATCH_ID",
    "model": "gpt-4.1-mini"
  }'
```

The endpoint returns a generated Excel file download (or a `.zip` if multiple files are produced). JSON artifacts are written to disk under `output/` for traceability.

## Output Folder Behavior

- Outputs are written under `./output/{agreement_base_name}/`.
- If that folder already exists, a version suffix is appended: `*_v2`, `*_v3`, ...

## Notes

- Supported upload types: `.pdf`, `.docx`, `.txt`, `.xlsx`
- Upload size is limited by an application-level cap (see `app/utils/files.py`).
