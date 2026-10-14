# Noura AI — Nutrition Database Integration & Controlled AI Benchmark

## บทบาทและเป้าหมาย

คุณคือ Senior AI Engineer, Data Engineer และ Research Software Engineer ที่รับผิดชอบพัฒนา **Noura AI Nutrition Analysis Experiment Workspace**

ต้องการให้พัฒนาจาก Workspace เดิมที่แนบมา ให้เป็นระบบที่ใช้งานได้จริงบน Windows PowerShell โดยเน้นการวิเคราะห์รูปภาพอาหารด้วย AI การค้นข้อมูลวัตถุดิบจากฐานข้อมูลโภชนาการ และการคำนวณค่าพลังงานและสารอาหารด้วย Python

**เป้าหมายหลักคือเปรียบเทียบประสิทธิภาพ Single LLM, Multi-Agent และ Ensemble ว่าวิธีใดประมาณ kcal, Protein, Carbs และ Fat ได้แม่นยำที่สุด เมื่อเทียบกับ Ground Truth จาก Dataset**

กรุณาลงมือสร้างและทดสอบโค้ดจริง พร้อมส่ง Workspace ZIP ที่ใช้งานต่อได้ ไม่ต้องหยุดเพียงการออกแบบหรือเขียนคำแนะนำ

---

## 1. ไฟล์ต้นฉบับที่ต้องใช้

ฉันแนบไฟล์ดังนี้

1. `Noura-AI-Nutrition5k-Pilot-Workspace.zip` — Workspace เดิม
2. `data.zip` — ฐานข้อมูล USDA และข้อมูลโภชนาการที่รวบรวมไว้
3. `Food Composition Table of Thai Foods.pdf` — ตารางคุณค่าทางโภชนาการอาหารไทย กรมอนามัย ปี 2018
4. `AUSNUT 2023 - Food measures.xlsx` — ตารางหน่วยตวงและน้ำหนักอาหาร

ใน `data.zip` มีไฟล์สำคัญ เช่น

- `nutrition.sqlite`
- `nouriva_usda_food_nutrition.csv`
- `fndds_recipe_ingredients.csv`
- `ausnut_2023_food_measures_only.csv`
- `source_manifest.json`
- `import_audit.json`
- ไฟล์ USDA FoodData Central ต้นฉบับ

ให้ตรวจสอบโครงสร้างตาราง คอลัมน์ ประเภทข้อมูล จำนวนรายการ ข้อมูลซ้ำและข้อมูลที่ขาดหายจริงก่อนนำมาใช้

ห้ามสมมติว่าแต่ละไฟล์มีข้อมูลครบโดยไม่ได้ตรวจสอบ

## 2. Dataset รูปภาพที่ใช้ทดลอง

ฉันดาวน์โหลด Dataset จาก Hugging Face เรียบร้อยแล้ว

Dataset: `mmathys/food-nutrients`

ตำแหน่งบน Windows:

`C:\Users\CHOMP2O\food-nutrients`

ภายในประกอบด้วย

- `test/` — ภาพอาหารประมาณ 3,260 ภาพ
- `metadata.jsonl` — ข้อมูล Ground Truth เช่น ส่วนประกอบ น้ำหนักและสารอาหาร
- เอกสารประกอบ Dataset

**สำคัญมาก**

- ห้ามดาวน์โหลด Dataset 1.31 GB ใหม่
- ห้ามดาวน์โหลด Nutrition5k ต้นฉบับ 181 GB
- ให้ระบบรับตำแหน่ง Dataset ผ่าน Configuration หรือ CLI
- ถ้าไม่สามารถเข้าถึงไฟล์บน Windows จาก Work ได้ ให้สร้างตัวอ่านไฟล์ที่พร้อมรันบนเครื่องฉัน และใช้ Fixture ขนาดเล็กสำหรับทดสอบโค้ด
- ไม่ต้องรวมภาพทั้งหมดไว้ใน ZIP ที่ส่งกลับ
- ตรวจชื่อ Field และหน่วยจริงจาก `metadata.jsonl` ก่อนสร้าง Data Loader
- ตรวจสอบว่า Image ID เชื่อมกับ Ground Truth ได้ถูกต้อง

## 3. หลักการทำงานของ Noura AI

ระบบต้องทำงานตาม Pipeline นี้

**Food Image → AI Image Analysis → Ingredient Recognition → Portion/Weight Estimation → Nutrition Database Lookup → Python Nutrition Calculation → Ground Truth Evaluation**

อธิบายขั้นตอน:

