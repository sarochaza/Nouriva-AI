# รายงานตรวจข้อมูล Noura AI

ตรวจวันที่ 13 ตุลาคม 2026 จากไฟล์จริงที่แนบ ไม่ใช้จำนวนในรายงานเดิมเป็นหลักฐานเพียงอย่างเดียว

## ฐานสารอาหาร USDA

|Source/release|รายการ|Core ครบหลังคัดค่าผิดเงื่อนไข|Missing kcal|Missing protein|Missing carbs|Missing fat|
|---|---:|---:|---:|---:|---:|---:|
|FNDDS:2021-2023|5432|5431|1|1|1|1|
|Foundation:2025-12|436|366|59|12|70|24|
|SR_Legacy:2018-04|7793|7793|0|0|0|0|

รวม 13,661 รายการ Core ครบ 13,590 รายการ ขาด/ถูกคัดออกอย่างน้อยหนึ่งค่า 71 รายการ

Original CSV และ SQLite มีค่า kcal/protein/carbs/fat ตรงกันทุก ID ที่ตรวจ Original SQLite มี TEXT source/release/ID/name/state และ REAL nutrient fields พร้อม FTS index ข้อมูล CSV เป็นข้อความก่อน cast; หลัง normalize เก็บ SQLite REAL และ null อย่างชัดเจน

ตรวจต้นฉบับ USDA ZIP โดยอ่าน food.csv, food_nutrient.csv และ nutrient.csv ได้ดังนี้:

|Source|Raw food rows|Raw food_nutrient rows|Curated food rows|Nutrient ID domain|
|---|---:|---:|---:|---|
|Foundation|78,026|159,285|436|fdc_nutrient_id|
|SR_Legacy|7,793|644,125|7,793|fdc_nutrient_id|
|FNDDS|5,432|353,015|5,432|legacy_nutrient_number|

ตรวจค่าที่มีอยู่ 54,485 ค่า ตรงต้นฉบับภายใน tolerance relative 1e-7 / absolute 1e-6 ไม่มี substantive mismatch มี 98 ค่าที่ต่างเพียงความละเอียดการแสดงเลข บันทึกแยกไว้ใน JSON

FNDDS archive ใช้เลข legacy nutrient number 203/204/205/208 ภายใต้ชื่อคอลัมน์ nutrient_id จึงต้อง join กับ nutrient_nbr ใน nutrient dictionary ไม่สมมติว่าเป็น FDC nutrient ID 1003/1004/1005/1008 ทั้งหมด Foundation energy ใช้ค่าตาม energy_method 1008, 2047 หรือ 2048 และตรวจ unit G/KCAL จริง

## ค่าที่ผิดเงื่อนไขและรายการซ้ำ

พบคาร์โบไฮเดรตติดลบ 10 ค่าใน Foundation เก็บในต้นฉบับและ provenance แต่ normalized DB เป็น null ไม่ clamp เป็น 0

Duplicate source ID ใน CSV ที่ถูกยุบ: 0 รายการ กลุ่มชื่อ normalize และสถานะซ้ำ: 223 กลุ่ม เก็บรายการคนละ Source แยกกัน ไม่บวกหรือเฉลี่ย nutrient values เพื่อทำเป็นแถวใหม่ Source priority ใช้เฉพาะชื่อและสถานะเหมือนกันทุกประการและถูกล็อกก่อนทดลอง

สถานะอาหารจัดใหม่จาก description แทนค่าสถานะเดิมที่ติด cooked ให้หลายวิธีปรุง แยก fried/boiled/roasted/steamed/grilled/baked/dried และ unspecified ไม่ตี cooked, dry heat เป็น dried และไม่ตี oil for frying เป็น fried

## AUSNUT และ FNDDS recipe

AUSNUT 9,816 measures, 3,713 Public food keys ตรวจกับ Excel ที่แนบครบทั้ง quantity/gram/volume/identity ไม่มี mismatch ไม่มี nutrient columns ไม่ใช้เป็นสารอาหาร

FNDDS recipe 18,584 แถว, 5,431 recipe IDs units ที่พบจริง: GM=14,137, C=1,105, FO=160, [blank]=1,125, TB=664, TS=897, PT=2, LB=250, WO=126, CP=117, QT=1

NDB crosswalk เชื่อม ingredient food ID ได้ 14,079 แถว ที่เหลือ 4,505 แถวไม่เชื่อมอัตโนมัติ amount และ gram_weight ไม่มี null แต่ unit บางแถวว่าง จึงไม่ใช้ amount โดยเดาหน่วยหรือใช้แทนปริมาณภาพ

## PDF ไทยและสิทธิ์

PDF Thai FCT September 2018 มี 148 หน้า เป็นภาพสแกน ไม่พบข้อความตารางที่ดึงได้แบบเชื่อถือได้ จึงนำเข้าตัวเลขไทย 0 แถว มี blank verified-row template และนำเข้าได้หลังตรวจ Source page/hash/100g/reviewer เท่านั้น ไม่รวม PDF ต้นฉบับใน ZIP

Hash ของ USDA originals ทั้ง 3 และ Excel ที่แนบตรงกับ source_manifest ที่ได้รับทั้งหมด สิทธิ์ USDA CC0 และ FSANZ attribution บันทึกใน DATA_SOURCES_AND_RIGHTS.md ข้อจำกัด third-party ยังคงใช้ตามต้นฉบับ

Audit JSON เก็บชนิดคอลัมน์ จำนวน null duplicate groups ค่า negative ที่แยกออก provenance และ source hashes ผล Coverage จากภาพจริงต้องรันก่อนจึงจะรายงานได้
