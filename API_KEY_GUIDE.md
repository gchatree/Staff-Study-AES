# 🔑 คู่มือการขอรับและตั้งค่า API Key พร้อมการเปิดใช้งาน Billing (API Key & Billing Setup Guide)

คู่มือนี้แนะนำขั้นตอนการขอรับ API Key และการเปิดใช้งานระบบชำระเงิน (Billing Setup) สำหรับโมเดลปัญญาประดิษฐ์ฝั่ง Cloud (**Google Gemini** และ **Anthropic Claude**) เพื่อนำมาใช้ร่วมกับระบบประเมินงานเขียนอัตโนมัติ (Staff-Study-AES)

---

## ⚠️ ข้อสังเกตสำคัญจากการทดลองทางวิชาการ (Critical Research Note)

> 🚨 **ข้อควรระวังเรื่อง Rate Limits:**  
> จากผลการทดลองเปรียบเทียบในระยะที่ 2 ของการวิจัยพบว่า **บัญชีทดลองฟรี (Free Tier / Trial Keys) ของทั้งสองผู้ให้บริการ ไม่สามารถประมวลผลการประเมินบทความวิชาการที่มีความยาวและโครงสร้างซับซ้อนได้จนจบไปป์ไลน์** เนื่องจากติดข้อจำกัดอัตราคำสั่งต่อนาที (Rate Limit: RPM/TPM) และเกิดข้อผิดพลาด `HTTP 429 Too Many Requests` หรือคำตอบถูกตัดกลางคัน  
> 
> **ดังนั้น ผู้ใช้งานจำเป็นต้องเปิดใช้งานระบบชำระเงินตามจริง (Pay-as-you-go / Paid Tier) กับทั้งสองผู้ให้บริการเพื่อปลดล็อกโควตาให้ระบบประมวลผลได้อย่างสมบูรณ์**

---

## 🔵 Part 1: การขอรับ Google Gemini API Key และการตั้งค่า Billing

### 1.1 ขั้นตอนการขอรับ API Key:
1. เข้าไปที่เว็บ **Google AI Studio**: [https://aistudio.google.com](https://aistudio.google.com)
2. เข้าสู่ระบบ (Log in) ด้วยบัญชี Google Account (Gmail)
3. ที่เมนูซ้ายมือ คลิกปุ่ม **"Get API key"** ➔ กด **Create API key in new project**
4. คัดลอกรหัส API Key (`AIzaSy...`) ไว้ใช้ในระบบ

### 1.2 ขั้นตอนการเปิดใช้งาน Billing (Pay-as-you-go):
1. ที่หน้า Google AI Studio คลิกเมนู **"Plan & Billing"** หรือเข้าไปที่ [Google Cloud Billing Console](https://console.cloud.google.com/billing)
2. เลือกโครงการ (Project) เดียวกับที่สร้าง API Key ไว้
3. คลิก **"Set up billing account"** หรือ **"Enable Pay-as-you-go"**
4. ผูกบัตรเครดิต/เดบิตเพื่อเปิดใช้งานชำระเงินตามจริง  
   *(การเปิด Pay-as-you-go จะเพิ่มโควตาจาก 15 RPM เป็น 360+ RPM ทำให้ระบบประเมินรันบทความยาวได้อย่างต่อเนื่องโดยไม่สะดุด)*

---

## 🟠 Part 2: การขอรับ Anthropic Claude API Key และการตั้งค่า Billing

### 2.1 ขั้นตอนการขอรับ API Key:
1. เข้าไปที่เว็บ **Anthropic Console**: [https://console.anthropic.com](https://console.anthropic.com)
2. ลงทะเบียนสมัครสมาชิก (Sign up) หรือเข้าสู่ระบบ (Log in)
3. ไปที่เมนู **"API Keys"** ➔ คลิกปุ่ม **"Create Key"**
4. ตั้งชื่อคีย์แล้วกด **Create Key** ➔ คัดลอกรหัส API Key (`sk-ant-...`) ไว้ในที่ปลอดภัย

### 2.2 ขั้นตอนการเติมเงินเพื่อเปิดใช้งาน (Claim / Prepaid Billing):
1. ไปที่เมนู **"Plans & Billing"** บน Anthropic Console
2. คลิกปุ่ม **"Add Funds"** หรือ **"Claim / Claim Credits"**
3. กรอกข้อมูลบัตรและทำการเติมเงินขั้นต่ำ (เช่น $5–$10 USD) เพื่อยกระดับจากบัญชีทดลอง เป็น **Build Tier 1 (or Tier 2)**
4. เมื่อมีเครดิตในบัญชี ระบบจะอนุญาตให้ส่ง Prompt ขนาดใหญ่ (เช่น Rubric_prompt.txt ขนาด 58KB) และประมวลผลบทความยาวได้อย่างสมบูรณ์โดยไม่ถูกตัดสาย

---

## 🛠️ Part 3: การนำ API Key ไปตั้งค่าในระบบ

ท่านสามารถนำ API Key ที่ขอได้ไปตั้งค่าใช้งานได้ **2 ช่องทาง** ดังนี้:

### วิธีที่ 1: ตั้งค่าผ่านไฟล์ `.env` (แนะนำสำหรับระบบภาพรวม)
1. คัดลอกไฟล์แม่แบบ `.env.example` เป็น `.env` ในโฟลเดอร์โครงการ:
   ```bash
   cp .env.example .env
   ```
2. เปิดไฟล์ `.env` ด้วยโปรแกรมแก้ไขข้อความ (Text Editor / VS Code)
3. วางคีย์ของท่านลงในบรรทัดที่เกี่ยวข้อง:
   ```ini
   GOOGLE_API_KEY=AIzaSyรหัสคีย์จริงของท่านที่นี่
   ANTHROPIC_API_KEY=sk-ant-รหัสคีย์จริงของท่านที่นี่
   ```

### วิธีที่ 2: ตั้งค่าใน Credential ของ n8n (สำหรับรัน Workflow รายตัว)
- **สำหรับ Google Gemini (`Rubric Assessment Workflow (gemini-3.5-flash).json`):**
  1. ดับเบิลคลิกเปิด Node **`Call Gemini API Direct`**
  2. หัวข้อ Authentication ➔ เลือก **Generic Credential Type** ➔ **Query Auth**
  3. สร้าง Credential: กำหนด **Name:** `key` | กำหนด **Value:** วางรหัส Google Gemini API Key (`AIzaSy...`)

- **สำหรับ Anthropic Claude (`Rubric Assessment Workflow (claude-sonnet-5).json`):**
  1. ดับเบิลคลิกเปิด Node **`Call Claude API Direct`**
  2. หัวข้อ Authentication ➔ เลือก **Generic Credential Type** ➔ **Header Auth**
  3. สร้าง Credential: กำหนด **Name:** `x-api-key` | กำหนด **Value:** วางรหัส Anthropic Claude API Key (`sk-ant-...`)
