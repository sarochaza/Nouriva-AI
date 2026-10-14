# Noura AI — Image Nutrition Benchmark v2

Workspace สำหรับเปรียบเทียบ **Single LLM, Multi-Agent และ Ensemble** จากภาพอาหาร โดยทุกวิธีใช้ SQLite, Ingredient Matcher, สูตร Python และเกณฑ์ประเมินเดียวกัน

**สถานะส่งมอบ: MOCK TEST PASSED / REAL API NOT VERIFIED**

ทดสอบโค้ดและ Mock ใน Linux แล้ว ยังไม่ได้เรียก Groq จริง ยังไม่ได้เข้าถึง Dataset บนเครื่อง Windows ของคุณ และยังไม่ได้รัน PowerShell บน Windows จริง ผล Mock ใน ZIP เป็นการตรวจซอฟต์แวร์เท่านั้น ไม่ใช่ผลความแม่นยำของ AI

## เริ่มใช้งานบน Windows

ต้องมี Python 3.10 ขึ้นไป แตก ZIP แล้วเปิด PowerShell ในโฟลเดอร์ `Noura-AI-Nutrition-Benchmark` ไม่ต้องเปิด Docker และไม่ต้องดาวน์โหลด Dataset ซ้ำ

รันทดสอบแบบไม่ใช้ API ก่อน:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\START_HERE.ps1 -Mode Mock
```

สคริปต์สร้าง `.venv` และ `.env` จากตัวอย่างให้ ใช้ Python ใน `.venv` โดยตรง จึงไม่ต้อง Activate และไม่ต้องติดตั้งแพ็กเกจสำหรับระบบหลัก

จากนั้นเปิด `.env` แล้วแทน `PASTE_YOUR_GROQ_API_KEY_HERE` ด้วยคีย์ของคุณ:

```powershell
notepad .env
notepad config\models.yaml
```

ชื่อโมเดลอยู่ใน Config เท่านั้น ค่าเริ่มต้นเป็นโมเดล Vision ที่เอกสาร Groq ระบุ ณ วันที่ตรวจสอบ เปลี่ยน ID และรายการ `vision_confirmed_models` ให้ตรงกันหากบริการเปลี่ยน ก่อนรันจริงตรวจทั้งการรองรับภาพและ JSON จาก [Groq Vision](https://console.groq.com/docs/vision) การปรากฏในรายการ `/models` อย่างเดียวไม่ยืนยันความสามารถ Vision

ดูรายชื่อโมเดลที่บัญชีเข้าถึงได้ด้วย GET เท่านั้น ไม่มี inference:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_setup --list-models
```

Smoke จริง: **5 ภาพ × 3 วิธี × 3 รอบ = 45 การประเมิน** ใช้ nominal 105 model calls หากทุกขั้นสำเร็จ ยังไม่รวม Retry คำสั่งนี้เริ่มเรียก API จริง:

```powershell
.\START_HERE.ps1 -Mode Smoke -DatasetPath 'C:\Users\CHOMP2O\food-nutrients' -RunId smoke-v1
```

Pilot จริง: **30 ภาพ × 3 วิธี × 3 รอบ = 270 การประเมิน** ใช้ nominal 630 model calls หากทุกขั้นสำเร็จ ยังไม่รวม Retry:

```powershell
.\START_HERE.ps1 -Mode Pilot -DatasetPath 'C:\Users\CHOMP2O\food-nutrients' -RunId pilot-v1
```

ผลจะอยู่ใน `results\real\<RunId>\comparison\report.md` พร้อม CSV/JSON ไม่รวมผล Mock ค่า Cost เป็นค่าว่างหากยังไม่ได้ตั้งราคาใน Config ห้ามอ่านค่าว่างเป็นค่าใช้จ่ายศูนย์

## คำสั่งแยกทีละขั้น

```powershell
.\START_HERE.ps1 -Mode Setup
$NouraPython = '.\.venv\Scripts\python.exe'
& $NouraPython -m unittest discover -v
& $NouraPython -m scripts.prepare_dataset --dataset-root 'C:\Users\CHOMP2O\food-nutrients' --count 5 --seed 20261013 --out data\prepared\smoke
& $NouraPython -m scripts.run_experiment --mode real --prepared data\prepared\smoke --run-id smoke-v1
& $NouraPython -m evaluation.evaluate --run-dir results\real\smoke-v1 --truth data\prepared\smoke\ground_truth.json
```

ข้ามคำสั่ง Prepare หากเคยเตรียมโฟลเดอร์นั้นแล้ว ระบบจะไม่เขียนทับชุดภาพเดิม หากจะเปลี่ยน Dataset/Seed ให้เตรียมโฟลเดอร์ใหม่และใช้ Run ID ใหม่

