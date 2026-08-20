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
   ollama pull llama3.1:8b
   ollama pull deepseek-r1:8b
   ollama pull gemma:7b
   ollama pull qwen2.5:7b
   ```
3. Ensure Native Ollama service is active at `http://localhost:11434` (or `http://host.docker.internal:11434` inside Docker containers).

### Step 2: Clone & Configure Environment
1. Clone this repository:
   ```bash
   git clone https://github.com/gchatree/aes-staff-study.git
   cd aes-staff-study
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
aes-staff-study/
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
