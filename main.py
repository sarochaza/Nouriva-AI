import argparse
import csv
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
CLASSES = ['ไก่ทอด','แกงเขียวหวาน','ข้าวมันไก่','ข้าวเหนียวมะม่วง','ก๋วยเตี๋ยวเรือ','ผัดไทย','ผัดกะเพรา','ส้มตำ','ข้าวขาหมู','ต้มยำกุ้ง']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5, help='Number of images; 0 means all')
    parser.add_argument('--model', default=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'))
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise SystemExit('Missing GEMINI_API_KEY in .env')
    datafile = ROOT / 'ground_truth.csv'
    if not datafile.exists():
        raise SystemExit('Extract thai_food_phase1_200.zip into this folder first.')
    with datafile.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    selected = rows if args.limit == 0 else rows[:args.limit]
    client = genai.Client(api_key=key)
    output = ROOT / 'results'
    output.mkdir(exist_ok=True)
    path = output / 'predictions.csv'
    existing = {}
    if path.exists():
        with path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                existing[row['image_path']] = row
    fields = ['image_path','ground_truth_th','predicted_th','correct','model','status','raw_response']
    for index, row in enumerate(selected, 1):
        rel = row['image_path']
        if rel in existing and existing[rel].get('status') == 'OK':
            print(f'[{index}/{len(selected)}] SKIP {rel}')
            continue
        image_path = ROOT / rel
        if not image_path.is_file():
            raise SystemExit(f'Image not found: {image_path}')
        prompt = ('ระบุชื่อเมนูอาหารไทยหลักจากภาพนี้ เลือกได้เพียงหนึ่งรายการจาก: '
                  + ', '.join(CLASSES)
                  + '. หากไม่สามารถระบุอย่างสมเหตุสมผลให้ตอบ UNKNOWN. '
                  + 'ตอบเป็น JSON เท่านั้นในรูป {"food_name":"ชื่อเมนูหรือ UNKNOWN"}. '
                  + 'ห้ามใช้ชื่อไฟล์หรือข้อมูลอื่นนอกภาพ')
        try:
            response = client.models.generate_content(
                model=args.model,
                contents=[types.Part.from_text(text=prompt),
                          types.Part.from_bytes(data=image_path.read_bytes(), mime_type='image/jpeg')],
                config=types.GenerateContentConfig(temperature=0, response_mime_type='application/json'),
            )
            raw = response.text or ''
            prediction = json.loads(raw).get('food_name', 'UNKNOWN').strip()
            if prediction not in CLASSES:
                prediction = 'UNKNOWN'
            status = 'OK'
        except Exception as e:
            raw = f'{type(e).__name__}: {e}'
            prediction = ''
            status = 'ERROR'
        existing[rel] = dict(image_path=rel, ground_truth_th=row['ground_truth_th'],
                             predicted_th=prediction, correct=str(prediction == row['ground_truth_th']) if status == 'OK' else '',
                             model=args.model, status=status, raw_response=raw)
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(existing.values())
        print(f'[{index}/{len(selected)}] {rel}: {prediction} ({status})')
        if status == 'ERROR':
            print(raw)
            print('Stopped after API error. Check key, quota, model, or network; then rerun.')
            break
        time.sleep(1)
    print(f'Results: {path}')

if __name__ == '__main__':
    main()
