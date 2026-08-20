from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import re
import json
from pathlib import Path
from docxtpl import DocxTemplate, Listing

app = FastAPI()

LOG_FILE_PATH  = Path("/app/data/result.txt")
FILES_DIR      = Path("/app/data")
TEMPLATE_FILE  = Path("/app/template_03.docx")

# Assessment (Rubric Scoring) Workflow — โฟลเดอร์แยกจาก FILES_DIR เดิม
# โดยเจตนา เพื่อไม่ให้ปนกับ staging area ของ workflow Pre-process /
# Extract-to-JSON-Pure-Python / Batch Summarize ที่ใช้ FILES_DIR (root)
# และ FILES_DIR/"input" อยู่ก่อนแล้ว
ASSESS_PENDING = FILES_DIR / "assess_pending"   # SetA json รอตรวจ
ASSESS_DONE    = FILES_DIR / "assess_done"      # ย้ายมาเมื่อประมวลผลสำเร็จ (marker)
ASSESS_OUTPUT  = FILES_DIR / "assess_output"    # ผลตรวจจริง (score + detail)


# ═════════════════════════════════════════════════════════════
# ใช้เฉพาะกับ 3 workflow: Pre-process / Extract-to-JSON-Pure-Python
# / Batch Summarize เท่านั้น (endpoint/class อื่นที่ไม่ถูกเรียกใช้
# ถูกตัดออกทั้งหมด)
# ═════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# Batch Summarize Workflow — Get Prompt Template
# เสิร์ฟไฟล์ prompt (เก็บที่ /app/data/prompts/) เป็นข้อความล้วน
# ให้ n8n ดึงไปประกอบกับข้อมูลไฟล์ก่อนส่งเข้า Gemini node
# ใช้แทนการให้ n8n อ่านไฟล์เอง (เลี่ยงปัญหา binaryDataMode=filesystem
# ที่ทำให้ n8n decode เนื้อไฟล์ผิดพลาด)
# ─────────────────────────────────────────────