### ขั้นที่ 1 — วิเคราะห์ภาพอาหาร

AI รับรูปภาพอาหารและวิเคราะห์ว่า

- เป็นอาหารประเภทใด
- มีวัตถุดิบอะไรบ้าง
- วัตถุดิบอยู่ในสถานะดิบ สุก ทอด หรือต้ม หากประเมินได้
- น้ำหนักหรือปริมาณแต่ละส่วนประมาณเท่าใด
- มีน้ำมัน ซอส หรือส่วนประกอบที่อาจมองไม่เห็นหรือไม่

ต้องแยกข้อมูลที่มองเห็นจริงกับข้อมูลที่ AI คาดการณ์ โดยมีสถานะความไม่แน่นอน

### ขั้นที่ 2 — ค้นฐานข้อมูลวัตถุดิบ

นำชื่อและสถานะวัตถุดิบที่ AI วิเคราะห์ได้ ไปค้นข้อมูลจาก Nutrition Database

ตัวอย่าง:

AI ทำนาย:
- Cooked rice 150 g
- Cooked chicken 80 g
- Vegetable oil 5 g

จากนั้นระบบจะค้นค่าโภชนาการต่อ 100 g ของแต่ละวัตถุดิบ

ฐานข้อมูลที่ใช้ต้องมีชื่อวัตถุดิบ หน่วย แหล่งอ้างอิง สถานะดิบ/สุก และ kcal, Protein, Carbs, Fat

### ขั้นที่ 3 — คำนวณสารอาหาร

ให้ Python คำนวณจากฐานข้อมูล

`Nutrient = predicted_weight_g / 100 × nutrient_per_100g`

รวมผลลัพธ์ของทุกวัตถุดิบเป็นค่าโภชนาการของอาหารหนึ่งจาน

ห้ามให้ LLM สร้างค่าโภชนาการต่อ 100 กรัมขึ้นมาเองเมื่อค้นฐานข้อมูลไม่พบ

### ขั้นที่ 4 — เปรียบเทียบกับ Ground Truth

นำผลทำนายไปเทียบกับ Expected Result ที่มาจาก `metadata.jsonl`

วัดความคลาดเคลื่อนจริงของ kcal, Protein, Carbs และ Fat

**ห้ามส่ง Ground Truth รายจาน ทั้งวัตถุดิบ น้ำหนัก และค่าโภชนาการให้ AI เห็นก่อนการทำนาย** แม้ว่าฐานข้อมูลอ้างอิงโภชนาการจะใช้ร่วมกันได้ก็ตาม

---

## 4. Nutrition Database Integration

ต้องการสร้าง Nutrition Database กลางสำหรับทั้งสามวิธี AI

ใช้ฐานข้อมูลที่แนบมาเป็นหลัก และเตรียมรองรับอาหารไทยด้วย

### แหล่งข้อมูล

**USDA FoodData Central**

ใช้เป็นฐานข้อมูลวัตถุดิบหลักสำหรับการทดลอง Nutrition5k

**Thai Food Composition Table 2018**

เตรียมข้อมูลวัตถุดิบและอาหารไทยสำหรับการทดลองในอนาคต PDF เป็นเอกสารสแกน ต้องตรวจความถูกต้องของการถอดตัวเลขและหน่วย ห้ามนำค่าที่อ่านไม่ชัดมาใช้โดยอัตโนมัติ

**AUSNUT Food Measures**

ใช้ข้อมูลหน่วยตวง น้ำหนักและปริมาณอาหาร เพื่อช่วย Portion Conversion ไม่ใช่นำไปใช้เป็นตารางสารอาหารโดยตรง

**FNDDS Recipe Ingredients**

ใช้เป็นข้อมูลสนับสนุนความสัมพันธ์ของอาหารกับส่วนประกอบ ตรวจแหล่งที่มาและความเข้ากันได้ของหน่วยก่อนใช้

### ข้อกำหนดฐานข้อมูล

ต้องการ:

