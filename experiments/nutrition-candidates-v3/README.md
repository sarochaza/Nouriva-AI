# Noura · Nutrition Agent Candidates v3

**พร้อมทดลองจากภาพ: Single Agent เทียบกับ Ensemble 2 ตัว เพื่อเลือก candidate เป็น Agent โภชนาการ**

ใช้ฐานข้อมูล `nutrition_database/ingredients.sqlite` จาก ZIP ที่แนบมาโดยตรง: **13,661 รายการ**, reviewed aliases **46 รายการ** พร้อมข้อมูลที่ใช้รันและ metadata แหล่งที่มา ตรวจ checksum ตรงกับต้นฉบับ ดู `docs/DATABASE_ORIGIN_V3.json`

ขั้นตอน: **ภาพ → AI ระบุวัตถุดิบ/กรัม → ดึงค่าฐานข้อมูล → เติมค่าที่ขาดด้วย AI ประมาณ → คำนวณต่อจาน → เทียบ Expected Result**

## เริ่มบน Windows

ต้องมี **Python 3.10+**; workflow ใช้ standard library ไม่ต้องติดตั้ง PostgreSQL, Docker หรือ packages เพิ่มสำหรับการทดลองนี้

1. แตก ZIP และเปิด PowerShell ในโฟลเดอร์ `Noura-Nutrition-Agent-Candidates-v3`
2. ตรวจ workflow แบบจำลองก่อน:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Mock
```

ดับเบิลคลิก `START_MOCK.cmd` ได้เช่นกัน MOCK ไม่เรียก API และ **ไม่ใช้ตัดสินความแม่นยำหรือเลือก Agent**

3. เปิด `.env` ที่ script สร้าง แล้วใส่ key ของตัวเอง:

```dotenv
GROQ_API_KEY=YOUR_KEY_HERE
```

4. ทดลองจริง **5 ภาพ × 3 รอบ** จากชุดที่โหลดไว้บนเครื่อง:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Smoke -DatasetPath "C:\Users\CHOMP2O\food-nutrients" -RunId candidate-smoke-v3
```

เปลี่ยน DatasetPath ให้ตรงเครื่องเธอ **รูปจริงและ Expected Result ไม่ได้แนบใน ZIP นี้** โปรแกรมอ่านชุดข้อมูลบนเครื่องโดยตรง ไม่ดาวน์โหลดใหม่

