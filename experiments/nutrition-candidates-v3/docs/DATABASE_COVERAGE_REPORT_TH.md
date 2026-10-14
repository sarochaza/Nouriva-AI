# Database Coverage Report

ฐานข้อมูลมี 13,661 รายการ ค่า kcal/protein/carbs/fat ครบและไม่ติดเงื่อนไข invalid 13,590 รายการ (99.480%) นี่คือ **ความครบของข้อมูลอ้างอิง** ไม่ใช่เปอร์เซ็นต์ที่ AI จะจับคู่ชื่อได้

มี Alias ภาษาอังกฤษ/ไทย 46 รายการพร้อม Food ID, preparation state และเหตุผล Fuzzy suggestions ไม่ถูกนับเป็น MATCHED

ผลจริงยังไม่รัน จึงไม่มี Real prediction Match Coverage ในเอกสารนี้ ผลจาก Mock แยกไว้ใน `results/mock/software-validation/comparison/database_coverage.csv` และ `.json` ไม่ใช้แทนผลของภาพอาหารจริง

หลังรันจริง `results/real/<run-id>/comparison/database_coverage.csv` แสดงทุกวัตถุดิบที่ทำนาย ชื่อ สถานะ Food ID Source ID เหตุผล และ Missing nutrients JSON รวม Micro match coverage ส่วน Summary แสดง Mean item/mass/complete nutrient coverage และจำนวนที่ใช้ ตัวหารไม่รวม Trial ที่ไม่มี Prediction เพราะ API ล้มเหลว จึงต้องอ่านคู่กับ Failure Rate

Ingredient Match Coverage = matched rows / predicted rows. Complete Nutrient Coverage = matched rows with all 4 nutrients / predicted rows. Mass Match Coverage = predicted matched grams / all predicted grams. ถ้าไม่มีมวลรวม ตัวหลังเป็น null ไม่ใช่ 0

รายงาน Ingredient recall แยก เพราะการจับชื่อวัตถุดิบที่ AI ทำนายครบไม่ได้หมายความว่า AI ตรวจเจอวัตถุดิบจริงทุกอย่าง