- SQLite เป็นฐานข้อมูลหลัก
- ใช้ชื่อภาษาไทยและภาษาอังกฤษได้
- รองรับ ingredient alias และ normalization
- แยก raw/cooked/fried/boiled อย่างชัดเจน
- มี Food ID และ Source ID
- มีค่าโภชนาการต่อ 100 g
- จัดการ null และ missing values อย่างถูกต้อง
- มีระบบ Ingredient Matching พร้อมคะแนนความมั่นใจหรือสถานะการจับคู่
- หากจับคู่ไม่ได้ ให้รายงาน `UNMATCHED` หรือ `REVIEW_REQUIRED`
- ห้ามใช้วัตถุดิบคนละชนิดแทนกันโดยไม่มีเหตุผลรองรับ
- เก็บ provenance เพื่อดูย้อนหลังว่าค่ามาจากฐานไหน
- ป้องกันรายการซ้ำระหว่างแหล่งข้อมูล
- มีรายงาน Coverage ว่าสามารถค้นวัตถุดิบจากการทำนายได้กี่เปอร์เซ็นต์
- ตรวจเงื่อนไขสิทธิ์การใช้งานและการแจกจ่ายข้อมูลต้นฉบับ

ให้แยกข้อมูลต้นฉบับออกจากฐานข้อมูลที่ผ่านการจัดรูปแบบแล้ว และหลีกเลี่ยงการกระจายไฟล์ที่มีข้อจำกัดด้านลิขสิทธิ์

---

## 5. การทดลอง AI ทั้ง 3 วิธี

ทุกวิธีต้องใช้

- ภาพอาหารชุดเดียวกัน
- Nutrition Database ชุดเดียวกัน
- Ingredient Matching Engine ตัวเดียวกัน
- Python Nutrition Calculator ตัวเดียวกัน
- Evaluation Metrics เดียวกัน

### Method A — Single LLM

ใช้ Vision LLM หนึ่งโมเดล วิเคราะห์รูปภาพและคืนค่า JSON ที่มีชื่ออาหาร รายการวัตถุดิบ สถานะอาหาร และน้ำหนักที่คาดการณ์

จากนั้นส่งข้อมูลไปยัง Shared Nutrition Engine

### Method B — Multi-Agent

แยกหน้าที่เป็น

1. Vision Agent — วิเคราะห์เมนูและวัตถุดิบ
2. Portion Estimation Agent — ตรวจและประมาณน้ำหนักแต่ละส่วนประกอบ
3. Critic Agent — ตรวจความสมเหตุสมผล ความไม่สอดคล้อง และความไม่แน่นอนของผล

หลังจากนั้นส่งผลไปยัง Shared Nutrition Engine

ต้องมีการทำงานแบบหลายขั้นตอนจริง ไม่ใช่เพียงเปลี่ยนชื่อ Prompt ให้เป็น Multi-Agent

### Method C — Ensemble

ให้มีระบบสร้างคำทำนายอิสระ 3 ชุด และรวมผลด้วยกฎที่กำหนดก่อนเริ่มทดลอง

รองรับ

- Multi-model Ensemble ถ้ามี Vision Model หลายรุ่น
- Single-model Self-consistency ถ้าใช้รุ่นเดียวทำนายหลายครั้ง

ต้องระบุชื่อวิธีอย่างถูกต้อง ไม่เรียกการทำนายซ้ำด้วยโมเดลเดียวว่า Multi-model Ensemble

การรวมผลต้องจัดการทั้งรายชื่อวัตถุดิบ การจับคู่ชื่อ และน้ำหนัก โดยใช้วิธีที่ตรวจสอบย้อนหลังได้

ทุกวิธีต้องส่งผลไปคำนวณใน Shared Nutrition Engine เหมือนกัน

---

## 6. Groq API Integration

ใช้ Groq API เป็นช่องทางเรียก AI

ต้อง:

- เลือกโมเดลที่รองรับ Vision จริงและกำหนดผ่าน Config ได้
- ไม่ Hardcode ชื่อโมเดลที่อาจเลิกให้บริการ
- อ่าน `GROQ_API_KEY` จาก `.env`
- รองรับ JSON Output
- มี Retry, Timeout และ Rate Limit Handling
- บันทึก Model ID, Prompt Version และเวลา
- บันทึก Token Usage และ Cost เมื่อคำนวณได้
- แยก API Error กับ Prediction Error
- ห้ามเก็บ API Key ลง Log หรือ ZIP

อย่าทดสอบด้วยการเรียก API ที่มีต้นทุนโดยไม่ได้รับอนุญาต ให้เตรียมระบบ Real API และทดสอบด้วย Mock ก่อน

---

## 7. การออกแบบการทดลอง

### Phase 1 — Smoke Test

- 5 ภาพ
- 3 วิธี AI
- 3 รอบ

รวม 45 การประเมิน

ใช้ตรวจว่า Pipeline ทำงานครบก่อน

### Phase 2 — Pilot Benchmark

- 30 ภาพ
- 3 วิธี AI
- 3 รอบ

