# Nouriva AI — EfficientNet-B0 Food Classification

การทดลองฝึกโมเดลจำแนกภาพอาหารไทย 10 ประเภทด้วย **EfficientNet-B0 (Transfer Learning)** บน Google Colab และการนำโมเดลไปใช้ในแอป Streamlit ของ Nouriva

> **ขอบเขต:** โมเดลในระยะนี้ทำนาย **ชื่อประเภทอาหาร** ไม่ได้ทำนายน้ำหนัก ส่วนผสม พลังงาน หรือคุณค่าทางโภชนาการจากภาพโดยตรง

## ผลการทดลอง (Clean Model)

| ตัวชี้วัด | ผล |
|---|---:|
| จำนวนประเภทอาหาร | 10 |
| Train หลังทำความสะอาด | 2,563 ภาพ |
| Validation หลังทำความสะอาด | 270 ภาพ |
| Test | 200 ภาพ (20 ภาพ/ประเภท) |
| Best Validation Accuracy | **95.93%** |
| Test Accuracy | **92.00%** (184/200) |
| Test Macro F1 | **91.98%** |
| Training epochs | 10 |
| GPU ที่แสดงใน Notebook | NVIDIA Tesla T4 |

### ผล Test แยกตามประเภท

| อาหาร | Precision | Recall | F1-score | จำนวนทดสอบ |
|---|---:|---:|---:|---:|
| ก๋วยเตี๋ยวเรือ | 0.85 | 0.85 | 0.85 | 20 |
| ข้าวขาหมู | 0.90 | 0.95 | 0.93 | 20 |
| ข้าวมันไก่ | 0.90 | 0.90 | 0.90 | 20 |
| ข้าวเหนียวมะม่วง | 1.00 | 0.95 | 0.97 | 20 |
| ต้มยำกุ้ง | 0.80 | 1.00 | 0.89 | 20 |
| ผัดกะเพรา | 0.95 | 1.00 | 0.98 | 20 |
| ผัดไทย | 0.94 | 0.85 | 0.89 | 20 |
| ส้มตำ | 0.95 | 0.90 | 0.92 | 20 |
| แกงเขียวหวาน | 1.00 | 0.80 | 0.89 | 20 |
| ไก่ทอด | 0.95 | 1.00 | 0.98 | 20 |

## ชุดข้อมูลและการเตรียมข้อมูล

Notebook ใช้ไฟล์ `THFOOD10.zip` ซึ่งมีโฟลเดอร์ `train` และ `val` รวม 10 คลาส ก่อนทำความสะอาดมี Train 2,564 ภาพ และ Validation 290 ภาพ จากนั้นตรวจความคล้ายกับชุด Test 200 ภาพด้วย perceptual hash (pHash) และคัดภาพที่น่าสงสัยออก 21 ภาพ เหลือ Train 2,563 และ Validation 270 ภาพ ทั้งนี้การตรวจดังกล่าวเป็นการลดความเสี่ยงข้อมูลรั่วไหล ไม่ใช่หลักประกันว่าไม่มีภาพที่สัมพันธ์กันระหว่างชุดข้อมูลเลย

**แหล่งภาพต้นฉบับและเงื่อนไขสิทธิ์ใช้งานยังต้องระบุเพิ่มเติม** จากผู้จัดเตรียม `THFOOD10.zip` และ Test Set ไม่ควรอ้างว่าชุดข้อมูลมาจากแหล่งใดโดยไม่มีหลักฐาน

## ขั้นตอนฝึกโมเดล

