# AI-Based Assessment Framework for Complex Structured Academic Writing (AES Pipeline)

[![Educational Technology](https://img.shields.io/badge/Field-Educational%20Technology-blue.svg)](https://edu.swu.ac.th)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Framework-n8n](https://img.shields.io/badge/Pipeline-n8n%20Workflow-red.svg)](https://n8n.io)
[![Engine-FastAPI](https://img.shields.io/badge/Engine-Python%20FastAPI-green.svg)](https://fastapi.tiangolo.com)

An Open-Source Research Artifact and Automated Essay Scoring (AES) Pipeline developed for evaluating complex structured academic writing (**Staff Study / บันทึกความเห็นฝ่ายอำนวยการ**). 

This repository is part of the Doctoral Dissertation:
> **"Development of an AI-Based Assessment Framework for Complex Structured Academic Writing"**  
> **"การพัฒนารูปแบบระบบประเมินงานเขียนเชิงวิชาการที่มีโครงสร้างซับซ้อนโดยใช้เทคโนโลยีปัญญาประดิษฐ์"**  
> 
> **Author:** Chatree Saengtongsrikamon (ชาตรี แสงทองศรีกมล)  
> **Degree:** Doctor of Education (Educational Technology), Faculty of Education, Srinakharinwirot University (2025 / 2568)  
> **Advisors:** Assoc. Prof. Dr. Khwanying Sriprasertpap & Asst. Prof. Dr. Jaemjan Sriarunrasmee

---

## 🌟 Key Research & Technical Features

1. **Theoretical Grounding:** Built upon Evidence-Centered Design (ECD), Messick's Construct Validity Framework, SOLO Taxonomy, and Paul-Elder Critical Thinking Principles.
2. **Multi-Aspect Rubric (P-F-C-R-S):** Evaluates 5 dimensions across 17 granular sub-items:
   - **P (Problem Statement):** Weight x1 (Max 3 pts)
   - **F (Facts & Evidence):** Weight x2 (Max 6 pts)
   - **C (Consideration & Analysis):** Weight x4 (Max 12 pts)
   - **R (Recommendations & Actionability):** Weight x1 (Max 3 pts)
   - **S (Structural & Logical Coherence):** Weight x2 (Max 6 pts)
3. **Decoupled Prompting Architecture:** 
   - **LLM Layer:** Evaluates 17 sub-items objectively and extracts direct textual evidence without cognitive overload.
   - **Python Engine Layer (n8n Node):** Handles weighted calculation, decision tree rules, short-circuiting logic, and deterministic score mapping (0–3 level).
4. **Multi-Model LLM Benchmarking:** Includes workflows for testing 14 Cloud and Local Open-Source LLMs (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, Llama 3.1 8B, DeepSeek-R1 8B, Gemma 3 4B, Ministral 3 8B, Qwen 2.5/3, Typhoon 2.5, Chinda Qwen, etc.).

---

## ⚡ Important Technical Note: Local LLM Execution (Native Ollama vs Docker)

During Phase 2 experimental benchmarking, we evaluated two local execution strategies for Ollama:
- ❌ **Containerized Ollama (in Docker):** Running Ollama inside a standard Docker container resulted in severe CPU bottlenecks and slow inference latency because container virtualized layers struggled with host GPU passthrough overhead.
- ✅ **Native Ollama (Host OS) [RECOMMENDED]:** Running **Native Ollama directly on the host operating system** (macOS / Linux / Windows) enables full GPU acceleration (Apple Silicon Metal / NVIDIA CUDA), delivering up to **10x–20x faster inference throughput**.

> **Recommendation:** Run **Native Ollama on your host OS** for model serving, while using **Docker Compose** to run the Python Scoring API and n8n Workflow Engine.

---

## 🚀 Quick Start & Installation Guide

### Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose installed on Host OS.
- [Ollama](https://ollama.com/) installed natively on Host OS (for Local LLM testing).

### Step 1: Install & Launch Native Ollama (Host OS)
1. Download and install Native Ollama from [https://ollama.com](https://ollama.com).
2. Open terminal/command prompt and pull your desired benchmarking model(s):
   ```bash
   ollama pull qwen3:4b
   ollama pull gemma4:latest
   ollama pull llama3.1:8b
   ollama pull deepseek-r1:8b
   ```
3. Ensure Native Ollama service is active at `http://localhost:11434` (or `http://host.docker.internal:11434` inside Docker containers).

### Step 2: Clone & Configure Environment
1. Clone this repository:
   ```bash
   git clone https://github.com/gchatree/Staff-Study-AES.git
   cd Staff-Study-AES
   ```
2. Create environment configuration file:
   ```bash
   cp .env.example .env
   ```
3. Fill in your API keys in `.env` (if using Cloud Models like OpenAI, Anthropic Claude, or Google Gemini).

### Step 3: Launch Services via Docker Compose
Start the Python FastAPI Scoring Engine and n8n Pipeline:
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Step 4: Access n8n & Import Workflows
1. Open your browser and navigate to `http://localhost:5678`.
2. Set up your n8n account.
3. Navigate to **Workflows -> Import from File** and select any `.json` workflow file from the `n8n/workflow/` directory.

---

## 📁 Repository Structure

```text
Staff-Study-AES/
├── api/                        # Python FastAPI Scoring Engine
│   ├── main.py                 # Core scoring logic, Decision Tree, & Weighted Aggregation
│   └── requirements.txt        # Python package dependencies
├── data/                       # Prompts & Data Directories
│   ├── prompts/                # Validated System Prompts (Rubric_10.docx, Rubric_prompt.txt, Rubric_prompt_local.txt)
│   ├── assess_pending/         # Ingestion directory for pending essays
│   ├── assess_output/          # Raw AI response outputs
│   └── assess_done/            # Final structured JSON evaluation results
├── docker/                     # Containerization Files
│   ├── Dockerfile              # Python API container build instructions
│   └── docker-compose.yml      # Multi-container orchestration (n8n + API)
├── n8n/                        # Workflow Automation Layer
│   └── workflow/               # 14 Exported n8n Workflow JSON files
├── .env.example                # Template for API keys and environment variables
├── .gitignore                  # Git exclusions (privacy protection & runtime cache)
└── README.md                   # Project documentation (this file)
```

---

## 📖 Citation

If you use this framework, prompts, or workflows in your academic research, please cite:

```bibtex
@phdthesis{saengtongsrikamon2025development,
  title        = {Development of an AI-Based Assessment Framework for Complex Structured Academic Writing},
  author       = {Saengtongsrikamon, Chatree},
  year         = {2025},
  school       = {Srinakharinwirot University},
  degree       = {Doctor of Education (Educational Technology)},
  address      = {Bangkok, Thailand}
}
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

<br>
<hr>
<br>

# 🇹🇭 คู่มือการใช้งานภาษาไทย (Thai Version)

คลังรหัสต้นฉบับและระบบประเมินงานเขียนอัตโนมัติ (Automated Essay Scoring: AES) สำหรับงานเขียนเชิงวิชาการที่มีโครงสร้างซับซ้อน (**บันทึกความเห็นฝ่ายอำนวยการ / Staff Study**)

โครงการนี้เป็นส่วนหนึ่งของปริญญานิพนธ์ระดับดุษฎีบัณฑิต:
> **"การพัฒนารูปแบบระบบประเมินงานเขียนเชิงวิชาการที่มีโครงสร้างซับซ้อนโดยใช้เทคโนโลยีปัญญาประดิษฐ์"**  
> 
> **ผู้วิจัย:** ชาตรี แสงทองศรีกมล  
> **ปริญญา:** การศึกษาดุษฎีบัณฑิต (เทคโนโลยีการศึกษา) คณะศึกษาศาสตร์ มหาวิทยาลัยศรีนครินทรวิโรฒ (ปีการศึกษา 2568)  
> **อาจารย์ที่ปรึกษา:** รศ.ดร.ขวัญหญิง ศรีประเสริฐภาพ และ ผศ.ดร.แจ่มจันทร์ ศรีอรุณรัศมี

---

## 🌟 คุณลักษณะเด่นเชิงวิจัยและเทคโนโลยี

1. **ฐานทฤษฎีการวัดผล:** ออกแบบตามกรอบ Evidence-Centered Design (ECD), Construct Validity ของ Messick, SOLO Taxonomy และ Paul-Elder Critical Thinking
2. **เกณฑ์การประเมินแบบผสม 5 มิติ (P-F-C-R-S):** ประเมินครอบคลุม 17 ข้อรายการย่อย:
   - **P (ปัญหา):** น้ำหนัก ×1 (คะแนนเต็ม 3)
   - **F (ข้อเท็จจริง):** น้ำหนัก ×2 (คะแนนเต็ม 6)
   - **C (ข้อพิจารณา):** น้ำหนัก ×4 (คะแนนเต็ม 12)
   - **R (ข้อเสนอ):** น้ำหนัก ×1 (คะแนนเต็ม 3)
   - **S (ความเชื่อมโยงตลอดสาย):** น้ำหนัก ×2 (คะแนนเต็ม 6)
3. **สถาปัตยกรรมชุดคำสั่งแบบแยกหน้าที่ (Decoupled Prompting):**
   - **ชั้นโมเดล AI (LLM Layer):** ทำหน้าที่ประเมิน 17 ข้อรายการย่อยและสกัดหลักฐาน (Evidence Quote) จากงานเขียน เพื่อลดภาระทางปัญญา
   - **ชั้นเครื่องมือคำนวณ (Python Node บน n8n):** ทำหน้าที่คำนวณคะแนนถ่วงน้ำหนัก ตรรกะ Decision Tree และการสรุประดับคะแนน 0–3 อย่างตรงไปตรงมา
4. **การทดสอบเปรียบเทียบ 14 โมเดล:** รองรับการทดสอบทั้ง Cloud LLMs (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro) และ Local Open-Source LLMs (Llama 3.1 8B, DeepSeek-R1 8B, Gemma 3 4B, Ministral 3 8B, Qwen, Typhoon 2.5 ฯลฯ)

---

## ⚡ หมายเหตุเชิงเทคนิคสำคัญ: การใช้งาน Local LLMs (Ollama)

จากการทดสอบเปรียบเทียบประสิทธิภาพในระยะที่ 2 พบว่า:
- ❌ **การรัน Ollama ใน Docker:** ทำให้การประมวลผลช้ามากและเกิดคอขวดที่ CPU เนื่องจากชั้น Virtualization ของ Docker ไม่สามารถดึงพลังจาก GPU ของเครื่อง Host มาใช้ได้อย่างเต็มประสิทธิภาพ
- ✅ **การรัน Native Ollama (บน Host OS) [แนะนำอย่างยิ่ง]:** การติดตั้งและรัน **Native Ollama บนระบบปฏิบัติการของเครื่องโดยตรง** (macOS / Linux / Windows) จะเปิดใช้งาน GPU Acceleration (Apple Silicon Metal / NVIDIA CUDA) ได้เต็มร้อย ส่งผลให้ประมวลผลเร็วขึ้น **10 ถึง 20 เท่า**

> **ข้อแนะนำ:** ให้รัน **Native Ollama บนเครื่อง Host OS** สำหรับให้บริการโมเดล AI ส่วน Python Scoring API และระบบ n8n ให้รันผ่าน **Docker Compose**

---

## 🚀 คู่มือการติดตั้งและการใช้งานอย่างรวดเร็ว

### สิ่งที่ต้องเตรียมก่อนติดตั้ง
- ติดตั้ง [Docker](https://www.docker.com/) & Docker Compose บนเครื่อง Host OS
- ติดตั้ง [Ollama](https://ollama.com/) แบบ Native บนเครื่อง Host OS (กรณีต้องการทดสอบ Local LLMs)

### ขั้นตอนที่ 1: ติดตั้งและเปิดใช้งาน Native Ollama (Host OS)
1. ดาวน์โหลดและติดตั้ง Native Ollama จาก [https://ollama.com](https://ollama.com)
2. เปิด Terminal/Command Prompt แล้วดาวน์โหลดโมเดลที่ต้องการทดสอบ:
   ```bash
   ollama pull qwen3:4b
   ollama pull gemma4:latest
   ollama pull llama3.1:8b
   ollama pull deepseek-r1:8b
   ```
3. ตรวจสอบให้แน่ใจว่า Native Ollama ทำงานอยู่ที่พอร์ต `http://localhost:11434` (หรือ `http://host.docker.internal:11434` สำหรับเรียกจากใน Docker)

### ขั้นตอนที่ 2: ดึงคลังรหัสและตั้งค่าระบบ
1. ดึงคลังรหัสต้นฉบับจาก GitHub:
   ```bash
   git clone https://github.com/gchatree/Staff-Study-AES.git
   cd Staff-Study-AES
   ```
2. คัดลอกไฟล์ตั้งค่าสภาพแวดล้อม:
   ```bash
   cp .env.example .env
   ```
3. กรอก API Keys ของท่านในไฟล์ `.env` (หากต้องการใช้งาน Cloud Models เช่น OpenAI, Anthropic Claude, หรือ Google Gemini)

### ขั้นตอนที่ 3: เปิดใช้งานระบบด้วย Docker Compose
สั่งรัน Python FastAPI Scoring Engine และระบบ n8n:
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### ขั้นตอนที่ 4: เข้าใช้งาน n8n และนำเข้า Workflows
1. เปิดเว็บเบราว์เซอร์ไปที่ `http://localhost:5678`
2. ตั้งค่าบัญชีผู้ใช้ n8n
3. ไปที่เมนู **Workflows -> Import from File** แล้วเลือกไฟล์ `.json` จากโฟลเดอร์ `n8n/workflow/` ที่ต้องการทดสอบ

---

## 📁 โครงสร้างโฟลเดอร์ในโครงการ

```text
Staff-Study-AES/
├── api/                        # เครื่องมือคำนวณคะแนน Python FastAPI (Scoring Engine)
│   ├── main.py                 # โค้ดหลักคำนวณ Decision Tree และคะแนนถ่วงน้ำหนัก
│   └── requirements.txt        # รายชื่อคลังไลบรารี Python
├── data/                       # โฟลเดอร์ Prompts และข้อมูลประเมิน
│   ├── prompts/                # ชุดคำสั่งระบบที่ผ่านการทวนสอบ (Rubric_10.docx, Rubric_prompt.txt, Rubric_prompt_local.txt)
│   ├── assess_pending/         # โฟลเดอร์พักงานเขียนที่รอประเมิน
│   ├── assess_output/          # ผลลัพธ์การประเมินดิบจาก AI
│   └── assess_done/            # ผลลัพธ์คะแนน JSON ฉบับสมบูรณ์
├── docker/                     # ไฟล์ระบบจำลอง Docker
│   ├── Dockerfile              # คำสั่งสร้าง Container ของ Python API
│   └── docker-compose.yml      # การเชื่อมต่อระบบรันคู่กัน (n8n + API)
├── n8n/                        # ชั้นผังกระบวนการอัตโนมัติ n8n
│   └── workflow/               # ไฟล์ส่งออก n8n Workflow JSON รวม 14 ไฟล์
├── .env.example                # แม่แบบตั้งค่า API Keys และตัวแปรระบบ
├── .gitignore                  # คำสั่งข้ามการ Upload ไฟล์ส่วนตัวและแคช
└── README.md                   # เอกสารอธิบายโครงการ (ไฟล์นี้)
```

---

## 📖 การอ้างอิงงานวิจัย (Citation)

หากท่านนำกรอบแนวคิด ชุดคำสั่ง หรือผังกระบวนการไปใช้ในการวิจัย กรุณาอ้างอิงดังนี้:

```bibtex
@phdthesis{saengtongsrikamon2025development,
  title        = {Development of an AI-Based Assessment Framework for Complex Structured Academic Writing},
  author       = {Saengtongsrikamon, Chatree},
  year         = {2025},
  school       = {Srinakharinwirot University},
  degree       = {Doctor of Education (Educational Technology)},
  address      = {Bangkok, Thailand}
}
```

---

## 📄 สิทธิ์การใช้งาน (License)

เผยแพร่ภายใต้สิทธิ์ใช้งานแบบ MIT License อ่านรายละเอียดเพิ่มเติมได้ในไฟล์ `LICENSE`