รวม 270 การประเมิน

ให้เลือกภาพแบบกำหนด Seed และเก็บรายชื่อ Image ID คงที่ เพื่อให้ทุกวิธีใช้ภาพเดียวกัน

ควรเลือกภาพที่มีความหลากหลายของจำนวนวัตถุดิบ พลังงาน และลักษณะอาหาร โดยใช้ Ground Truth สำหรับจัดกลุ่มชุดทดสอบได้ แต่ห้ามเปิดเผยข้อมูลดังกล่าวให้ AI ในระหว่าง inference

ห้ามเปลี่ยน Prompt, โมเดล หรือกฎรวมผลระหว่างการทดลองจริง

ต้องรายงานจำนวนการเรียกโมเดลต่อวิธีด้วย เพราะ Multi-Agent และ Ensemble อาจใช้ทรัพยากรมากกว่า Single LLM

ถ้าเป็นไปได้ ให้มีการวิเคราะห์เพิ่มเติมโดยควบคุมงบประมาณจำนวนการเรียกโมเดล เพื่อดูว่าประสิทธิภาพที่เพิ่มขึ้นมาจากสถาปัตยกรรมหรือจำนวนการเรียกที่มากขึ้น

---

## 8. Evaluation Metrics

### Primary Metrics

- Calories MAE (kcal)
- Protein MAE (g)
- Carbs MAE (g)
- Fat MAE (g)

### Secondary Metrics

- RMSE
- MAPE เฉพาะรายการที่ค่าอ้างอิงมากกว่า 0
- Ingredient Precision, Recall และ F1 เมื่อมีรายการส่วนประกอบอ้างอิง
- Ingredient Weight MAE สำหรับรายการที่จับคู่ได้
- Success Rate
- Database Match Coverage
- Latency
- Token Usage
- Estimated API Cost

ให้รายงานแยกแต่ละวิธีและแต่ละรอบ รวมถึงค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐานตามความเหมาะสม

ต้องบันทึกผล `FAILED`, `UNMATCHED`, `REVIEW_REQUIRED` และ `NOT_RUN` แยกกัน ห้ามนำมาเป็น error = 0

หากผลคำนวณมีวัตถุดิบที่จับคู่ไม่ได้ ต้องแสดง Coverage และไม่อ้างว่าค่าสารอาหารครบถ้วน

---

## 9. โครงสร้าง Workspace

ต้องการโครงสร้างประมาณนี้ โดยปรับให้เหมาะกับโค้ดเดิมได้

```text
Noura-AI-Nutrition-Benchmark/
│
├── config/
│   ├── experiment.yaml
│   ├── models.yaml
│   └── database.yaml
│
├── data/
│   ├── external_dataset/
│   ├── selected_images.csv
│   └── ground_truth/
│
├── nutrition_database/
│   ├── sources/
│   ├── normalized/
│   ├── ingredients.sqlite
│   ├── aliases.csv
│   └── database_audit.csv
│
├── methods/
│   ├── single_llm.py
│   ├── multi_agent.py
│   └── ensemble.py
│
├── nutrition_engine/
│   ├── ingredient_matcher.py
│   ├── nutrition_lookup.py
│   ├── portion_conversion.py
│   └── calculator.py
│
├── evaluation/
│   ├── metrics.py
│   ├── evaluate.py
│   └── compare.py
│
├── scripts/
│   ├── prepare_database.py
│   ├── prepare_dataset.py
│   ├── check_setup.py
│   └── run_experiment.py
│
├── tests/
├── results/
├── docs/
├── .env.example
├── requirements.txt
├── START_HERE.ps1
└── README.md
```

อย่ารื้อ Workspace เดิมโดยไม่จำเป็น ให้ตรวจและนำส่วนที่ทำงานถูกต้องกลับมาใช้

---

## 10. การตรวจสอบก่อนส่งมอบ

ต้องทำ Unit Tests และ Integration Tests โดยใช้ข้อมูลจำลองที่แยกจากผลการทดลองจริง

ตรวจสอบอย่างน้อย:

- อ่าน Metadata JSONL ได้
- จับคู่ Image ID กับไฟล์ภาพถูกต้อง
- ไม่ส่ง Ground Truth เข้า AI
- ตรวจข้อมูลผิดรูปแบบได้
- ค้นวัตถุดิบจาก SQLite ได้
- คำนวณสารอาหารถูกต้องเมื่อทราบน้ำหนักและค่าอ้างอิง
- ไม่ใช้วัตถุดิบที่จับคู่ไม่ได้แทนโดยพลการ
- Multi-Agent ทำงานแยกขั้นตอนจริง
- Ensemble รวมผลได้ตามกฎ
- ทั้งสามวิธีใช้ Calculator เดียวกัน
- บันทึกผล 3 รอบได้
- คำนวณ Metrics ถูกต้อง
- รันบน Windows PowerShell ได้

