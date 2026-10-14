# ข้อตกลงการทดลองและการอ่านผล

## สิ่งที่วัด

วัดความคลาดเคลื่อนของการประมาณน้ำหนัก/ส่วนประกอบจากภาพ แล้วนำไปคำนวณด้วย USDA เทียบกับ labels ของ food-nutrients ผลจึงรวมความคลาดเคลื่อนจากการรู้จำภาพ การประมาณปริมาณ การจับคู่ฐานข้อมูล และความแตกต่างระหว่างฐาน USDA กับสูตร/ฐานอ้างอิงของ labels ไม่ใช่การวัด Vision recognition ล้วน ๆ

ภาพเดิม ฐานข้อมูลเดิม Matcher เดิม Calculator เดิม และ Evaluation เดิมใช้ทั้งสามวิธี ค่าเริ่มต้น Single และ Multi ใช้โมเดลเดียวกับสมาชิก Self-consistency เพื่อคุมความต่างของโมเดล แต่ใช้จำนวน Calls ต่างกัน

| Phase | ภาพ | วิธี | รอบ | การประเมิน | Nominal model calls รวม |
|---|---:|---:|---:|---:|---:|
| Smoke | 5 | 3 | 3 | 45 | 105 |
| Pilot | 30 | 3 | 3 | 270 | 630 |

จำนวนข้างต้นสมมติทุกขั้นทำครบ Single 1 call, Multi 3 calls, Ensemble 3 calls ต่อภาพต่อรอบ หากขั้นกลางล้มเหลว อาจใช้ Calls น้อยลง Retry ทำให้ HTTP attempts มากขึ้น ต้องอ่านจำนวนจริงจาก log

## กฎก่อนเริ่มจริง

เลือกภาพด้วย Seed 20261013 และผนึกรายการ ID กับ Hash ภาพไว้ การจัดกลุ่มใช้ energy quartile และ ingredient count ไม่ส่งข้อมูลเหล่านี้ให้ API หนึ่งตัวแทนต่อ signature ของ ingredient/gram ช่วยลดหลายเฟรมของจานเดิม แต่ไม่สามารถรับรองว่าอาหารคล้ายกันทุกกรณีถูกตัดออก

ล็อก Config, Source priority, Alias, Code, Prompt version, Database และรูปภาพต่อ Run ID ห้ามเลือกรายการ Alias โดยดูฉลากของจานที่จะทดสอบ หากปรับจาก Smoke เพื่อเตรียม Pilot ให้บันทึกการปรับแล้วเริ่ม Pilot ใหม่ครบทุกวิธีด้วยชุดล็อกเดียวกัน ไม่มีการแก้เฉพาะ Method ที่ผลไม่ดี

ทำนายโดยใช้ภาพเท่านั้น Multi ได้ผล AI ก่อนหน้า ส่วน Ensemble ทุกสมาชิกไม่เห็นผลของกันและกัน Reference nutrients มาจาก SQLite หลังทำนาย ไม่มาจาก Ground Truth หรือจากการแต่งค่าของ LLM

## Ensemble

สมาชิก 3 คนใช้ Prompt เดียวกัน คืนชื่อ สถานะ น้ำหนัก และความไม่แน่นอน อัตลักษณ์ชื่อใช้ Food ID หาก Matcher จับคู่ได้อย่างชัดเจน มิฉะนั้นใช้การปรับรูปคำและสถานะ แยก raw/cooked/boiled/fried คนละเสียง ผู้สนับสนุนต้องมาจากคนละสมาชิกอย่างน้อย 2 คน ไม่เติมน้ำหนัก 0 ให้สมาชิกที่ไม่มีวัตถุดิบนั้น น้ำหนักสุดท้ายเป็น Median ของสมาชิกที่มีวัตถุดิบ มี Trace บอกทั้งสิ่งที่เก็บและตัดออก ตรวจ schema/น้ำหนักรวมอีกครั้งก่อนคำนวณ

โมเดลเดียว 3 ครั้งเรียกว่า Single-model Self-consistency หลาย ID เรียกว่า Multi-model Ensemble และผลของการเปลี่ยน Model family เป็นส่วนหนึ่งของความแตกต่างนั้น

## สถานะและ Coverage

`SUCCESS` เป็น Operational success ว่าคำนวณครบ ไม่ใช่ Prediction correctness Missing ไม่เท่ากับศูนย์ Partial totals อยู่ใน `partial_nutrients` ไม่มี full `nutrients` และไม่ใช้คำนวณ Primary error