รันทีละวิธีหรือทีละรอบได้ เช่น:

```powershell
& $NouraPython -m scripts.run_experiment --mode real --prepared data\prepared\smoke --run-id smoke-v1 --method single --round 1
```

รันคำสั่งเดิมเพื่อทำรายการที่ยังไม่ได้รันต่อ ผลที่มีแล้วจะไม่ถูกเรียก API ซ้ำ หากต้องการลองเฉพาะรายการ `FAILED` อีกครั้ง:

```powershell
& $NouraPython -m scripts.run_experiment --mode real --prepared data\prepared\smoke --run-id smoke-v1 --retry-failed
```

ระบบเก็บประวัติเดิมและรวมจำนวน Attempt, Token ที่ทราบ และ Latency ที่ใช้แล้ว รายการ `REVIEW_REQUIRED` ไม่ถูกทำนายซ้ำอัตโนมัติ ให้ตรวจเหตุผลจาก Coverage หากแก้ฐานข้อมูลหรือ Alias ต้องเริ่มชุดทดลองใหม่ ไม่แก้เฉพาะวิธีที่แพ้

## Dataset Loader

ไม่มีโค้ดดาวน์โหลด Dataset 1.31 GB หรือ Nutrition5k 181 GB ใช้ไฟล์ที่คุณมีอยู่แล้ว:

```text
C:\Users\CHOMP2O\food-nutrients\
  metadata.jsonl
  test\dish_*.png
```