1. โหลด EfficientNet-B0 ที่มีน้ำหนัก Pretrained จาก ImageNet ผ่าน `torchvision`.
2. Freeze ส่วน `features` และแทนที่ชั้น classifier เพื่อรองรับอาหารไทย 10 ประเภท.
3. ใช้ `RandomResizedCrop(224)`, `RandomHorizontalFlip`, `RandomRotation(15)` สำหรับ Train และใช้ Resize/CenterCrop สำหรับ Validation.
4. ใช้ `CrossEntropyLoss` และ `AdamW` (learning rate `0.001`, weight decay `0.0001`).
5. Train สูงสุด 10 Epoch พร้อม Early Stopping patience 3; เก็บ Checkpoint ที่ Validation Accuracy สูงสุด.
6. เริ่มเทรน Clean Model ใหม่จากน้ำหนัก Pretrained แทนการใช้ Checkpoint เก่าต่อ แล้วประเมินบน Test Set 200 ภาพ.

โมเดลที่บันทึกใน Notebook: `models/best_model_clean.pth` โดยมี `model_state_dict`, `class_names`, `architecture`, `epoch` และ `val_accuracy`.

## ไฟล์สำคัญ

```text
Nouriva-App/
├── app.py                         # Streamlit สำหรับอัปโหลดภาพและทำนาย
├── models/
│   └── best_model_clean.pth       # Checkpoint (ถ้าขนาด/สิทธิ์อนุญาตให้อัปโหลด)
├── Nouriva_EfficientNetB0.ipynb  # Notebook การฝึกและประเมินผล
├── README.md
└── .gitignore
```

ไฟล์ผลประเมินที่ Notebook บันทึกใน Google Drive: `results/efficientnet_clean_predictions.csv` ควรคัดลอกมาเก็บใน Repository หากต้องการให้ตรวจสอบผลซ้ำได้

## การใช้งานแอป

รันจากโฟลเดอร์ `Nouriva-App` ที่ติดตั้ง dependencies ซึ่งใช้จริงใน `app.py` แล้ว:

```powershell
python -m streamlit run app.py
```

จากนั้นเปิด `http://localhost:8501` การทำงานต้องมี Checkpoint ในตำแหน่งที่ `app.py` อ้างถึง และมี Python packages ที่สอดคล้องกัน (เช่น `torch`, `torchvision`, `streamlit`, `Pillow` ตามที่โค้ดใช้) ก่อนใช้งานควรทดสอบการโหลดโมเดลกับไฟล์ Checkpoint จริง

## ข้อจำกัด

- ผลที่รายงานเป็นการทดสอบเพียง 10 ประเภทและ Test Set 200 ภาพ ไม่ครอบคลุมทุกเมนูอาหารไทย
- คะแนน Softmax ไม่ควรตีความว่าเป็นความน่าจะเป็นที่ปรับเทียบความเชื่อมั่นแล้วโดยอัตโนมัติ
- การประเมินอาหารในภาพไม่เท่ากับการประเมินกรัมหรือสารอาหาร
- ควรทดสอบกับภาพจากแหล่งใหม่และตรวจสอบภาพซ้ำ/ภาพคล้ายอย่างต่อเนื่อง
- แหล่งที่มาและสิทธิ์ใช้งานชุดข้อมูลต้องได้รับการยืนยันเพิ่มเติม

## แหล่งอ้างอิง

- Tan, M. & Le, Q. (2019). *EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks.* https://arxiv.org/abs/1905.11946
- PyTorch Torchvision — EfficientNet-B0: https://pytorch.org/vision/stable/models/generated/torchvision.models.efficientnet_b0.html
- PyTorch — Transfer Learning for Computer Vision: https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html
- scikit-learn — Classification Report: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report.html
- scikit-learn — F1 Score: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html
- Streamlit — Documentation: https://docs.streamlit.io/
- **หลักฐานผลการทดลองในโครงการ:** `Nouriva_EfficientNetB0.ipynb` (Training และ Clean Model Test outputs)

## การจัดเก็บบน GitHub

ควรแยกสาขา `trained-model-v2` ออกจาก `ai-response-testing`; อย่า Commit `.venv/`, `.env`, API keys หรือ Dataset ที่ไม่มีสิทธิ์เผยแพร่ หาก Checkpoint ใหญ่เกิน 100 MB ให้ใช้ Git LFS หรือแหล่งจัดเก็บโมเดลที่เหมาะสมแทน Git ปกติ