@app.get("/prompt/{prompt_name}")
def get_prompt(prompt_name: str):
    try:
        prompt_path = FILES_DIR / "prompts" / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ prompt: {prompt_path}")
        text = prompt_path.read_text(encoding="utf-8")
        return {"status": "success", "prompt_name": prompt_name, "prompt": text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Utility — List input files
# สแกนไฟล์ .docx, .pdf, .txt ใน n8n-files folder
# ยกเว้น result.txt ซึ่งเป็น log file ของระบบ
# ใช้โดย: Pre-process, Extract-to-JSON-Pure-Python
# ─────────────────────────────────────────────

EXCLUDED_FILES = {"result.txt"}

@app.get("/list-files")
def list_files():
    """สแกนไฟล์ .docx, .pdf, .txt ใน n8n-files folder (ยกเว้น result.txt)"""
    for folder in [Path("/home/node/.n8n-files"), Path("/home/node/.n8n/files")]:
        if folder.exists():
            return [
                {"filePath": str(p), "fileName": p.name}
                for p in folder.iterdir()
                if p.is_file()
                and p.suffix.lower() in {".docx", ".pdf", ".txt"}
                and p.name not in EXCLUDED_FILES
            ]
    return []


# ─────────────────────────────────────────────
# Pre-process Workflow — Check PDF Type
# ตรวจสอบว่า PDF เป็น image-based หรือไม่ ด้วย pikepdf ดู Font
# resource ใน PDF structure จริงๆ ไม่ได้นับ text → ไม่โดน garbage หลอก
# คืน: pdf_type = "image_based" | "text_based"
# ─────────────────────────────────────────────

import pikepdf

class CheckPdfTypePayload(BaseModel):
    file_path: str

@app.post("/check-pdf-type")
def check_pdf_type(payload: CheckPdfTypePayload):
    try:
        p = Path(payload.file_path)
        if not p.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์: {payload.file_path}"}
        if p.suffix.lower() != ".pdf":
            return {"status": "error", "error": "only .pdf supported"}

        with pikepdf.open(str(p)) as pdf:
            for page in pdf.pages:
                resources = page.get("/Resources", {})
                if "/Font" in resources:
                    # พบ Font resource อย่างน้อย 1 หน้า = มี text layer
                    return {
                        "status":    "success",
                        "file_name": p.name,
                        "file_path": str(p),
                        "pdf_type":  "text_based"
                    }

        # วนครบทุกหน้าแล้วไม่พบ Font เลย = image-based
        return {
            "status":    "success",
            "file_name": p.name,
            "file_path": str(p),
            "pdf_type":  "image_based"
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Pre-process Workflow — Compress PDF
# PDF → pdf2image → resize → บันทึกกลับเป็น PDF
# ─────────────────────────────────────────────

from pdf2image import convert_from_path
from PIL import Image as PilImage

class CompressPdfPayload(BaseModel):
    file_path:    str
    max_width:    int = 2500
    jpeg_quality: int = 75

@app.post("/compress-pdf")
def compress_pdf(payload: CompressPdfPayload):
    try:
        p = Path(payload.file_path)
        if not p.exists():
            return {"status": "error", "error": f"not found: {payload.file_path}"}
        if p.suffix.lower() != ".pdf":
            return {"status": "error", "error": "only .pdf supported"}

        original_size = p.stat().st_size

        pages = convert_from_path(str(p), dpi=150)

        resized_pages = []
        for page in pages:
            w, h = page.size
            if w > payload.max_width:
                ratio    = payload.max_width / w
                new_size = (payload.max_width, int(h * ratio))
                page     = page.resize(new_size, PilImage.LANCZOS)
            resized_pages.append(page.convert("RGB"))

        out_name = p.stem + ".pdf"
        out_path = p.parent / out_name

        if len(resized_pages) == 1:
            resized_pages[0].save(str(out_path), "PDF",
                save_all=False, quality=payload.jpeg_quality, optimize=True)
        else:
            resized_pages[0].save(str(out_path), "PDF",
                save_all=True, append_images=resized_pages[1:],
                quality=payload.jpeg_quality, optimize=True)

        compressed_size = out_path.stat().st_size
        reduction_pct   = round((1 - compressed_size / original_size) * 100, 1)

        return {
            "status":             "success",
            "original_path":      str(p),
            "compressed_path":    str(out_path),
            "file_name":          out_name,
            "original_size_kb":   round(original_size   / 1024, 1),
            "compressed_size_kb": round(compressed_size / 1024, 1),
            "reduction_pct":      reduction_pct,
            "pages":              len(resized_pages)
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Pre-process Workflow — Vision OCR via Gemini
# รับ file_path + api_key → เรียก Gemini Vision เอง คืน extracted text
# ─────────────────────────────────────────────

import base64
import httpx

class VisionOcrPayload(BaseModel):
    file_path: str
    api_key:   str

@app.post("/vision-ocr")
def vision_ocr(payload: VisionOcrPayload):
    try:
        p = Path(payload.file_path)
        if not p.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์: {payload.file_path}"}

        ext = p.suffix.lower()
        mime_map = {
            ".pdf":  "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
        }
        mime_type = mime_map.get(ext, "application/pdf")

        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "คุณคือระบบ OCR ภาษาไทยที่มีความแม่นยำสูง\n\n"
            "งาน: อ่านและถอดความเนื้อหาทั้งหมดจากเอกสารนี้\n\n"
            "กฎ:\n"
            "1. ถอดข้อความให้ครบถ้วนทุกตัวอักษร ตามลำดับที่ปรากฏในเอกสาร ไม่เพิ่ม ไม่แต่งเดิม แก้ไขข้อความใดๆ\n"
            "2. รักษาการขึ้นบรรทัดใหม่ตามต้นฉบับอย่างเคร่งครัด โดยเฉพาะบรรทัดที่ขึ้นต้นด้วย 'เรื่อง' และ 'เรียน' ต้องอยู่คนละบรรทัดเสมอ\n"
            "3. ห้ามใช้ '...' หรือ '_' แทนช่องว่างหรือเส้นประในเอกสาร ให้ใช้ช่องว่างธรรมดาแทน\n"
            "4. หากอ่านข้อความใดไม่ชัด ให้ใส่ [อ่านไม่ชัด] แทน\n"
            "6. เลขไทย ให้เปลี่ยนเป็นเลขอารบิกตามตารางนี้อย่างเคร่งครัด:\n"
            "   ๐=0, ๑=1, ๒=2, ๓=3, ๔=4, ๕=5, ๖=6, ๗=7, ๘=8, ๙=9\n"
            "   *** คู่ที่มักอ่านสับสน — ต้องระวังเป็นพิเศษ ***\n"
            "   - ๙ (เก้า=9): หัวม้วนอยู่ด้านบนซ้าย เส้นวนลงด้านล่างขวาแล้วม้วนกลับขึ้น คล้ายตัว ว ที่มีหางยาว\n"
            "   - ๔ (สี่=4): หัวกลมอยู่ด้านบนขวา เส้นลากลงด้านล่างตรงๆ คล้ายตัว ด\n"
            "   - ๖ (หก=6): คล้ายเลข 6 อารบิก หัวกลมอยู่ด้านล่าง\n"
            "   - ๕ (ห้า=5): คล้ายตัว น แต่มีหางยาวลงด้านล่าง\n"
            "   หากเห็นเลขไทยที่คล้าย ๔ ให้ดูรูปทรงให้ชัดเจน: ถ้าเส้นม้วนวนกลับขึ้น = ๙(9) ถ้าเส้นลากลงตรง = ๔(4)\n"
            "7. ตอบกลับเป็นข้อความล้วน ไม่ต้องมี markdown หรือคำอธิบายเพิ่มเติม\n"
        )
        request_body = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192
            }
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/gemini-2.5-flash:generateContent"
            f"?key={payload.api_key}"
        )

        resp = httpx.post(url, json=request_body, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        extracted_text = result["candidates"][0]["content"]["parts"][0]["text"]

        return {
            "status":     "success",
            "file_name":  p.name,
            "text":       extracted_text,
            "file_path":  str(p),
            "char_count": len(extracted_text)
        }

    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"Gemini API error: {e.response.text}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# [NEW] Pre-process (Google Cloud Vision variant) — Vision OCR via
# Google Cloud Vision API (files:annotate, synchronous, DOCUMENT_TEXT_DETECTION)
#
# *** endpoint ใหม่ทั้งหมด ไม่แตะ /vision-ocr (Gemini) เดิม — workflow
#     Pre-process เดิมยังใช้ /vision-ocr ได้ตามปกติทุกประการ ***
#
# ข้อจำกัดของ Cloud Vision synchronous files:annotate (ตาม doc ทางการ
# Google, ก.ค. 2026): ประมวลผลได้สูงสุด 5 หน้า/ไฟล์ ถ้าไฟล์เกิน 5 หน้า
# ต้องใช้ asyncBatchAnnotate (ต้องผ่าน GCS) แทน — endpoint นี้จึงกันไว้
# ไม่ให้ทำงานกับไฟล์ที่เกิน 5 หน้า (แจ้ง error กลับไปตรงๆ แทนที่จะ
# ตัดหน้าทิ้งแบบเงียบๆ)
# ─────────────────────────────────────────────

MAX_SYNC_PAGES = 5

class VisionOcrGcvPayload(BaseModel):
    file_path: str
    #api_key:   str = "AIzaSyA1SM16TxWXA9hMl0bSa3FQ_GHfK-UzgF8"  # default สำหรับ Cloud Vision API (key แยกจาก Gemini)
    api_key:   str = "AIzaSyC1UzDvedGzqlzM7mKCkTcciLP-S4UFFXs"
@app.post("/vision-ocr-gcv")
def vision_ocr_gcv(payload: VisionOcrGcvPayload):
    try:
        p = Path(payload.file_path)
        if not p.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์: {payload.file_path}"}
        if p.suffix.lower() != ".pdf":
            return {"status": "error", "error": "only .pdf supported (Cloud Vision files:annotate sync)"}

        # เช็คจำนวนหน้าก่อน — sync files:annotate จำกัดไว้ที่ 5 หน้า/ไฟล์
        with pikepdf.open(str(p)) as pdf:
            page_count = len(pdf.pages)

        if page_count > MAX_SYNC_PAGES:
            return {
                "status": "error",
                "error": (f'ไฟล์ "{p.name}" มี {page_count} หน้า เกินขีดจำกัด '
                          f'{MAX_SYNC_PAGES} หน้าของ Cloud Vision synchronous API '
                          f'(ไฟล์ที่เกินต้องใช้ asyncBatchAnnotate ผ่าน Cloud Storage แทน)')
            }

        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        request_body = {
            "requests": [
                {
                    "inputConfig": {
                        "content":  b64,
                        "mimeType": "application/pdf"
                    },
                    "features": [
                        {"type": "DOCUMENT_TEXT_DETECTION"}
                    ],
                    "pages": list(range(1, page_count + 1))
                }
            ]
        }

        url = f"https://vision.googleapis.com/v1/files:annotate?key={payload.api_key}"

        resp = httpx.post(url, json=request_body, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        file_response = result.get("responses", [{}])[0]
        if "error" in file_response:
            return {
                "status": "error",
                "error": file_response["error"].get("message", "Cloud Vision API error ไม่ทราบสาเหตุ")
            }

        page_responses  = file_response.get("responses", [])
        page_texts      = [
            pr.get("fullTextAnnotation", {}).get("text", "")
            for pr in page_responses
        ]
        extracted_text  = "\n".join(t for t in page_texts if t)

        return {
            "status":          "success",
            "file_name":       p.name,
            "text":            extracted_text,
            "file_path":       str(p),
            "char_count":      len(extracted_text),
            "pages_processed": len(page_responses)
        }

    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"Cloud Vision API error: {e.response.text}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Pre-process Workflow — Save and Move (atomic)
# รวม save-as-txt + move-to-done เป็น call เดียว
# บันทึก .txt แล้วย้าย PDF ต้นฉบับใน step เดียว — ไม่มี partial state
# ─────────────────────────────────────────────

class SaveAndMovePayload(BaseModel):
    file_name: str   # ชื่อไฟล์ต้นฉบับ เช่น "doc.pdf"
    text: str        # ข้อความที่ได้จาก Vision OCR

@app.post("/save-and-move")
def save_and_move(payload: SaveAndMovePayload):
    try:
        # 1) บันทึก .txt
        txt_name = re.sub(r"\.(pdf|docx)$", ".txt", payload.file_name, flags=re.IGNORECASE)
        txt_path = FILES_DIR / txt_name
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        with txt_path.open("w", encoding="utf-8") as f:
            f.write(payload.text)

        # 2) ย้าย PDF ต้นฉบับ → Complete/
        src = FILES_DIR / payload.file_name
        moved_to = None
        if src.exists():
            done_dir = FILES_DIR / "Complete"
            done_dir.mkdir(parents=True, exist_ok=True)
            dst = done_dir / payload.file_name
            os.rename(str(src), str(dst))
            moved_to = str(dst)

        return {
            "status":     "success",
            "txt_file":   txt_name,
            "txt_path":   str(txt_path),
            "char_count": len(payload.text),
            "moved_to":   moved_to
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Extract-to-JSON-Pure-Python Workflow — Extract Memo (NO AI)
#   0. แปลงเลขไทย→อารบิก ด้วย str.translate (แม่น 100% — จำเป็นเพราะ
#      _MAIN_SECT_RE ใช้ [1-4] ซึ่งไม่ match เลขไทย)
#   1. ดึง serial_no, subject_text จาก header
#   2. ตัด body: หลัง "เรียน ..." ถึงก่อน "จึงเรียนมา"
#   3. ต่อบรรทัดที่ขาดกลางประโยค + ตัดบรรทัดเลขหน้า
#   4. แบ่ง 4 ส่วน + sub-items ด้วย regex/helper
# ─────────────────────────────────────────────

from typing import Any, Dict

_THAI_ARABIC = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
# บรรทัดเลขหน้าล้วน เช่น "- ๒ -", "-3", "4" (ตัวเลข/ขีดล้วน ไม่มีเนื้อหา)
_PAGE_NUM_RE = re.compile(r'^\s*-?\s*\d{1,3}\s*-?\s*$')
# บรรทัดที่ขึ้นต้นด้วยเลขข้อ (main หรือ sub ทุกระดับ)
_ITEM_START_RE = re.compile(r'^\d[\d.]*\s')
# sub-item pattern: 2.1 / 2.1.1 / 2.3.2.1 ฯลฯ (ต้องมี digit หลัง dot อย่างน้อย 1 ตัว)
_SUB_ITEM_RE = re.compile(r'(?m)^(\d+\.\d[\d\.]*)\s+')
# main section pattern: 1. / 2. / 3. / 4. เท่านั้น (ไม่มี digit ต่อท้าย dot)
_MAIN_SECT_RE = re.compile(r'(?m)^([1-4])\.\s+')
_SECTION_MAP  = {'1': 'problem', '2': 'fact', '3': 'consideration', '4': 'proposal'}


def _extract_section(sec_text: str) -> dict:
    """สกัด {text, items} จาก section text (รวม prefix เลขข้อหลัก)"""
    if not sec_text:
        return {"text": "", "items": []}
    clean = re.sub(r'^\d+\.\s*', '', sec_text).strip()
    subs  = [(m.start(), m.group(1), m.end()) for m in _SUB_ITEM_RE.finditer(clean)]
    if not subs:
        return {"text": clean, "items": []}
    main_text = clean[:subs[0][0]].strip()
    items = []
    for i, (start, no, content_start) in enumerate(subs):
        end       = subs[i + 1][0] if i + 1 < len(subs) else len(clean)
        item_text = clean[content_start:end].strip()
        items.append({"no": no, "text": item_text})
    return {"text": main_text, "items": items}


def _join_wrapped_lines(body: str) -> str:
    """ต่อบรรทัดที่ขาดกลางประโยค:
    บรรทัดที่ 'ไม่ได้' ขึ้นต้นด้วยเลขข้อ ให้ผนวกเข้ากับบรรทัดก่อนหน้า
    เพื่อรักษา boundary ของข้อหลัก/ข้อย่อยไว้เสมอ พร้อมตัดบรรทัดเลขหน้าทิ้ง"""
    out: list = []
    for raw_line in body.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        if _PAGE_NUM_RE.match(line):
            continue  # เลขหน้า → ทิ้ง
        if _ITEM_START_RE.match(line) or not out:
            out.append(line)          # ขึ้นข้อใหม่ หรือบรรทัดแรกสุด
        else:
            out[-1] = out[-1] + ' ' + line  # ต่อบรรทัดที่ขาด
    return '\n'.join(out)


class ExtractMemoPurePayload(BaseModel):
    file_name: str
    raw_text: str


@app.post("/extract-memo-pure")
def extract_memo_pure(payload: ExtractMemoPurePayload):
    try:
        # 0) แปลงเลขไทย→อารบิก ทั้งเอกสาร + ลบอักขระเสีย OCR
        text = payload.raw_text.translate(_THAI_ARABIC).replace('�', '')

        # 1) serial_no: ระหว่าง "ที่" กับ newline/เรื่อง/วันที่ ในหัวเอกสาร
        #    ใช้ (?<!วัน) กัน "ที่" ที่ซ่อนอยู่ใน "วันที่"
        serial_no = ""
        m = re.search(r'(?<!วัน)ที่\s+(.+?)(?:\n|เรื่อง|วันที่)', text[:500])
        if m:
            serial_no = m.group(1).strip()

        # 2) subject_text: ระหว่าง "เรื่อง" กับ "เรียน"
        subject_text = ""
        m = re.search(r'เรื่อง\s+(.+?)(?=\nเรียน|เรียน\s)', text[:600], re.DOTALL)
        if m:
            subject_text = ' '.join(m.group(1).split())

        # 3) body: หลัง "เรียน ...", ก่อน "จึงเรียนมา"
        body_start, body_end = 0, len(text)
        m = re.search(r'เรียน[^\n]*\n', text)
        if m:
            body_start = m.end()
        m = re.search(r'จึงเรียนมา', text)
        if m:
            body_end = m.start()
        body_raw = text[body_start:body_end].strip()

        # 4) ต่อบรรทัดที่ขาด + ตัดเลขหน้า
        body = _join_wrapped_lines(body_raw)

        # 5) แบ่ง section หลัก (1-4)
        main_matches = [(mm.start(), mm.group(1)) for mm in _MAIN_SECT_RE.finditer(body)]
        section_texts: dict = {}
        for i, (start, num) in enumerate(main_matches):
            end = main_matches[i + 1][0] if i + 1 < len(main_matches) else len(body)
            section_texts[num] = body[start:end].strip()

        # 6) สกัด items แต่ละ section
        body_text = {
            _SECTION_MAP[num]: _extract_section(sec)
            for num, sec in section_texts.items()
            if num in _SECTION_MAP
        }
        for key in ("problem", "fact", "consideration", "proposal"):
            body_text.setdefault(key, {"text": "", "items": []})

        # Guard: ถ้าสกัด body ไม่ได้เลย (ไม่พบเลขข้อ 1-4) → raise 422 ให้ n8n หยุดไฟล์นี้
        has_content = any(sec["text"] or sec["items"] for sec in body_text.values())
        if not has_content:
            raise HTTPException(
                status_code=422,
                detail=(f'สกัด body ไม่สำเร็จ (ไม่พบเลขข้อ 1-4) — '
                        f'ไฟล์ "{payload.file_name}" ต้องตรวจสอบ/แก้ก่อน execute ใหม่')
            )

        return {
            "status":       "success",
            "file_name":    payload.file_name,
            "serial_no":    serial_no,
            "subject_text": subject_text,
            "body_text":    body_text
        }

    except HTTPException:
        raise  # ส่ง 422 ออกไปตรงๆ ให้ n8n หยุด — อย่าให้ except ด้านล่างกลืนเป็น 200
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Extract-to-JSON-Pure-Python Workflow — Save Extracted
# รับ 3 field (serial_no, subject_text, body_text 4 ส่วน)
# ประกอบเป็น JSON เต็ม 8 field → เขียน <ชื่อ>.json ลง root (FILES_DIR)
# bullet_text / summary_text เว้นว่างไว้รอ workflow Batch Summarize
# ─────────────────────────────────────────────

from datetime import datetime

class SaveExtractedPayload(BaseModel):
    file_name: str
    serial_no: str = ""
    subject_text: str = ""
    body_text: Dict[str, Any] = {}

BODY_SECTIONS = ("problem", "fact", "consideration", "proposal")

def _normalize_section(section: Any) -> Dict[str, Any]:
    """บังคับโครงสร้าง {text, items[{no, text}]} เสมอ"""
    if not isinstance(section, dict):
        return {"text": "", "items": []}
    items_in = section.get("items") or []
    items = []
    if isinstance(items_in, list):
        for it in items_in:
            if isinstance(it, dict):
                items.append({
                    "no":   str(it.get("no")   or ""),
                    "text": str(it.get("text") or "")
                })
    return {"text": str(section.get("text") or ""), "items": items}

@app.post("/save-extracted")
def save_extracted(payload: SaveExtractedPayload):
    try:
        body_text = {
            key: _normalize_section(payload.body_text.get(key))
            for key in BODY_SECTIONS
        }

        output_data = {
            "fileName":     payload.file_name,
            "serial_no":    payload.serial_no,
            "subject_text": payload.subject_text,
            "body_text":    body_text,
            "bullet_text":  "",
            "summary_text": "",
            "status":       "extracted",
            "extracted_at": datetime.now().isoformat(timespec="seconds")
        }

        json_name = re.sub(r"\.(pdf|docx|txt)$", ".json", payload.file_name, flags=re.IGNORECASE)
        if not json_name.lower().endswith(".json"):
            json_name += ".json"

        FILES_DIR.mkdir(parents=True, exist_ok=True)
        json_path = FILES_DIR / json_name

        with json_path.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        return {
            "status":    "success",
            "json_file": json_name
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Extract-to-JSON-Pure-Python Workflow — Move To Done
# ย้าย PDF ต้นฉบับไปไว้ใน Complete/ หลัง save-extracted
# ─────────────────────────────────────────────

class MoveToDonePayload(BaseModel):
    file_name: str

@app.post("/move-to-done")
def move_to_done(payload: MoveToDonePayload):
    try:
        src = FILES_DIR / payload.file_name
        if not src.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์: {payload.file_name}"}

        done_dir = FILES_DIR / "Complete"
        done_dir.mkdir(parents=True, exist_ok=True)

        dst = done_dir / payload.file_name
        os.rename(str(src), str(dst))

        return {
            "status":    "success",
            "file_name": payload.file_name,
            "moved_to":  str(dst)
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Batch Summarize Workflow — List Extracted
# list *.json ใน root ที่ status == "extracted"
# ส่งเนื้อหาไปด้วย เพื่อให้ n8n ไม่ต้องอ่าน disk เอง
# ─────────────────────────────────────────────

@app.get("/list-extracted")
def list_extracted():
    results = []
    if not FILES_DIR.exists():
        return results

    for p in sorted(FILES_DIR.glob("*.json")):
        if not p.is_file():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue  # ไฟล์ json เสีย ข้ามไป
        if isinstance(data, dict) and data.get("status") == "extracted":
            results.append({
                "filePath":     str(p),
                "fileName":     data.get("fileName") or p.name,
                "serial_no":    data.get("serial_no", ""),
                "subject_text": data.get("subject_text", ""),
                "body_text":    data.get("body_text", {})
            })

    return results


# ─────────────────────────────────────────────
# Batch Summarize Workflow — Finalize (atomic)
# รวม update-summary + generate-docx + append-log เป็น call เดียว
# ทำทั้ง 3 ขั้นตอนใน transaction เดียว — ไม่มีสภาวะข้อมูลค้างกลางทาง
# ─────────────────────────────────────────────

class FinalizePayload(BaseModel):
    file_name: str
    bullet_text: str = ""
    summary_text: str = ""

@app.post("/finalize")
def finalize(payload: FinalizePayload):
    try:
        # 1) หาและโหลด JSON ที่ /save-extracted เขียนไว้ที่ root
        json_name = payload.file_name
        if not json_name.lower().endswith(".json"):
            json_name = re.sub(r"\.(pdf|docx|txt)$", ".json", json_name, flags=re.IGNORECASE)
        if not json_name.lower().endswith(".json"):
            json_name += ".json"

        json_path = FILES_DIR / json_name
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ {json_name}")

        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # 2) อัพเดต bullet/summary + timestamp
        data["bullet_text"]   = payload.bullet_text
        data["summary_text"]  = payload.summary_text
        data["summarized_at"] = datetime.now().isoformat(timespec="seconds")

        # บันทึกลง JSON/ แล้วลบไฟล์ root
        json_dir  = FILES_DIR / "input"
        json_dir.mkdir(parents=True, exist_ok=True)
        dest_path = json_dir / json_name
        with dest_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        json_path.unlink()

        # 3) Render docx template → Finish/<ชื่อ>_finished.docx
        if not TEMPLATE_FILE.exists():
            raise HTTPException(status_code=500, detail=f"ไม่พบ template: {TEMPLATE_FILE}")

        body_raw = data.get("body_text", "")
        if isinstance(body_raw, dict):
            parts = []
            for section_key in ("problem", "fact", "consideration", "proposal"):
                sec = body_raw.get(section_key, {})
                if not isinstance(sec, dict):
                    continue
                text = sec.get("text", "")
                if text:
                    parts.append(text)
                for it in (sec.get("items") or []):
                    if isinstance(it, dict):
                        no = it.get("no", "")
                        t  = it.get("text", "")
                        parts.append(f"{no} {t}" if no else t)
            body_text = "\n".join(parts)
        else:
            body_text = str(body_raw)

        doc = DocxTemplate(TEMPLATE_FILE)
        context = {
            "serial_no":    data.get("serial_no", ""),
            "subject_text": data.get("subject_text", ""),
            "summary_text": data.get("summary_text", ""),
            "body_text":    Listing(body_text),
            "bullet_text":  Listing(data.get("bullet_text", "")),
        }
        doc.render(context)

        finish_dir  = FILES_DIR / "output"
        finish_dir.mkdir(parents=True, exist_ok=True)
        output_name = json_name.replace(".json", "_finished.docx")
        doc.save(str(finish_dir / output_name))

        # 4) Append log
        subject_text = data.get("subject_text", "")
        LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{payload.file_name} | {subject_text}\n")

        return {
            "status":       "success",
            "json_file":    json_name,
            "output_file":  output_name,
            "subject_text": subject_text
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Assessment Workflow — List Pending
# สแกน assess_pending/*.json (โฟลเดอร์ใหม่ แยกจาก /list-extracted เดิม
# ที่ผูกกับ workflow Batch Summarize คนละ schema) คืนแค่ fileName +
# student_id + content (essay จริงที่จะเอาไปแทน %%ESSAY_JSON%% ใน
# prompt) — ตัด word_file_url/score(null) ทิ้ง ไม่ส่งของที่ไม่ใช้เข้า prompt
# ─────────────────────────────────────────────

@app.get("/list-assess-pending")
def list_assess_pending():
    results = []
    if not ASSESS_PENDING.exists():
        return results

    for p in sorted(ASSESS_PENDING.glob("*.json")):
        if not p.is_file():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue  # ไฟล์ json เสีย ข้ามไป
        results.append({
            "fileName":   p.name,
            "student_id": (data.get("student_id") if isinstance(data, dict) else None) or p.stem,
            "content":    data.get("content", {}) if isinstance(data, dict) else {}
        })

    return results


# ─────────────────────────────────────────────
# Assessment Workflow — Expand Compact JSON (prompt_i.txt) → Score + Detail
#
# รับคำตอบดิบจาก AI (raw text อาจมี code fence/ข้อความปนมา โดยเฉพาะ
# local model) → แกะ JSON → validate ตามกฎ sequential-stop ของ
# prompt_i.txt → คำนวณ level ต่อเกณฑ์ (Decision Tree เกณฑ์ 1-4,
# เกณฑ์ 5 ใช้ S_level ที่ AI สรุปมาโดยตรง) → เขียนผลลง assess_output/
# แล้วย้ายไฟล์ input เดิมจาก assess_pending → assess_done
#
# ถ้าข้อมูลผิดปกติ (JSON แกะไม่ได้ / ค่า p ไม่ใช่ 0-1 / ผิดลำดับ
# sequential-stop / ไม่มี S_level) → ไม่ย้ายไฟล์ ไม่เขียน output
# คืน status: "error" ให้ไฟล์ค้างอยู่ใน assess_pending เพื่อตรวจ manual
# ─────────────────────────────────────────────

GROUP_ORDER = {
    "P": ["P1", "P2", "P3"],
    "F": ["F1", "F2", "F3", "F4"],
    "C": ["C1", "C2", "C3", "C4"],
    "R": ["R1", "R2", "R3", "R4"],
}
GROUP_LABEL = {"P": "problem", "F": "fact", "C": "consideration", "R": "proposal"}
# นับจำนวนรายการ pass ต่อเนื่องจากต้น (ตามกฎ sequential-stop) แล้วแมปเป็น level
# P: แต่ละ item ยกระดับตรงตัว | F/C/R: 2 item แรกเป็นประตูสู่ level 2, item 3-4 เป็นเงื่อนไข OR สู่ level 3
LEVEL_MAP = {
    "P": {0: 0, 1: 1, 2: 2, 3: 3},
    "F": {0: 0, 1: 1, 2: 2, 3: 2, 4: 3},
    "C": {0: 0, 1: 1, 2: 2, 3: 2, 4: 3},
    "R": {0: 0, 1: 1, 2: 2, 3: 2, 4: 3},
}
WEIGHTS = {"problem": 1, "fact": 2, "consideration": 4, "proposal": 1, "coherence": 2}


def _strip_line_comments(text: str) -> str:
    """ตัด comment สไตล์ JavaScript ("// ...") ที่อยู่นอกเครื่องหมายคำพูดออก
    (พบกับ ministral-3:8b ที่แทรก // comment ปนกลาง object ทำให้ผิด JSON
    มาตรฐาน — JSON ไม่รองรับ comment เลยแม้แต่แบบเดียว) เดินตัวอักษรทีละตัว
    คอยจำสถานะว่าอยู่ "ในเครื่องหมายคำพูด" หรือไม่ เพื่อไม่ไปตัด "//" ที่อาจ
    ปรากฏอยู่ในข้อความจริงโดยบังเอิญ (เช่น URL ในฟิลด์ evidence) — เคสปกติ
    ที่ไม่มี // comment เลยจะได้ข้อความกลับมาเหมือนเดิมทุกตัวอักษร"""
    out = []
    in_string = False
    escape = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            nl = text.find('\n', i)
            i = n if nl == -1 else nl
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _strip_stray_trailing_quote(text: str) -> str:
    """ตัด " เกินที่ ministral-3:8b บางครั้งแทรกต่อท้าย string value ที่ปิดไป
    สมบูรณ์แล้ว (พบกับ field "e" ที่มีข้อความ 2 ท่อนเชื่อมด้วย "และ" คล้าย
    พยายามต่อ string แบบ JS แล้วเบิ้ล quote ผิดจังหวะ เช่น
    `"e": "\\"...\\" และ \\"...\\""` + มี " เกินอีกตัวก่อนถึง , หรือ }) —
    เดินอักขระทีละตัวเหมือน _strip_line_comments คอยจำว่าเพิ่งปิด string
    สมบูรณ์ไปหมาดๆ หรือไม่ ถ้าใช่ แล้วเจอ " ตามมาอีกตัว (ข้าม whitespace ได้)
    ตามด้วย , หรือ } หรือ ] ทันที (ไม่มีเนื้อหาอื่นคั่น) — pattern นี้ไม่มีทาง
    เป็น JSON ที่ถูกต้องได้เลยไม่ว่ากรณีใด (สอง string token ติดกันไม่มี
    ตัวคั่นไม่มีทางถูกต้อง) จึงตัด " ตัวเกินทิ้งได้อย่างปลอดภัย ส่วนกรณีปกติ
    เช่น empty string "" ตามด้วย , จะไม่ถูกแตะต้อง เพราะไม่มี " เกินให้ตัด"""
    out = []
    in_string = False
    escape = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                i += 1
                continue
            if ch == '\\':
                out.append(ch)
                escape = True
                i += 1
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                i += 1
                # เพิ่งปิด string สมบูรณ์ — เช็ค " เกินตามมาไหม
                j = i
                while j < n and text[j] in ' \t\r\n':
                    j += 1
                if j < n and text[j] == '"':
                    k = j + 1
                    while k < n and text[k] in ' \t\r\n':
                        k += 1
                    if k < n and text[k] in ',}]':
                        out.append(text[i:j])  # เก็บ whitespace คั่นกลางไว้เหมือนเดิม
                        i = j + 1               # ข้าม " เกินทิ้ง
                continue
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _fix_missing_value_open_quote(text: str) -> str:
    """แก้กรณี qwen3.5:4b บางครั้งลืมใส่ " ตัวเปิด string ของ value จริงๆ แล้ว
    ใช้ \\" (backslash+quote) แทนตั้งแต่ต้นเลย เช่น
    `"e": \\"\\"เนื่องจาก...บางแสน...\\""` — ตรง value ที่ควรขึ้นต้นด้วย " ธรรมดา
    กลับกลายเป็น \\" แทน (backslash ที่อยู่นอกเครื่องหมายคำพูดไม่มีความหมายใน JSON
    เลย จึงตัดทิ้งได้ปลอดภัย ปล่อยให้ " ตัวถัดมาทำหน้าที่เปิด string จริงแทน) —
    เดินอักขระทีละตัว คอยจำ "อักขระที่มีความหมายตัวล่าสุด" นอกเครื่องหมายคำพูด
    (last_sig) ถ้าเจอ \\" (นอก string) ในจังหวะที่ last_sig คือ : หรือ [ หรือ ,
    (แปลว่าตำแหน่งนี้คือจุดที่ "ควรเริ่ม value ใหม่") ถึงจะตัด backslash ทิ้ง —
    เจาะจงเฉพาะบริบทนี้เพื่อไม่ให้ชนกับ _strip_stray_trailing_backslash_quote ที่
    จับ \\" ที่โผล่ "ต่อท้าย" string ซึ่งปิดไปแล้ว (คนละบริบท คนละวิธีแก้ กรณีนั้น
    ต้องตัดทิ้งทั้ง \\" ไม่ใช่เก็บ " ไว้เปิด string ใหม่) — เคสปกติที่ไม่มีปัญหานี้
    เลยจะได้ข้อความเดิมทุกตัวอักษร"""
    out = []
    in_string = False
    escape = False
    last_sig = ''
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
                last_sig = '"'
            i += 1
            continue
        if ch == '\\' and i + 1 < n and text[i + 1] == '"' and last_sig in (':', '[', ','):
            i += 1  # ตัด backslash ทิ้ง ปล่อยให้ " ตัวถัดไปเปิด string จริง
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            last_sig = '"'
            i += 1
            continue
        if ch not in ' \t\r\n':
            last_sig = ch
        out.append(ch)
        i += 1
    return ''.join(out)


def _strip_stray_trailing_backslash_quote(text: str) -> str:
    """ตัด \\" เกิน (backslash ตามด้วย quote) ที่ qwen3.5:4b บางครั้งแทรกต่อท้าย
    string value ที่ปิดไปสมบูรณ์แล้ว เช่น
    `"e": "\\"๒.๑ สถานภาพกำลังพล...\\"\\"` — string จริงปิดไปแล้วด้วย " ตัวที่ถูกต้อง
    แต่ตามมาด้วย \\" เกินอีก 2 ตัวอักขระ (backslash + quote) ก่อนถึง , หรือ }
    ต่างจาก _strip_stray_trailing_quote (ที่โดนกับ ministral-3:8b) ตรงที่ตัวเกิน
    เป็น \\" ไม่ใช่ " เดี่ยวๆ — เดินอักขระทีละตัวเหมือนกัน คอยจำว่าเพิ่งปิด string
    สมบูรณ์ไปหมาดๆ หรือไม่ ถ้าใช่ แล้วเจอ \\" ตามมาอีก (ข้าม whitespace ได้)
    ตามด้วย , หรือ } หรือ ] ทันที (ไม่มีเนื้อหาอื่นคั่น) — pattern นี้ไม่มีทางเป็น
    JSON ที่ถูกต้องได้เลย (backslash ที่อยู่นอกเครื่องหมายคำพูดไม่มีความหมายใน JSON)
    จึงตัด \\" ตัวเกินทิ้งได้อย่างปลอดภัย ส่วนกรณีปกติ เช่น string ที่ลงท้ายด้วย
    \\\\ ข้างในตัวมันเอง (escape จริงของ string) จะไม่ถูกแตะต้อง เพราะ backslash
    นั้นยังอยู่ใน state "in_string" ไม่ใช่ตัวเกินนอก string"""
    out = []
    in_string = False
    escape = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                i += 1
                continue
            if ch == '\\':
                out.append(ch)
                escape = True
                i += 1
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                i += 1
                # เพิ่งปิด string สมบูรณ์ — เช็ค \" เกินตามมาไหม
                j = i
                while j < n and text[j] in ' \t\r\n':
                    j += 1
                if j + 1 < n and text[j] == '\\' and text[j + 1] == '"':
                    k = j + 2
                    while k < n and text[k] in ' \t\r\n':
                        k += 1
                    if k < n and text[k] in ',}]':
                        out.append(text[i:j])  # เก็บ whitespace คั่นกลางไว้เหมือนเดิม
                        i = j + 2               # ข้าม \" เกินทิ้ง
                continue
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _strip_trailing_comma(text: str) -> str:
    """ตัด , เกินที่ qwen3.5:4b บางครั้งแทรกก่อนวงเล็บปิด } หรือ ] เช่น
    `"e": "..." },` — JSON มาตรฐานไม่อนุญาต trailing comma เลย (ต่างจาก
    JavaScript object literal ที่ยอมรับได้) ทำให้ parser คาดหวัง property name
    ตัวถัดไปแต่ดันเจอ } ปิด object แทน — เดินอักขระทีละตัวนอกเครื่องหมายคำพูด
    พอเจอ , ให้ดูต่อ (ข้าม whitespace ได้) ว่าตัวถัดไปคือ } หรือ ] ทันทีไหม ถ้าใช่
    แปลว่าเป็น comma เกินแน่นอน (ไม่มีทางเป็น JSON ที่ถูกต้องได้เลย) จึงตัดทิ้งได้
    อย่างปลอดภัย — เคสปกติที่ไม่มี , เกินเลยจะได้ข้อความเดิมทุกตัวอักษร"""
    out = []
    in_string = False
    escape = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ',':
            j = i + 1
            while j < n and text[j] in ' \t\r\n':
                j += 1
            if j < n and text[j] in '}]':
                # , ตัวนี้เป็นตัวเกิน — ข้ามไม่ต้องใส่ใน output
                i += 1
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _fix_duplicate_closing_braces(text: str) -> str:
    """ตัด } เกินที่บาง local model (พบกับ deepseek-r1:8b) แทรกซ้ำก่อนวงเล็บปิด
    ที่ถูกต้องของแต่ละ item ใน "results" เช่น
    `"e": "...ข้อความ..." }` แล้วตามด้วย `},` อีกชั้น — ทำให้เดินนับวงเล็บผิด
    จังหวะ ปิด "results" (หรือแม้แต่ราก JSON) ก่อนเวลาอันควร ผลคือ item ที่มา
    ทีหลัง (รวมถึง "S_level") หายไปจากผล parse ทั้งที่โมเดลตอบมาครบจริง —
    เดินอักขระนอกเครื่องหมายคำพูด พอเจอ } ตามด้วย } อีกตัว (คั่นด้วย
    whitespace ได้) ให้ดูต่อว่าหลังจากนั้นคือ ,"S_level" หรือไม่ (กรณีเดียวที่
    } ติดกัน 2 ตัวถูกต้องตามโครงสร้างจริง คือปิด item สุดท้ายใน results +
    ปิด results เอง ก่อนขึ้น key "S_level") ถ้าไม่ใช่ ให้ตัด } ตัวแรกทิ้ง
    เพราะเป็นตัวเกิน — เคสปกติที่ไม่มี } เกินเลยจะได้ข้อความเดิมทุกตัวอักษร"""
    out = []
    in_string = False
    escape = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == '}':
            j = i + 1
            while j < n and text[j] in ' \t\r\n':
                j += 1
            if j < n and text[j] == '}':
                k = j + 1
                while k < n and text[k] in ' \t\r\n':
                    k += 1
                is_legit = False
                if k < n and text[k] == ',':
                    m = k + 1
                    while m < n and text[m] in ' \t\r\n':
                        m += 1
                    if text[m:m + 9] == '"S_level"':
                        is_legit = True
                if not is_legit:
                    # } ตัวแรกเป็นตัวเกิน — ข้ามไม่ต้องใส่ใน output
                    i += 1
                    continue
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _extract_json_text(raw: str) -> str:
    """แกะ JSON ออกจากคำตอบดิบของ AI (ตัด code fence / ข้อความปนหน้า-หลัง)

    เคสพิเศษ 1: local reasoning model (เช่น Qwen3) บางครั้ง "ร่าง" JSON เต็ม
    รูปแบบปนอยู่ในส่วน thinking เอง (ก่อน </think>) แล้วเขียน JSON จริงอีกรอบ
    หลัง </think> — ตัดทุกอย่างก่อน </think> ทิ้งก่อนเสมอถ้าเจอ tag นี้ ไม่กระทบ
    Gemini/Claude ที่ไม่เคยส่ง </think> มาอยู่แล้ว (เงื่อนไขนี้จะไม่ trigger เลย
    ถ้าไม่เจอ substring ดังกล่าว)

    เคสพิเศษ 2: บางครั้งโมเดลพ่วงข้อมูลส่วนเกินต่อท้าย JSON ที่สมบูรณ์แล้ว
    (เช่น total_score ที่ prompt ห้ามใส่ แต่โมเดลยังใส่มา) ทำให้ parse ทั้งก้อน
    ไม่ผ่าน (Extra data) — ใช้ json.JSONDecoder().raw_decode() แกะแค่ JSON
    object แรกที่สมบูรณ์ถูกต้องจากจุดเริ่มต้น แล้วตัดข้อมูลส่วนเกินท้ายๆทิ้งไปเลย
    (เคสปกติที่ไม่มีข้อมูลเกินต่อท้ายจะได้ผลเหมือนเดิมทุกประการ)

    เคสพิเศษ 3: บาง local model (พบกับ ministral-3:8b) แทรก // comment สไตล์
    JavaScript ปนกลาง object — ตัดออกด้วย _strip_line_comments ก่อนเสมอ
    (ฟังก์ชันนี้เว้น // ที่อยู่ในเครื่องหมายคำพูดไว้ ไม่กระทบข้อความจริง)

    เคสพิเศษ 4: ministral-3:8b บางครั้งแทรก " เกินต่อท้าย string value ที่ปิด
    สมบูรณ์แล้ว (พบใน field ที่มีข้อความ 2 ท่อนเชื่อมด้วย "และ") — ตัดออกด้วย
    _strip_stray_trailing_quote (ดู docstring ของฟังก์ชันนั้นสำหรับรายละเอียด)

    เคสพิเศษ 5: deepseek-r1:8b บางครั้งแทรก } เกินก่อนวงเล็บปิดที่ถูกต้องของ
    แต่ละ item ทำให้ "results" ปิดก่อนเวลา — ตัดออกด้วย
    _fix_duplicate_closing_braces (ดู docstring ของฟังก์ชันนั้นสำหรับรายละเอียด)

    เคสพิเศษ 6: qwen3.5:4b บางครั้งแทรก \\" เกิน (backslash+quote) ต่อท้าย
    string value ที่ปิดสมบูรณ์แล้ว — ตัดออกด้วย _strip_stray_trailing_backslash_quote
    (ดู docstring ของฟังก์ชันนั้นสำหรับรายละเอียด) — ฟังก์ชันนี้ต้องรันก่อน
    _strip_stray_trailing_quote (เคสพิเศษ 4) เสมอ ไม่เช่นนั้น _strip_stray_trailing_quote
    จะเข้าใจ \\" ผิดว่าเป็น " เดี่ยวๆ ที่เปิด string ใหม่ ทำให้เนื้อหาถัดไปทั้งก้อน
    ถูกกลืนเป็น string มั่ว (ยืนยันด้วยการทดสอบจริงกับตัวอย่างที่ error)

    เคสพิเศษ 7: qwen3.5:4b บางครั้งลืมใส่ " ตัวเปิด string ของ value แล้วใช้ \\"
    แทนตั้งแต่ต้นเลย (เช่น `"e": \\"\\"เนื้อหา...\\""`) — ตัดออกด้วย
    _fix_missing_value_open_quote (ดู docstring ของฟังก์ชันนั้นสำหรับรายละเอียด)
    ต้องรันก่อน _strip_stray_trailing_backslash_quote (เคสพิเศษ 6) เพราะเจาะจงจับ
    \\" เฉพาะตอนที่ตามหลัง : หรือ [ หรือ , (จุดเริ่ม value) เท่านั้น ไม่ชนกับกรณี
    \\" ที่โผล่ต่อท้าย string ที่ปิดไปแล้ว (คนละบริบท คนละฟังก์ชันรับผิดชอบ)

    เคสพิเศษ 8: qwen3.5:4b บางครั้งแทรก , เกินก่อนวงเล็บปิด } หรือ ] (trailing
    comma แบบ JavaScript ซึ่ง JSON มาตรฐานไม่รองรับ) — ตัดออกด้วย
    _strip_trailing_comma (ดู docstring ของฟังก์ชันนั้นสำหรับรายละเอียด)"""
    text = raw.strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    text = _strip_line_comments(text)
    text = _fix_missing_value_open_quote(text)
    text = _strip_stray_trailing_backslash_quote(text)
    text = _strip_stray_trailing_quote(text)
    text = _strip_trailing_comma(text)
    text = _fix_duplicate_closing_braces(text)

    start = text.find("{")
    if start == -1:
        raise ValueError("ไม่พบโครงสร้าง JSON ({ ... }) ในคำตอบของ AI")
    candidate = text[start:]

    try:
        _, end_idx = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"ไม่พบโครงสร้าง JSON ({{ ... }}) ในคำตอบของ AI: {e}")
    return candidate[:end_idx]


def _is_valid_p(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in (0, 1)


def _sequential_count(results: dict, order: list) -> int:
    """นับ item ที่ p=1 ต่อเนื่องจากต้นลิสต์ (ใช้กำหนด level ตาม Decision Tree)
    ทุก item ใน order ต้องมีอยู่ครบเสมอและมีค่า p ถูกต้อง (0/1) — ไม่มีการข้าม/หยุดกลางคันแล้ว
    (item หลังจุดที่ p=0 ตัวแรกยังต้องถูกประเมิน แค่ไม่ถูกนับเข้า count ที่มีผลต่อ level)"""
    count = 0
    stopped = False
    for code in order:
        item = results.get(code)
        if item is None:
            raise ValueError(f"{code}: ไม่มีข้อมูล (ต้องประเมินให้ครบทุกรายการเสมอ ห้ามข้าม)")
        p = item.get("p")
        if not _is_valid_p(p):
            raise ValueError(f"{code}: ค่า p ต้องเป็นเลข 0 หรือ 1 เท่านั้น (ได้ {p!r})")
        if not stopped:
            if p == 1:
                count += 1
            else:
                stopped = True
    return count


def _build_checklist(results: dict, order: list) -> list:
    checklist = []
    for code in order:
        item = results.get(code)
        if item is None:
            continue  # ไม่ควรเกิดแล้ว (ถูกดักไว้ที่ _sequential_count/_parse_and_score ก่อนหน้า) กันไว้เฉยๆ
        checklist.append({
            "item":      code,
            "reasoning": item.get("r", ""),
            "pass":      bool(item.get("p")),
            "evidence":  item.get("e", "")
        })
    return checklist


def _parse_and_score(parsed: dict, student_id: str) -> dict:
    if not isinstance(parsed.get("results"), dict):
        raise ValueError("ไม่พบ key 'results' หรือไม่ใช่ object")
    results = parsed["results"]

    # ปกติ S_level ต้องอยู่นอก results (ระดับบนสุด) ตามที่ prompt สั่ง แต่บาง
    # local model (พบกับ Typhoon2.5-Qwen3-4B) วางผิดที่ไปไว้เป็นสมาชิกใน results
    # แทน — fallback มองเข้าไปใน results ด้วยถ้าหาที่ระดับบนสุดไม่เจอ ไม่กระทบ
    # เคสที่วางถูกตำแหน่งอยู่แล้ว (เจอที่ระดับบนสุดก่อนเสมอ)
    s_level = parsed.get("S_level")
    if s_level is None and isinstance(results, dict):
        s_level = results.get("S_level")
    if not (isinstance(s_level, int) and not isinstance(s_level, bool) and s_level in (0, 1, 2, 3)):
        raise ValueError(f"'S_level' ต้องเป็นเลข 0-3 เท่านั้น (ได้ {s_level!r})")

    score = {"coherence": s_level}
    criteria_detail = {}

    for g, order in GROUP_ORDER.items():
        count = _sequential_count(results, order)
        level = LEVEL_MAP[g][count]
        score[GROUP_LABEL[g]] = level
        criteria_detail[GROUP_LABEL[g]] = {"checklist": _build_checklist(results, order)}

    # S1/S2 เก็บไว้เป็น audit เท่านั้น ไม่ผูกกับการคำนวณ score (ใช้ S_level ตรงๆ)
    # แต่ยังต้องมีครบทั้งคู่เสมอ (ตามกฎ "ประเมินครบทุกรายการ" ข้อ 1 ใหม่)
    for code in ("S1", "S2"):
        item = results.get(code)
        if item is None:
            raise ValueError(f"{code}: ไม่มีข้อมูล (ต้องประเมินให้ครบทุกรายการเสมอ ห้ามข้าม)")
        if not _is_valid_p(item.get("p")):
            raise ValueError(f"{code}: ค่า p ต้องเป็นเลข 0 หรือ 1 เท่านั้น (ได้ {item.get('p')!r})")
    criteria_detail["coherence"] = {"checklist": _build_checklist(results, ["S1", "S2"])}

    score["total"] = sum(score[k] * WEIGHTS[k] for k in WEIGHTS)

    detail = {
        "student_id":          student_id,
        "issues_from_problem": parsed.get("issues_from_problem", []),
        "criteria":            criteria_detail
    }
    return {"score": score, "detail": detail}


class AssessExpandPayload(BaseModel):
    file_name:    str              # ชื่อไฟล์ที่รออยู่ใน assess_pending เช่น "103001.json"
    raw_response: str              # คำตอบดิบจาก AI (ยังไม่ parse)
    elapsed_ms:   float | None = None  # optional — เวลาที่ใช้เรียกโมเดล (ms) จาก n8n
                                        # ไม่บังคับส่ง เพื่อไม่ให้ workflow เดิมที่ไม่ส่งค่านี้พัง


@app.post("/assess-expand")
def assess_expand(payload: AssessExpandPayload):
    try:
        pending_path = ASSESS_PENDING / payload.file_name
        if not pending_path.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์ใน assess_pending: {payload.file_name}"}

        student_id = re.sub(r"\.(json|txt)$", "", payload.file_name, flags=re.IGNORECASE)

        try:
            json_text = _extract_json_text(payload.raw_response)
            parsed = json.loads(json_text)
            result = _parse_and_score(parsed, student_id)
        except (ValueError, json.JSONDecodeError) as e:
            # ข้อมูลผิดปกติ — ไม่ย้ายไฟล์ ไม่เขียน output ปล่อยค้างใน assess_pending
            return {"status": "error", "student_id": student_id, "error": str(e)}

        ASSESS_OUTPUT.mkdir(parents=True, exist_ok=True)
        ASSESS_DONE.mkdir(parents=True, exist_ok=True)

        out_path = ASSESS_OUTPUT / f"{student_id}_assessment.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "student_id": student_id,
                    "score":      result["score"],
                    "elapsed_ms": payload.elapsed_ms,
                    "detail":     result["detail"]
                },
                f, ensure_ascii=False, indent=2
            )

        os.rename(str(pending_path), str(ASSESS_DONE / payload.file_name))

        return {
            "status":      "success",
            "student_id":  student_id,
            "score":       result["score"],
            "elapsed_ms":  payload.elapsed_ms,
            "output_file": str(out_path)
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Ollama Sanity-Test Workflow — Save Test Output (endpoint ใหม่แยกต่างหาก)
#
# *** ไม่แตะ /assess-expand และ /assess-expand-tokens เดิมแม้แต่บรรทัดเดียว ***
# ใช้เฉพาะตอนทดสอบ pipeline เบื้องต้น (เช่น prompt_test.txt "คุณคือใคร")
# ก่อนจะไปทดสอบ Rubric_prompt.txt เต็มรูปแบบ — ไม่ validate schema ใดๆ
# (ต่างจาก /assess-expand ที่บังคับ schema ของ Rubric) เพราะจุดประสงค์
# แค่เก็บ raw response ไว้ดูง่ายๆ ไม่ต้อง copy จาก n8n UI มาวางเอง
#
# เขียนลง data/test_output/ แยกจาก assess_output/ โดยเจตนา
# เพื่อไม่ให้ผลทดสอบ sanity-check ปนกับผลตรวจจริงของวิทยานิพนธ์
# ─────────────────────────────────────────────

TEST_OUTPUT = FILES_DIR / "test_output"

class SaveTestOutputPayload(BaseModel):
    file_name:         str                 # ชื่อไฟล์ผลลัพธ์ เช่น "prompt_test_qwen3-4b"
    raw_response:      str                 # คำตอบดิบจากโมเดล (ไม่ validate schema)
    model:             str  | None = None  # ชื่อโมเดลที่ใช้ทดสอบ (ถ้าอยากบันทึกไว้)
    thinking:          str  | None = None  # เนื้อ <think> ที่โมเดลสร้าง (เผื่อ think:false ปิดไม่สนิท จะได้เห็น)
    elapsed_ms:        float | None = None
    prompt_tokens:     int   | None = None
    completion_tokens: int   | None = None
    total_tokens:      int   | None = None


@app.post("/save-test-output")
def save_test_output(payload: SaveTestOutputPayload):
    try:
        TEST_OUTPUT.mkdir(parents=True, exist_ok=True)

        name = re.sub(r"\.(json|txt)$", "", payload.file_name, flags=re.IGNORECASE)
        out_path = TEST_OUTPUT / f"{name}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "file_name":         name,
                    "model":             payload.model,
                    "raw_response":      payload.raw_response,
                    "thinking":          payload.thinking,
                    "elapsed_ms":        payload.elapsed_ms,
                    "prompt_tokens":     payload.prompt_tokens,
                    "completion_tokens": payload.completion_tokens,
                    "total_tokens":      payload.total_tokens,
                    "saved_at":          datetime.now().isoformat(timespec="seconds")
                },
                f, ensure_ascii=False, indent=2
            )

        return {"status": "success", "output_file": str(out_path)}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Assessment Workflow — Expand + Score + Token Usage (endpoint ใหม่แยกต่างหาก)
#
# *** ไม่แตะ /assess-expand เดิมเลยแม้แต่บรรทัดเดียว *** ตัว endpoint นี้
# เป็นไฟล์/route ใหม่ทั้งหมด ใช้คู่กับ workflow ที่เรียก Gemini
# generateContent ตรง (httpRequest) แทน chainLlm — เพราะจะได้
# field "usageMetadata" (token จริงจาก provider) ติดมาด้วย ซึ่ง
# chainLlm เดิมไม่มีให้
#
# ใช้ตรรกะ parse/score เดียวกันกับ /assess-expand ทุกประการ
# (เรียก _extract_json_text / _parse_and_score ฟังก์ชันเดิมซ้ำ ไม่มี
# การเปลี่ยนกฎการให้คะแนนใดๆ) ต่างกันแค่รับ+บันทึก token usage เพิ่ม
# ─────────────────────────────────────────────

class AssessExpandTokensPayload(BaseModel):
    file_name:         str                 # ชื่อไฟล์ที่รออยู่ใน assess_pending
    raw_response:      str                 # ข้อความคำตอบจากโมเดล (ยังไม่ parse)
    elapsed_ms:        float | None = None # เวลาที่ใช้เรียกโมเดล (ms)
    prompt_tokens:     int   | None = None # token ฝั่ง input ตามที่ provider รายงาน
    completion_tokens: int   | None = None # token ฝั่ง output ตามที่ provider รายงาน
    total_tokens:      int   | None = None # รวม (เผื่อ provider ส่งมาให้ตรงๆ)


@app.post("/assess-expand-tokens")
def assess_expand_tokens(payload: AssessExpandTokensPayload):
    try:
        pending_path = ASSESS_PENDING / payload.file_name
        if not pending_path.exists():
            return {"status": "error", "error": f"ไม่พบไฟล์ใน assess_pending: {payload.file_name}"}

        student_id = re.sub(r"\.(json|txt)$", "", payload.file_name, flags=re.IGNORECASE)

        try:
            json_text = _extract_json_text(payload.raw_response)
            parsed = json.loads(json_text)
            result = _parse_and_score(parsed, student_id)
        except (ValueError, json.JSONDecodeError) as e:
            # ข้อมูลผิดปกติ — ไม่ย้ายไฟล์ ไม่เขียน output ปล่อยค้างใน assess_pending
            return {"status": "error", "student_id": student_id, "error": str(e)}

        ASSESS_OUTPUT.mkdir(parents=True, exist_ok=True)
        ASSESS_DONE.mkdir(parents=True, exist_ok=True)

        out_path = ASSESS_OUTPUT / f"{student_id}_assessment.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "student_id":         student_id,
                    "score":              result["score"],
                    "elapsed_ms":         payload.elapsed_ms,
                    "prompt_tokens":      payload.prompt_tokens,
                    "completion_tokens":  payload.completion_tokens,
                    "total_tokens":       payload.total_tokens,
                    "detail":             result["detail"]
                },
                f, ensure_ascii=False, indent=2
            )

        os.rename(str(pending_path), str(ASSESS_DONE / payload.file_name))

        return {
            "status":             "success",
            "student_id":         student_id,
            "score":              result["score"],
            "elapsed_ms":         payload.elapsed_ms,
            "prompt_tokens":      payload.prompt_tokens,
            "completion_tokens":  payload.completion_tokens,
            "total_tokens":       payload.total_tokens,
            "output_file":        str(out_path)
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