5. เมื่อ smoke ใช้งานได้ ทดลอง **30 ภาพ × 3 รอบ**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Pilot -DatasetPath "C:\Users\CHOMP2O\food-nutrients" -RunId candidate-pilot-v3
```

เปิดผลด้วยดับเบิลคลิก `results/real/<RunId>/comparison/report.html`

## Single กับ Ensemble 2

| รายการ | Single | Ensemble 2 |
|---|---|---|
| วิเคราะห์ต่อภาพ/รอบ | 1 response | 2 responses ที่วิเคราะห์อิสระ |
| Input | ภาพ + prompt เดียวกัน + catalog ชื่อขนาดเล็ก | เหมือน Single; ไม่เห็นคำตอบกัน |
| สูตร | DB-first + AI fallback | ใช้สูตรเดียวกันในแต่ละตัว |
| ผลสุดท้าย | ผลคำนวณจากตัวเดียว | เฉลี่ย nutrient contributions ของสองตัวด้วยโค้ด |
| วัตถุดิบพบตัวเดียว | ใช้กรัมที่ตอบ | รวมใน union; กรัมเฉลี่ยกับ 0g ของตัวที่ไม่พบ |
| สมาชิกหนึ่งล้มเหลว | Trial FAILED | Trial FAILED ทั้งคู่ ไม่ลดเหลือ Single |
| Calls รวม 5 ภาพ × 3 รอบ | 15 | 30 |
| Calls รวม 30 ภาพ × 3 รอบ | 90 | 180 |

Smoke รวม **45 calls**, Pilot รวม **270 calls** ก่อน retries; Ensemble ใช้ call รวมมากกว่า จึงต้องอ่านความแม่นยำพร้อมเวลา/tokens/calls และไม่สรุปว่าผลต่างเกิดจากสถาปัตยกรรมเพียงอย่างเดียว

ค่าเริ่มต้นใน `config/candidate.json` ใช้ `qwen/qwen3.8-27b` ทั้งสาม response: Single 1 ครั้ง; Ensemble รุ่นเดียวกัน 2 ครั้งอย่างอิสระที่ temperature 0.7 เรียกว่า **two-sample self-consistency** เอกสาร Groq ระบุการรองรับภาพ/JSON mode ที่ https://console.groq.com/docs/vision (ตรวจ 2026-10-14)

ถ้ามีสองรุ่นใน Groq ที่ตรวจแล้วว่ารองรับภาพจริง ให้ตั้ง `ensemble_mode` เป็น `multi_model`, ใส่สอง model IDs ต่างกันใน `ensemble_models` และเพิ่มทั้งคู่ใน `vision_confirmed_models` แล้วใช้ RunId ใหม่ การมีชื่อใน `/models` อย่างเดียวไม่ยืนยัน vision support

## ฐานข้อมูลก่อน; AI ประมาณเมื่อขาด

รองรับ **kcal, protein_g, carbs_g, fat_g**; ชุดนี้ยังไม่ประเมินโซเดียม น้ำตาล หรือสารอาหารรอง

AI ส่งชื่อ การปรุง กรัม และค่าประมาณต่อ 100g มาพร้อมกัน ค่าประมาณเป็น fallback จึงไม่ต้องเรียก Agent เพิ่ม

| เงื่อนไขรายสารอาหาร | ใช้ค่า | ป้าย |
|---|---|---|
| Exact match / reviewed alias + มีค่าที่ต้องการ | ค่าฐานข้อมูล | `DATABASE` |
| ชื่อไม่ตรง, สภาพไม่ตรง, กำกวม หรือ nutrient ใน DB เป็น null | ค่าประมาณจาก Agent | `AI_ESTIMATE` |
| DB และ Agent ไม่มีค่า | null; คำนวณไม่ครบ | `MISSING`, trial `INCOMPLETE` |

สูตรร่วม: `contribution = กรัมที่ AI คาด / 100 × ค่าต่อ 100g` แล้วรวมทั้งจาน

ตัวอย่าง ข้าวสุก 150g × 130kcal/100g = 195kcal; ซอส 20g หาไม่พบและ AI ประมาณ 100kcal/100g = 20kcal รวม 215kcal โดยซอสติดป้าย `AI_ESTIMATE`

ไม่แทน null ด้วยศูนย์; DB ที่มีค่า 0 จริงยังใช้ 0; ไม่เขียน AI estimates เข้า DB และไม่ใช้รายการที่เพียงชื่อคล้ายแทนโดยอัตโนมัติ เมื่อชื่อกับ state ขัดกันจะ fallback อย่างเปิดเผย

JSON เก็บ food/source ID, match reason, per_100g, nutrient source ราย field, contribution, uncertainty และสมาชิก Ensemble ทั้งสอง

## ชุดภาพและ Expected Result บนเครื่อง

รองรับรูปแบบที่เคยใช้กับ `mmathys/food-nutrients`:

```text
food-nutrients/
  metadata.jsonl
  test/
    dish_0001.png
    dish_0002.png
```

หรือ `test/metadata.jsonl` ที่อ้างรูปในโฟลเดอร์เดียวกัน `file_name` เป็น path สัมพันธ์กับโฟลเดอร์ของ metadata ใช้ `/`; `id` เป็นข้อความตรงกับชื่อภาพที่ไม่มีนามสกุล

Fields: `file_name`, `id`, `ingredients`, `total_calories`, `total_mass`, `total_fat`, `total_carb`, `total_protein`; ingredients แต่ละรายการมี `name`, `grams` หน่วย kcal และ g ดู `config/metadata_schema.json`

ถ้า metadata อยู่ที่อื่น/ชื่อ fields ต่างกัน:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Smoke -DatasetPath "D:\food-nutrients" -MetadataPath "D:\food-nutrients\test\metadata.jsonl" -SchemaPath "config\metadata_schema.json" -PreparedPath "data\prepared\custom-v3" -RunId custom-v3
```

