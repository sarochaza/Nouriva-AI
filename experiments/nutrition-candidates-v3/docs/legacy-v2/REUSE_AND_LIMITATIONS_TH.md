# สิ่งที่ต่อยอดและข้อจำกัด

ตรวจ Workspace เดิมเฉพาะ common helpers, nutrition catalog, API/method flow, evaluation, config และ tests

ใช้ `src/common.py` เดิมเป็นฐานของ file helpers และรักษาแนวคิดเดิมของ no-imputation calculation, Groq image requests, 3-stage Multi-Agent และ 2/3 median Ensemble เพิ่ม schema สถานะ/evidence, Source ID, per-100g provenance, database audits, JSONL loader, run freeze, retry journaling และ evaluation cohorts ตาม requirement ใหม่

Catalog เดิมอ้าง ingredient CSV ของ Nutrition5k และสูตร per gram เปลี่ยนเป็นฐาน USDA แยกจาก test labels และสูตร per 100g การเปลี่ยนนี้จำเป็นเพื่อไม่ใช้ฐานที่สร้างจาก Ground Truth ของจานทดสอบ

ข้อที่ยังไม่ได้ยืนยัน:

1. **REAL API NOT VERIFIED** ไม่ส่งภาพให้ Groq จริง ไม่มีการทดสอบ billed inference ในรอบพัฒนานี้
2. **Native Windows PowerShell not executed** ไม่มี Windows/PowerShell ใน runtime ที่ใช้ทดสอบ ตรวจโครงคำสั่งและใช้ Python stdlib, pathlib และ quoting สำหรับ PowerShell แต่ต้องทดสอบคำสั่งบนเครื่องคุณ
3. **Local full dataset not accessed** ไม่เข้าถึง `C:\Users\CHOMP2O\food-nutrients` จาก Work ใช้ schema ของ publisher และตรวจ local metadata ทุกครั้งก่อนเลือกภาพ
4. **Thai nutrient transcription not imported** PDF 148 หน้าเป็นภาพสแกน Text extraction ได้เพียงตัวคั่นหน้า จึงไม่มีเลขไทยที่เดาแล้วใส่ DB มี importer ที่บังคับการตรวจจากคน
5. **Conservative matching** ชื่อทั่วไป เช่น “rice” หรือ “chicken” อาจต้องตรวจ เพราะ DB แยกชนิด/ส่วน/วิธีปรุง นี่อาจลด Success Rate ของงานจริง ห้ามอ้างว่าทุกรูปจะได้ full nutrients หากปรับ Alias ต้องมีเหตุผลและเริ่ม Run ใหม่ครบทุกวิธี
6. **Reference compatibility** Labels ของ food-nutrients อาจใช้สูตรที่ต่างจาก USDA การเห็นคลาดเคลื่อนไม่พิสูจน์ว่า Vision ผิดทั้งหมด Loader รายงานผลรวม ingredient labels ที่ไม่ตรง total labels โดยไม่แก้ Ground Truth เอง
7. **FNDDS links partial** NDB crosswalk เชื่อม 14,079/18,584 component rows ที่เหลือ 4,505 แถวเป็น UNLINKED_NDB ไม่จับเลข SR code เป็น FDC ID โดยตรง
8. **Measures need identity review** AUSNUT เป็นฐานหน่วยตวงอาหารออสเตรเลีย ไม่ใช้แทนค่า nutrients และไม่โยง Public food key กับ USDA อัตโนมัติ

ไม่มีผลประสิทธิภาพจริงใน ZIP ค่า Mock ใช้ colored squares และ scripted responses ไม่ใช่ผลการรู้จำอาหารจากภาพ
