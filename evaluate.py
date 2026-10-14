import csv
from pathlib import Path
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent
with (ROOT/'results'/'predictions.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
valid = [r for r in rows if r['status'] == 'OK']
if not valid:
    raise SystemExit('No successful predictions yet')
y_true = [r['ground_truth_th'] for r in valid]
y_pred = [r['predicted_th'] for r in valid]
labels = sorted(set(y_true) | set(y_pred))
print('Images evaluated:', len(valid))
print('Accuracy:', round(accuracy_score(y_true, y_pred), 4))
print('Macro F1:', round(f1_score(y_true, y_pred, labels=labels, average='macro', zero_division=0), 4))
print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
cm = confusion_matrix(y_true, y_pred, labels=labels)
fig, ax = plt.subplots(figsize=(12, 10))
ConfusionMatrixDisplay(cm, display_labels=labels).plot(ax=ax, xticks_rotation=90, colorbar=False)
fig.tight_layout()
fig.savefig(ROOT/'results'/'confusion_matrix.png', dpi=160)
print('Saved results/confusion_matrix.png')