เมื่อมีปัญหา ดู `data/prepared/.../dataset_audit.json` ที่ระบุแถวและเหตุผล ไม่สร้าง Expected Result จาก AI หรือเปลี่ยนหน่วยเงียบ ๆ

การเตรียมชุดข้อมูลแยก `manifest.json` (ID/path/hash สำหรับ inference) ออกจาก `ground_truth.json` (Expected Result สำหรับ evaluator) และเก็บ `truth_integrity.json` ป้องกันเปลี่ยน labels การเลือกภาพคงที่ด้วย seed และลดเฟรมซ้ำโดยจัดกลุ่มตาม ingredient labels/weights ใน metadata; ตรวจ `selection_audit.json` สำหรับข้อจำกัด

Agent ไม่เห็นค่าจริง น้ำหนักจริง ชื่อไฟล์ หรือคำตอบสมาชิกอื่น การแบ่ง strata ใช้ labels ก่อน inference ได้ แต่ไม่ส่ง labels เข้า prompt

## ไฟล์ผลและการเลือกผู้ชนะ

| ไฟล์ใน comparison/ | หน้าที่ |
|---|---|
| `report.html` / `report.md` | สรุปภาษาไทยและสถานะเลือก candidate |
| `per_evaluation.csv` | prediction เทียบ expected พร้อม error รายภาพ/รอบ |
| `summary_by_method_round.csv` | MAE/RMSE/MAPE/F1 แยกรอบและ cohort |
| `ingredient_breakdown.csv` | วัตถุดิบ กรัม สัดส่วน ที่มาของค่า และ contribution |
| `winner_selection.json` | เกณฑ์เลือก, selected method, config สำหรับ Agent |

`records/round_*/` เก็บผลดิบและ API metadata; `frozen.json` เก็บ config/database/code/selection hash

สารอาหารใช้ **คู่ภาพ/รอบที่ทั้งสองวิธีคำนวณครบ** พร้อม completion/failure rates; FAILED/INCOMPLETE/NOT_RUN ไม่ใช่ error=0 แยกคู่ที่ทั้งสองเป็น DB-only กับคู่ที่มี AI estimate ใน CSV ด้วย

การระบุวัตถุดิบวัด Precision/Recall/F1; ปริมาณวัดทั้ง matched weight MAE, union weight MAE ที่ลงโทษหาย/เกิน, และสัดส่วน L1 percentage points ชื่อใช้ normalization/synonym จำกัด จึงควรตรวจชื่อทั่วไปกับชื่อเฉพาะก่อนตีความ F1

เกณฑ์เลือกลงทะเบียนไว้ก่อนรัน: ใช้ error สารอาหารทั้งสี่เฉลี่ยหลังหาร scale `max(expected, 50kcal/5g/5g/5g)`; ต้องมีอย่างน้อย 5 จาน, 3 รอบ, แต่ละวิธีครบ ≥90%, จานที่ทั้งคู่ครบทุก 3 รอบ ≥80% และอย่างน้อย 5 จาน, error ดีขึ้น ≥5%, paired-dish bootstrap 95% CI ไม่คร่อมศูนย์ Bootstrap ใช้ **จานหลังเฉลี่ย 3 รอบ** ไม่ถือว่าภาพเดิมสามรอบเป็นสามภาพอิสระ

ผ่าน: `SELECTED_FOR_PILOT` และ selected method; ยังต้องยืนยันกับภาพชุดใหม่ ไม่ผ่าน: `INSUFFICIENT_DATA` หรือ `NO_CLEAR_WINNER`; MOCK: `MOCK_NOT_ELIGIBLE` ไม่มีการเลือก Agent

## ใช้ผู้ชนะกับภาพใหม่

เมื่อได้ `SELECTED_FOR_PILOT`:

```powershell
.\.venv\Scripts\python.exe -m candidate.analyze --selection "results\real\candidate-pilot-v3\comparison\winner_selection.json" --image "D:\food-images\new-meal.jpg" --out "results\new-meal-analysis.json"
```