หากยังไม่ได้ทดสอบกับ Groq API จริง ต้องระบุให้ชัดว่า `MOCK TEST PASSED / REAL API NOT VERIFIED`

ห้ามสร้างผล MAE จำลองแล้วรายงานว่าเป็นผลทดลองจริง

---

## 11. สิ่งที่ต้องส่งมอบ

1. Workspace ZIP เวอร์ชันใหม่ที่พร้อมใช้งาน
2. Database SQLite ที่ผ่านการจัดเตรียมและตรวจสอบแล้วเท่าที่ข้อมูลอนุญาต
3. Data Audit Report — จำนวนข้อมูล แหล่งข้อมูล รายการซ้ำและข้อมูลที่ขาด
4. Database Coverage Report
5. ตัวอ่าน Dataset `food-nutrients` ที่ใช้โฟลเดอร์บนเครื่องฉันได้
6. Single LLM, Multi-Agent และ Ensemble ที่เชื่อม Nutrition Engine เดียวกัน
7. Evaluation System สำหรับทดลอง 3 รอบ
8. CSV และ JSON Template สำหรับบันทึกผลทดลองจริง
9. README ภาษาไทย
10. คำสั่ง PowerShell ตั้งแต่ติดตั้งจนรันทดสอบ
11. Test Results และรายการข้อจำกัดที่ยังต้องแก้

## 12. เงื่อนไขสำคัญ

- ห้ามดาวน์โหลด Dataset ใหญ่ซ้ำ
- ห้ามสร้าง Ground Truth เอง
- ห้ามนำผลของ AI มาเป็น Expected Result
- ห้ามให้ AI เดาค่าสารอาหารที่ต้องมาจากฐานข้อมูล
- ห้ามนำข้อมูลที่ไม่มีหลักฐานอ้างอิงมาปะปนกับข้อมูลที่ตรวจสอบแล้ว
- ห้ามใช้ค่า Missing เป็น 0 โดยไม่มีเหตุผล
- ห้ามรวมข้อมูลหน่วยดิบ/สุกที่ไม่สอดคล้องกัน
- ห้ามแก้สถาปัตยกรรมส่วนที่ดีอยู่แล้วโดยไม่จำเป็น
- ต้องใช้ฐานข้อมูลและสูตรเดียวกันทั้งสามวิธี
- ต้องสามารถตรวจสอบย้อนกลับได้ทุกค่าที่คำนวณ
- ต้องแยก Mock Results ออกจาก Real Experiment Results
- ต้องออกแบบให้รองรับการเพิ่ม Dataset อาหารไทยในอนาคต

## 13. ลำดับการทำงานที่ต้องการ

ดำเนินการตามลำดับ:

1. ตรวจไฟล์แนบและโค้ดเดิมเฉพาะส่วนที่เกี่ยวข้อง
2. ตรวจฐานข้อมูลและทำ Data Audit
3. สร้างหรือปรับ Nutrition Database กลาง
4. พัฒนา Nutrition Lookup และ Calculator
5. เชื่อม Dataset Loader กับ `food-nutrients`
6. ปรับ Single LLM, Multi-Agent และ Ensemble
7. สร้าง Evaluation Pipeline
8. รัน Unit/Integration/Mock Tests
9. ตรวจความถูกต้องและแก้ปัญหาที่พบ
10. ส่ง ZIP พร้อมคู่มือใช้งานและรายงานสิ่งที่ผ่าน/ไม่ผ่าน

**เป้าหมายสุดท้าย:** เมื่อฉันแตกไฟล์ ZIP บนเครื่อง Windows ตั้งค่า Dataset Path และ Groq API Key แล้ว ต้องสามารถรันการทดลอง Single LLM, Multi-Agent และ Ensemble และรับผลเปรียบเทียบความแม่นยำของ kcal, Protein, Carbs และ Fat ได้โดยไม่ต้องเขียนโค้ดเพิ่ม

ให้เริ่มลงมือพัฒนาจริงทันที โดยถามเฉพาะกรณีที่มีข้อมูลจำเป็นซึ่งไม่สามารถดำเนินการต่อได้เท่านั้น
