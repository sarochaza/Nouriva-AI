# MOCK · ตรวจซอฟต์แวร์เท่านั้น ไม่ใช่ความแม่นยำจริง

| วิธี | เทียบคู่สำเร็จ | kcal MAE | โปรตีน MAE (g) | คาร์บ MAE (g) | ไขมัน MAE (g) | Ingredient F1 | HTTP attempts |
|---|---:|---:|---:|---:|---:|---:|---:|
|single|15/15|8.2000|0.1860|1.9160|0.0480|1.0000|15|
|ensemble2|15/15|5.7400|0.1302|1.3412|0.0336|1.0000|30|

- ผลเลือก candidate: MOCK_NOT_ELIGIBLE; selected=None
- Mock responses cannot select a nutrition agent
- ค่าต่อจาน = กรัมที่คาด / 100 × ค่าต่อ 100g; DATABASE มาก่อน AI_ESTIMATE; ค่าที่ขาดเป็น null
- Ensemble เฉลี่ย contributions จาก 2 ตัว; วัตถุดิบพบตัวเดียวใช้กรัมเฉลี่ยกับ 0g ของตัวที่ไม่พบ
- รายงานหลักใช้คู่ภาพ/รอบที่ทั้งสองวิธีคำนวณครบ; FAILED, INCOMPLETE, NOT_RUN ไม่ใช่ error=0
- แยก cohort ที่ทั้งคู่ใช้ DB ล้วนและ cohort ที่มี AI estimate ใน CSV เพื่อตรวจผลของ fallback
- Single ใช้ 1 response; Ensemble ใช้ 2 responses ต่อภาพต่อรอบ จึงใช้งบต่างกัน
- F1 ใช้ชื่อที่ normalize + synonym จำกัด ไม่ใช่การจับความหมายอัตโนมัติ; ตรวจกรณีชื่อเฉพาะ/ชื่อทั่วไป
- Bootstrap ใช้จานเป็นหน่วยหลังเฉลี่ย 3 รอบ; 3 รอบของภาพเดิมไม่ใช่ภาพอิสระ 3 ภาพ
- ดูสัดส่วนและแหล่งค่ารายวัตถุดิบใน ingredient_breakdown.csv และ JSON trial
- ไม่มีการเลือก Agent จาก MOCK; ผู้ชนะจริงเป็น candidate สำหรับ pilot และควรยืนยันด้วยภาพชุดใหม่