หรือใช้ `START_HERE.ps1 -Mode Analyze -RunId candidate-pilot-v3 -ImagePath "D:\food-images\new-meal.jpg"` คำสั่งนี้ใช้วิธี/config/DB/calculator เดียวกับผลที่เลือก ไม่มี Ground Truth สำหรับภาพใหม่ ถ้า DB, prompt หรือโค้ดที่ตรึงไว้เปลี่ยนจะปฏิเสธและให้ทดลองใหม่

## รันต่อและตรวจ setup

รันคำสั่งเดิมซ้ำเพื่อข้าม trial ที่เสร็จแล้ว เพิ่ม `-RetryFailed` เมื่อจะ retry FAILED/INCOMPLETE; attempt history/tokens/time เก็บสะสม เปลี่ยนโมเดล/prompt/โค้ด/DB ให้ใช้ **RunId ใหม่** เปลี่ยน dataset/schema/seed ให้ใช้ **PreparedPath ใหม่** ด้วย

ประเมินอย่างเดียว ไม่เรียก API:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1 -Mode Evaluate -RunId candidate-pilot-v3 -PreparedPath "data\prepared\pilot-v3"
```

ตรวจ local setup: `.\.venv\Scripts\python.exe -m candidate.check`

ดู model IDs ผ่าน API: `.\.venv\Scripts\python.exe -m candidate.check --list-models`

ลองภาพจริงหนึ่ง call: `.\.venv\Scripts\python.exe -m candidate.check --probe-image "D:\food-images\meal.jpg"`

429/quota หมด: หยุดและรันต่อภายหลัง; retry wait ไม่เกิน 60 วินาที ไม่มี key แนบมา ค่าใช้จ่ายเป็น null จนตั้งราคาที่ตรวจแล้วใน `api.prices` ไม่รับประกัน quota ฟรี/ราคา API ปัจจุบัน

## WSL/Linux

จากโฟลเดอร์ workspace และ Python 3.10+:

```bash
python3 -m candidate.check
python3 -m candidate.prepare --dataset-root /path/to/food-nutrients --count 5 --out data/prepared/smoke-v3
python3 -m candidate.run --mode real --prepared data/prepared/smoke-v3 --run-id candidate-smoke-v3
python3 -m candidate.evaluate --run-dir results/real/candidate-smoke-v3 --truth data/prepared/smoke-v3/ground_truth.json
```

## โครงสร้างและข้อจำกัด

`candidate/` และ `config/candidate.json` เป็น workflow v3 ที่ใช้จริง ส่วน `methods/`, `scripts/run_experiment.py`, `evaluation/evaluate.py`, config YAML และ `docs/legacy-v2/` เป็น v2 สำหรับอ้างอิง/regression; root scripts รัน v3 เท่านั้น

`nutrition_database/sources/` เป็นข้อมูลต้นทางเดิม; `nutrition_engine/ingredient_matcher.py` ตัวจับคู่ร่วม; `src/dataset.py` loader; `tests/` รวม regression และ tests v3

ดูผลตรวจจริงที่ `docs/VERIFICATION_V3.md` และตัวอย่างที่ `examples/mock-report/` **ยังไม่ได้ทดสอบ API จริงหรือวัด accuracy อาหารจริงในแพ็กนี้** ค่าจากภาพและ fallback เป็นการประมาณ; การทดลองนี้ครอบคลุมการระบุวัตถุดิบ/โภชนาการ ไม่รวมคำแนะนำรายโรคหรือเป้าหมายรายวัน

## ZIP repair 2026-10-14

This compact repair package includes the identical full ingredients.sqlite, aliases, derived CSV sources, code, tests and reports. The three original USDA source ZIP archives are omitted to reduce the transfer size; they remain in the original user-supplied Noura-AI-Nutrition-Benchmark-v2(1).zip. This does not reduce database records or change inference code. Raw archive reconciliation can be rerun by copying those three ZIPs into nutrition_database/sources/.