รองรับ metadata ที่อยู่ใน `test\` ด้วย โดย relative path อ้างจากโฟลเดอร์ของ metadata ถ้ามีมากกว่าหนึ่งไฟล์ ให้กำหนด `--metadata` ระบุไฟล์จริง

ตรวจชื่อ Field จาก publisher `metadata.jsonl`: `file_name`, `id`, `ingredients`, `total_calories`, `total_mass`, `total_fat`, `total_carb`, `total_protein` ส่วน ingredient ใช้ `id`, `name`, `grams`, `calories`, `fat`, `carb`, `protein` ตัวอ่านจะตรวจไฟล์บนเครื่องคุณอีกครั้ง ค่า mass/macros เป็นกรัม พลังงานเป็น kcal ตามสัญญาข้อมูลของ Dataset หน่วยไม่ได้เดาจากขนาดตัวเลข

ID ต้องตรงกับชื่อภาพ Missing/ผิดรูปแบบถูกบันทึกใน `dataset_audit.json` ไม่มีการสร้าง Ground Truth แทน หากข้อมูลคนละ Schema ให้ใช้ `--schema config\metadata_schema.json` พร้อมแก้ Mapping ให้ตรงกับหลักฐานจริง

คัดภาพแบบ Seed คงที่ โดยเลือกตัวแทนต่อกลุ่ม ingredient/gram ที่เหมือนกัน เพื่อลดการหยิบหลายเฟรมของจานเดียวกัน แล้วกระจายตาม Energy quartile และจำนวนส่วนประกอบ การคัดนี้ใช้ Ground Truth ได้เฉพาะขั้นเตรียมข้อมูล ไม่มีการรับรองความหลากหลายของลักษณะภาพด้วยวิธีนี้

`manifest.json` มีเพียง ID, ตำแหน่งภาพ และ Hash ส่วนฉลากอยู่ใน `ground_truth.json` แยกไว้ Inference ไม่อ่านค่าฉลาก API ได้เพียงภาพและ Prompt รวมถึงผล AI ก่อนหน้าเฉพาะ Multi-Agent ไม่ส่งชื่อไฟล์/ID/น้ำหนักจริง/สารอาหารจริง

## Nutrition Database

SQLite พร้อมใช้: `nutrition_database\ingredients.sqlite` รวม 13,661 food records จาก USDA ก่อนนำเข้าไทย ตารางเพิ่มเติม: `sources`, `aliases`, `measures`, `measure_links`, `recipe_components`

อ่านผลตรวจละเอียดจาก:

- `docs\DATA_AUDIT_REPORT_TH.md` และ JSON ใน `nutrition_database\normalized\`
- `docs\DATABASE_COVERAGE_REPORT_TH.md`
- `nutrition_database\database_audit.csv`

สูตรเดียวกันทุกวิธี:

```text
สารอาหารของส่วนประกอบ = น้ำหนักที่ AI ประมาณเป็นกรัม / 100 × ค่าฐานข้อมูลต่อ 100 กรัม
```

Matcher อัตโนมัติใช้ชื่อและสถานะตรงกัน หรือ Alias ที่ผ่านการตรวจเท่านั้น Fuzzy เป็นรายการเสนอให้ตรวจ ไม่เลือกแทนเอง ถ้าชื่อและสถานะเหมือนกันทุกประการแต่มีหลาย Source ใช้ลำดับที่กำหนดก่อนทดลอง `SR_Legacy → Foundation → FNDDS` เก็บ ID ของ Source อื่นไว้ใน Trace ไม่ผสมค่าโภชนาการจากหลาย Source ถ้ามีหลายรายการภายใน Source ที่เลือก ยังต้องตรวจ

Alias ภาษาไทย/อังกฤษต้องระบุ Food ID และเหตุผล การพิมพ์ว่า “ข้าว” ไม่ให้อำนาจระบบเลือกว่าเป็นข้าวสาร ข้าวสุก ข้าวกล้อง หรือข้าวเหนียว

ลองค้นด้วยตัวเอง:

```powershell
& $NouraPython -m scripts.lookup_ingredient --name 'แครอท' --state raw
& $NouraPython -m scripts.lookup_ingredient --name 'hard boiled eggs' --state boiled
```

AUSNUT ใช้สำหรับแปลงหน่วยตวงเท่านั้น `nutrition_engine.portion_conversion.convert_measure()` ต้องใช้ AUSNUT Public food key และ Measure ID ที่แน่นอน หรือรายการหน่วยที่มีเพียงรายการเดียว ไม่ใช้ Public food key เป็น USDA ID ความสัมพันธ์กับ USDA ต้องใส่ `measure_links` หลังตรวจชนิดอาหาร การทำนายหลักให้ AI คืนกรัม จึงไม่ใช้การแปลงหน่วยตวงที่กำกวม

FNDDS ใช้เป็นตารางอ้างอิงสูตรและส่วนประกอบ แยก SR code ออกจาก FDC ID เชื่อมผ่าน NDB crosswalk เท่านั้น ข้อมูลสูตรไม่ใช่ฉลากน้ำหนักจริงของภาพทดสอบ และไม่ได้เติม Hidden Ingredients ให้ทุกจานอัตโนมัติ

## ทั้งสามวิธีและการควบคุมการทดลอง

| วิธี | การทำงาน | Nominal calls ต่อภาพต่อรอบ |
|---|---|---:|
| Single | Vision LLM คืนรายการวัตถุดิบและน้ำหนัก | 1 |
| Multi-Agent | Vision → Portion → Critic แต่ละขั้นดูภาพและรับผล AI ก่อนหน้า | 3 |
| Ensemble | ทำนายอิสระ 3 ครั้ง ใช้ชื่อ/สถานะ/ID ที่จับคู่ได้ลงคะแนน 2 ใน 3 แล้วใช้ Median น้ำหนักของผู้สนับสนุน | 3 |

ค่าเริ่มต้น Ensemble เป็น **single-model self-consistency** โมเดลเดียว สุ่มแยก 3 Calls ด้วย Prompt เดียวและ Temperature > 0 ไม่เรียกว่า Multi-model หากใช้หลายโมเดลจริงให้แก้ `ensemble_mode` เป็น `multi_model` และมีอย่างน้อย 2 ID ต่างกันซึ่งรองรับ Vision ทั้งหมด

ไม่มีการปรับ Prompt/Model/กฎรวมผล/ฐานข้อมูลระหว่างรัน Freeze เก็บ Hash ของ Config, Python code, Prompt version, Database, ชุดภาพ และ Hash ฉลากที่ขั้นเตรียมข้อมูลผนึกไว้ หากสิ่งเหล่านี้เปลี่ยน ระบบหยุดให้ใช้ Run ID ใหม่ โมเดล hosted อาจเปลี่ยนภายในบริการได้แม้ ID เดิม จึงบันทึกวันที่และ Response ID และไม่รับรอง determinism ของผู้ให้บริการ

มี Equal-call control เพิ่มใน `budget_control.csv`: นำค่าที่คำนวณแล้วของสมาชิก Ensemble ทั้ง 3 มาเฉลี่ย เป็นกฎเปรียบเทียบที่กำหนดไว้ล่วงหน้าและไม่เรียกเพิ่ม ใช้เฉพาะกรณีที่สมาชิกทั้งหมดคำนวณครบ เพื่อเทียบ Ingredient vote กับการเฉลี่ย Nutrient totals ต้องเทียบชุดภาพ/รอบที่ตรงกัน และดูข้อจำกัดใน `docs\EXPERIMENT_PROTOCOL_TH.md`

## การอ่านผล

`SUCCESS` หมายถึงผลมีรูปแบบถูกต้องและคำนวณสารอาหารได้ครบ ไม่ได้หมายถึง AI ทำนายถูก

`FAILED` แยก API_ERROR, PREDICTION_ERROR, VALIDATION_ERROR, INTERNAL_ERROR `UNMATCHED` หมายถึงไม่มีข้อมูลจับคู่ `REVIEW_REQUIRED` คือมีข้อกำกวมหรือข้อมูลไม่ครบ `NOT_RUN` คือยังไม่รัน ทุกสถานะนอกจาก SUCCESS มี Error เป็น null ไม่ถูกนับเป็น Error = 0

วัด MAE/RMSE ของ kcal, protein, carbs, fat เฉพาะผลคำนวณครบ MAPE ใช้เฉพาะ Ground Truth > 0 รายงานทั้ง Available-success ของแต่ละวิธี และ Common-success ที่ทุกวิธีสำเร็จในภาพ/รอบเดียวกัน พร้อม Success Rate และ DB Coverage หาก Common-success ไม่มีรายการ จะไม่มีตัวเลขแทน

Ingredient Precision/Recall/F1 ใช้การปรับรูปคำและตัดคำสถานะที่ระบุชัดเท่านั้น ไม่ตัดชนิดสัตว์/ชิ้นส่วนออกอย่างกว้าง ๆ น้ำหนัก MAE วัดเฉพาะชื่อวัตถุดิบที่ตรงกัน ค่าฉลาก `deprecated`/`unknown` ไม่ใช้ประเมิน Ingredient identity รายงานจำนวนตัวอย่างที่ใช้ทุก Metric

SD ที่รายงานคือส่วนเบี่ยงเบนมาตรฐานของ MAE ระหว่าง 3 รอบ และไม่ใช่ความเชื่อมั่นเชิงประชากร ภาพเดียวทำซ้ำไม่ใช่ตัวอย่างอิสระ

Token/Cost ที่ไม่ทราบจะคง null และแสดงยอดที่ทราบแยกไว้ HTTP attempts รวม Retry ต่างจากจำนวนผลลัพธ์โมเดลสำเร็จ ราคา API เปลี่ยนได้ ให้เติม `api.prices` จากบัญชีของคุณพร้อมบันทึกแหล่งและวันที่ก่อนเริ่มรัน

## อาหารไทยในอนาคต

PDF ไทย 2018 ที่แนบเป็นภาพสแกน ยังไม่มีตัวเลขอาหารไทยที่ตรวจด้วยคนถูกนำเข้าสู่ฐานข้อมูลนี้ และไม่แจก PDF ต้นฉบับซ้ำใน ZIP มี `thai_verified_template.csv` และตัวนำเข้าที่บังคับ Source page, SHA256, หน่วย 100g, ผู้ตรวจ, วันที่ และสถานะ `VERIFIED`

เมื่อคุณตรวจค่าจากหน้า PDF จนครบแล้ว:

```powershell
& $NouraPython -m scripts.import_reviewed_thai --csv nutrition_database\thai_verified_template.csv --source-pdf 'C:\path\Thai-Food-Composition-2018.pdf'
```

Template เริ่มต้นมีเฉพาะ Header การรันไฟล์เปล่าจะไม่สร้างค่าขึ้นเอง หลังนำเข้าไทยต้องเริ่ม Run ID ใหม่ และเก็บข้อมูล Missing เป็นค่าว่างหากต้นฉบับไม่ได้ระบุ

## ตรวจต้นฉบับหรือสร้าง DB ใหม่

USDA ต้นฉบับและ CSV ที่นำเข้าอยู่ใน `nutrition_database\sources\` แยกจากฐานข้อมูลที่จัดรูปแบบแล้ว Source Audit พร้อมแล้ว ส่วนการตรวจ Excel เพิ่มต้องติดตั้ง openpyxl และใช้ Excel ที่คุณมี:

```powershell
& $NouraPython -m scripts.audit_sources
& $NouraPython -m pip install openpyxl
& $NouraPython -m scripts.audit_sources --xlsx 'C:\path\AUSNUT 2023 - Food measures.xlsx'
& $NouraPython -m scripts.prepare_database
```

ดูสิทธิ์และข้อจำกัดใน `docs\DATA_SOURCES_AND_RIGHTS.md` ไม่รวม API key, Dataset ภาพทั้งหมด หรือ PDF ไทยใน ZIP เก็บไฟล์อ้างอิงของคุณไว้ที่เดิม