รายงาน Ingredient-row Match Coverage, Complete Nutrient Coverage และ Mass Match Coverage ค่าทั้งหมดนี้ไม่รับรองว่า AI เห็นวัตถุดิบครบ ต้องดู Ingredient recall แยก ระบบไม่เพิ่ม confidence สูงเพราะพบชื่อใน DB

`FAILED` แยก API, prediction/schema, validation และ internal error หากหยุดกลางคัน เก็บ Request events ที่เกิดขึ้นแล้ว รวมถึง event ที่ไม่ทราบว่าผู้ให้บริการคิดเงินจริงหรือยัง `--retry-failed` เก็บประวัติและรวมยอดเดิม ถ้าทั้ง process ถูก kill ไฟล์ checkpoint ล่าสุดยังคงอยู่และ Trial เป็น FAILED/IN_PROGRESS ไม่สรุปว่าการใช้ทรัพยากรเป็นศูนย์

## Metrics

MAE = mean(abs(predicted - reference)) และ RMSE = sqrt(mean(error²)) ใช้ Unit kcal/g ตามคอลัมน์ MAPE ใช้เฉพาะ reference > 0 โดยรายงานจำนวนที่เข้าตัวหาร

Available-success ของแต่ละวิธีอาจเป็นคนละภาพ/รอบ Common-success ใช้ intersection ที่ทุกวิธีสำเร็จ ให้เทียบความแม่นยำ Common-success พร้อม Success Rate และ Failure count ของชุดเต็ม หาก Common-success เป็นศูนย์ ไม่มีหลักฐานจัดอันดับด้วย MAE

Ingredient identity metrics ใช้ normalized spelling และตัดคำ preparation ที่ระบุชัดออก ไม่ยุบทุกชื่อไก่/ปลาให้เหมือนกัน ไม่มี fuzzy semantic matching อิสระ ฉลากชื่อไม่ละเอียด เช่น `chicken` กับ prediction `chicken breast` อาจนับไม่ตรงกันทั้งที่ภาพดูคล้าย จึงต้องรายงานข้อจำกัดนี้ ชื่อ `deprecated`/`unknown` ไม่ใช้ identity scores ส่วน Macro errors ยังประเมินได้

Weight MAE ใช้เฉพาะ identity ที่ชื่อจับคู่กัน ไม่มีการตีน้ำหนักของวัตถุดิบที่พลาดเป็นศูนย์ ตัวหาร matched_identity_count ถูกบันทึก

รายงาน Mean และ sample SD ของ Round MAE ระหว่าง 3 รอบ ซึ่งเป็นความแปรปรวนของการรันซ้ำในชุดเดียว ไม่ใช่ confidence interval ของอาหารทุกประเภท อาหาร 5/30 จานเป็น Pilot และไม่แสดงความแม่นยำของอาหารไทย

## งบประมาณเท่ากัน

`budget_control.csv` เปรียบเทียบกฎ 2/3 Ingredient vote กับการเฉลี่ยค่าที่คำนวณจากสมาชิกอิสระ 3 คน ค่าเฉลี่ยนี้ใช้ DB/Calculator ตัวเดียวกัน กำหนดกฎไว้ก่อนรัน และใช้ Calls เดียวกับ Ensemble ไม่เรียกเพิ่ม ต้องมีครบ 3 สมาชิกที่คำนวณสารอาหารได้ ไม่มีการใช้ Partial หรือ NULL เติม 0

เมื่อ default ใช้โมเดลเดียวทั้งหมด ผลนี้ช่วยดูผลของกฎรวมผลภายใต้ 3 Calls เท่ากัน ไม่สามารถแยกว่าประโยชน์ทั้งหมดมาจาก Multi-Agent architecture ถ้าจะเทียบกับ Multi ให้ใช้ dish/round intersection ระหว่าง Multi SUCCESS, Ensemble SUCCESS และ control ที่มีค่า วิธี Single ยังคงใช้ 1 Call ให้รายงานต้นทุนต่อภาพและอย่าตีความการใช้ 3 Calls เป็นเงื่อนไขเดียวกับ 1 Call

## ข้อจำกัดจากผู้ให้บริการ

Temperature sampling, provider model revisions และ nondeterministic serving ทำให้ Seed คัดภาพไม่ได้ควบคุมคำตอบ AI แบบ bitwise บันทึก Model ID, Prompt version, วันที่, Response ID และ usage เท่าที่ผู้ให้บริการคืน ไม่มีการคิดราคาเมื่อ Config ยังไม่มีราคา และยอด unknown usage ไม่ถูกอ้างว่าเป็น 0
