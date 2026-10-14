import argparse
import base64
import csv
import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

ROOT = Path(__file__).resolve().parent
CLASSES = ['ไก่ทอด','แกงเขียวหวาน','ข้าวมันไก่','ข้าวเหนียวมะม่วง','ก๋วยเตี๋ยวเรือ','ผัดไทย','ผัดกะเพรา','ส้มตำ','ข้าวขาหมู','ต้มยำกุ้ง']
FIELDS = ['image_path', 'ground_truth_th', 'predicted_th', 'correct', 'model', 'status', 'raw_response']


def save_results(path, records):
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records.values())
    temp.replace(path)


def transient_error(error):
    status = getattr(error, 'status_code', None)
    return status in (429, 500, 502, 503, 504) or (status is None and isinstance(error, (TimeoutError, ConnectionError)))


def predict(client, model, path, max_retries):
    image_b64 = base64.b64encode(path.read_bytes()).decode('ascii')
    mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
    prompt = (
        'ระบุชื่อเมนูอาหารไทยหลักจากภาพนี้ เลือกได้เพียงหนึ่งรายการจาก: '
        + ', '.join(CLASSES)
        + '. หากไม่สามารถระบุอย่างสมเหตุสมผลให้ตอบ UNKNOWN. '
        + 'ตอบเป็น JSON เท่านั้นในรูป {"food_name":"ชื่อเมนูหรือ UNKNOWN"}. '
        + 'ห้ามใช้ชื่อไฟล์หรือข้อมูลอื่นนอกภาพ'
    )
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}}
                ]}],
                temperature=0,
                max_completion_tokens=256,
            )
            raw = response.choices[0].message.content or ''
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            try:
                prediction = json.loads(cleaned)['food_name'].strip()
            except (ValueError, KeyError, AttributeError, TypeError):
                prediction = cleaned.strip(' "\'\n')
            if prediction not in CLASSES and prediction != 'UNKNOWN':
                return 'UNKNOWN', raw, 'INVALID_RESPONSE'
            return prediction, raw, 'OK'
        except Exception as error:
            if transient_error(error) and attempt < max_retries:
                wait = min(60, 5 * (2 ** attempt)) + random.uniform(0, 1)
                print(f'  Temporary API error ({type(error).__name__}); retry {attempt+1}/{max_retries} in {wait:.1f}s')
                time.sleep(wait)
                continue
            return '', f'{type(error).__name__}: {error}', 'ERROR'


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description='Thai food image classification using Groq Vision')
    parser.add_argument('--limit', type=int, default=5, help='First N images from CSV; 0 = all')
    parser.add_argument('--model', default=os.getenv('GROQ_MODEL', ''), help='Groq vision model ID')
    parser.add_argument('--delay', type=float, default=2.0, help='Seconds between requests')
    parser.add_argument('--retries', type=int, default=4, help='Retries for temporary API errors')
    args = parser.parse_args()
    if args.limit < 0 or args.delay < 0 or args.retries < 0:
        parser.error('--limit, --delay and --retries must be >= 0')
    if not args.model:
        raise SystemExit('Missing GROQ_MODEL in .env or --model argument')
    key = os.getenv('GROQ_API_KEY')
    if not key:
        raise SystemExit('Missing GROQ_API_KEY in .env')
    csv_path = ROOT / 'ground_truth.csv'
    if not csv_path.is_file():
        raise SystemExit('Missing ground_truth.csv')
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows or not {'image_path', 'ground_truth_th'} <= set(rows[0]):
        raise SystemExit('CSV must have image_path and ground_truth_th columns')
    selected = rows if args.limit == 0 else rows[:args.limit]
    output = ROOT / 'results' / 'groq'
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'predictions.csv'
    existing = {}
    if path.is_file():
        with path.open(encoding='utf-8-sig', newline='') as f:
            for record in csv.DictReader(f):
                existing[record['image_path']] = record
    client = Groq(api_key=key, timeout=60.0)
    for index, row in enumerate(selected, 1):
        rel = row['image_path']
        previous = existing.get(rel, {})
        if (previous.get('status') == 'OK' and previous.get('model') == args.model
                and previous.get('ground_truth_th') == row['ground_truth_th']):
            print(f'[{index}/{len(selected)}] SKIP {rel}')
            continue
        image_path = ROOT / rel
        if not image_path.is_file():
            raise SystemExit(f'Image not found: {image_path}')
        prediction, raw, status = predict(client, args.model, image_path, args.retries)
        existing[rel] = {
            'image_path': rel, 'ground_truth_th': row['ground_truth_th'],
            'predicted_th': prediction,
            'correct': str(prediction == row['ground_truth_th']) if status == 'OK' else '',
            'model': args.model, 'status': status, 'raw_response': raw,
        }
        save_results(path, existing)
        print(f'[{index}/{len(selected)}] {rel}: {prediction} ({status})')
        if status != 'OK':
            print(raw[:500])
            print('Stopped. Fix the issue, then rerun to resume successful images.')
            break
        if index < len(selected):
            time.sleep(args.delay)
    print(f'Results: {path}')

if __name__ == '__main__':
    main()
