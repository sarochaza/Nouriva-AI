import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score

ROOT = Path(__file__).resolve().parent
CLASSES = ['ไก่ทอด','แกงเขียวหวาน','ข้าวมันไก่','ข้าวเหนียวมะม่วง','ก๋วยเตี๋ยวเรือ','ผัดไทย','ผัดกะเพรา','ส้มตำ','ข้าวขาหมู','ต้มยำกุ้ง']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-partial', action='store_true', help='Evaluate even if fewer than all dataset images are OK')
    args = parser.parse_args()
    with (ROOT / 'ground_truth.csv').open(encoding='utf-8-sig', newline='') as f:
        truth = list(csv.DictReader(f))
    expected = {r['image_path']: r['ground_truth_th'] for r in truth}
    result_dir = ROOT / 'results' / 'groq'
    with (result_dir / 'predictions.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    valid = [r for r in rows if r['status'] == 'OK' and r['image_path'] in expected and r['ground_truth_th'] == expected[r['image_path']]]
    if not valid:
        raise SystemExit('No valid successful predictions')
    models = {r['model'] for r in valid}
    if len(models) != 1:
        raise SystemExit(f'Mixed models in results: {models}. Use one model per evaluation.')
    if len(valid) != len(expected) and not args.allow_partial:
        raise SystemExit(f'Only {len(valid)}/{len(expected)} valid predictions. Run all images or use --allow-partial for a preliminary report.')
    labels = CLASSES + (['UNKNOWN'] if any(r['predicted_th'] == 'UNKNOWN' for r in valid) else [])
    y_true = [r['ground_truth_th'] for r in valid]
    y_pred = [r['predicted_th'] for r in valid]
    print(f'Model: {next(iter(models))}')
    print(f'Images evaluated: {len(valid)}/{len(expected)}')
    print(f'Accuracy: {accuracy_score(y_true, y_pred):.4f}')
    print(f'Macro F1 (10 food classes): {f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0):.4f}')
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    plt.rcParams['font.family'] = ['Noto Sans Thai', 'Tahoma', 'DejaVu Sans']
    fig, ax = plt.subplots(figsize=(13, 11))
    ConfusionMatrixDisplay(cm, display_labels=labels).plot(ax=ax, xticks_rotation=90, colorbar=False)
    fig.tight_layout()
    output = result_dir / 'confusion_matrix.png'
    fig.savefig(output, dpi=160)
    plt.close(fig)
    print(f'Saved {output}')

if __name__ == '__main__':
    main()
