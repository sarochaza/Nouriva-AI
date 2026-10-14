"""Offline paired evaluation. Expected values are used here, never by the agents."""
import argparse
import html
import math
import random
import statistics
from pathlib import Path
from candidate.pipeline import COMPLETE
from candidate.schema import CORE
from evaluation.metrics import ingredient_scores, label, mean, numeric_metrics
from src.common import load_json, save_json, sha256, write_csv

METHODS = ('single', 'ensemble2')
FLOORS = {'kcal': 50.0, 'protein_g': 5.0, 'carbs_g': 5.0, 'fat_g': 5.0}


def ingredient_details(expected, predicted):
    scores = ingredient_scores(expected, predicted)
    out = {'ingredient_precision': scores['precision'], 'ingredient_recall': scores['recall'],
           'ingredient_F1': scores['F1'], 'matched_weight_MAE_g': scores['weight_MAE_g'],
           'union_weight_MAE_g': None, 'ingredient_share_L1_percent': None}
    if scores['F1'] is None:
        return out
    def group(items):
        result = {}
        for i in items:
            key = label(i['name'])
            result[key] = result.get(key, 0) + i['grams']
        return result
    gt, pr = group(expected), group(predicted)
    union = sorted(set(gt) | set(pr))
    out['union_weight_MAE_g'] = mean([abs(gt.get(k, 0) - pr.get(k, 0)) for k in union])
    gt_mass, pr_mass = sum(gt.values()), sum(pr.values())
    if gt_mass > 0 and pr_mass > 0:
        out['ingredient_share_L1_percent'] = 100 * sum(abs(gt.get(k, 0) / gt_mass - pr.get(k, 0) / pr_mass) for k in union)
    return out


def select_winner(rows, frozen, agent_config):
    result = {'status': None, 'selected_method': None, 'agent_config': None, 'mode': frozen['mode'],
              'primary_metric': 'mean_scaled_absolute_error_kcal_protein_carbs_fat',
              'denominator_floors': FLOORS, 'minimum_relative_improvement': 0.05,
              'minimum_completion_rate': 0.9, 'minimum_all_rounds_paired_dish_fraction': 0.8,
              'minimum_distinct_images': 5, 'paired_dishes': 0, 'difference_ci95': None,
              'bootstrap_unit': 'dish mean over three rounds', 'bootstrap_draws': 2000,
              'reason': None, 'fingerprint': frozen.get('fingerprint'),
              'database_sha256': frozen.get('database_sha256'), 'prompt_version': frozen.get('prompt_version'),
              'code_sha256': frozen.get('code_sha256'), 'prompt_sha256': frozen.get('prompt_sha256'),
              'limitation': 'Pilot candidate selection, not a clinical validation or architecture-causality claim.'}
    if frozen['mode'] != 'REAL' or any(r.get('mode') == 'MOCK' or r.get('mock_call_detected') for r in rows):
        result.update(status='MOCK_NOT_ELIGIBLE', reason='Mock responses cannot select a nutrition agent')
        return result
    ids = {i['dish_id'] for i in frozen.get('images', [])} or {r['dish_id'] for r in rows}
    planned = len(ids) * 3
    if frozen['rounds'] != 3 or len(ids) < 5:
        result.update(status='INSUFFICIENT_DATA', reason='Need at least five distinct dishes and three rounds')
        return result
    by_key = {(r['dish_id'], r['round'], r['method']): r for r in rows}
    if len(by_key) != len(rows):
        raise ValueError('Duplicate evaluation identities')
    completion = {m: sum(r['status'] in COMPLETE and r.get('scaled_nutrient_error') is not None for r in rows if r['method'] == m) / planned for m in METHODS}
    paired = [dish for dish in sorted(ids) if all((dish, rnd, m) in by_key and
                by_key[dish, rnd, m]['status'] in COMPLETE and
                by_key[dish, rnd, m].get('scaled_nutrient_error') is not None
                for rnd in (1, 2, 3) for m in METHODS)]
    result.update(completion_rate=completion, paired_dishes=len(paired), distinct_images=len(ids))
    if min(completion.values()) < .9 or len(paired) < 5 or len(paired) / len(ids) < .8:
        result.update(status='INSUFFICIENT_DATA', reason='Complete more trials: both methods need >=90% completion and >=80% dishes fully paired over all rounds')
        return result
    dish_scores = {m: [mean([by_key[dish, rnd, m]['scaled_nutrient_error'] for rnd in (1, 2, 3)]) for dish in paired] for m in METHODS}
    averages = {m: mean(dish_scores[m]) for m in METHODS}
    differences = [b - a for a, b in zip(dish_scores['single'], dish_scores['ensemble2'])]
    rng = random.Random(20261014)
    boot = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(2000))
    interval = [boot[int(.025 * (len(boot) - 1))], boot[int(.975 * (len(boot) - 1))]]
    better = min(averages, key=averages.get)
    worse = 'ensemble2' if better == 'single' else 'single'
    improvement = (averages[worse] - averages[better]) / averages[worse] if averages[worse] else 0
    result.update(primary_scores=averages, difference_ci95=interval,
                  difference_definition='ensemble2 score minus single score; positive favors single',
                  relative_improvement=improvement, lower_point_estimate=better)
    excludes_zero = interval[0] > 0 if better == 'single' else interval[1] < 0
    if improvement < .05 or not excludes_zero:
        result.update(status='NO_CLEAR_WINNER', reason='Difference below 5% or paired-dish uncertainty includes zero; collect more held-out images',
                      efficiency_suggestion='single uses one vision response; no accuracy winner is selected')
        return result
    result.update(status='SELECTED_FOR_PILOT', selected_method=better, agent_config=agent_config,
                  reason='Pre-registered improvement and paired-dish uncertainty criteria passed')
    return result


def evaluate(run_dir, truth_path):
    run_dir, truth_path = Path(run_dir), Path(truth_path)
    frozen = load_json(run_dir / 'frozen.json')
    if frozen.get('schema_version') != 3:
        raise ValueError('Use candidate.evaluate only with a candidate v3 run')
    if sha256(truth_path) != frozen['truth_sha256']:
        raise ValueError('Expected labels changed after preparation')
    truth_file = load_json(truth_path)
    if truth_file['mode'] != frozen['mode']:
        raise ValueError('Expected labels and inference run mode differ')
    truth = {r['dish_id']: r for r in truth_file['records']}
    if len(truth) != len(truth_file['records']) or set(truth) != {r['dish_id'] for r in frozen['images']}:
        raise ValueError('Expected labels must exactly match selected image IDs')
    rows, details = [], []
    for rnd in (1, 2, 3):
        for image in frozen['images']:
            dish = image['dish_id']
            gt = truth[dish]
            numeric_metrics([gt[k] for k in CORE] + [gt['mass_g']], [gt[k] for k in CORE] + [gt['mass_g']])
            for method in METHODS:
                row = {'mode': frozen['mode'], 'dish_id': dish, 'round': rnd, 'method': method,
                       'status': 'NOT_RUN', 'error_type': None, 'http_attempts': 0, 'known_tokens': 0,
                       'total_tokens': None, 'known_cost_usd': 0, 'cost_usd': None,
                       'latency_seconds': None, 'database_mass_coverage': None,
                       'database_only_mass_coverage': None, 'fallback_ingredient_count': None,
                       'ingredient_precision': None, 'ingredient_recall': None, 'ingredient_F1': None,
                       'matched_weight_MAE_g': None, 'union_weight_MAE_g': None,
                       'ingredient_share_L1_percent': None, 'mass_prediction_g': None,
                       'mass_truth_g': gt['mass_g'], 'mass_abs_error_g': None,
                       'scaled_nutrient_error': None, 'mock_call_detected': False}
                for k in CORE:
                    row.update({k + '_truth': gt[k], k + '_prediction': None,
                                k + '_abs_error': None, k + '_ape_percent': None})
                path = run_dir / 'records' / ('round_' + str(rnd)) / (dish + '_' + method + '.json')
                if path.exists():
                    record = load_json(path)
                    if (record['fingerprint'], record['mode'], record['dish_id'], record['round'], record['method']) != (frozen['fingerprint'], frozen['mode'], dish, rnd, method):
                        raise ValueError('Record identity/fingerprint differs: ' + str(path))
                    if record['status'] not in (*COMPLETE, 'INCOMPLETE', 'FAILED'):
                        raise ValueError('Invalid candidate status')
                    events = record.get('call_metadata', [])
                    row.update(status=record['status'], error_type=record.get('error_type'),
                               http_attempts=len(events), known_tokens=sum(e.get('total_tokens') or 0 for e in events),
                               latency_seconds=record.get('cumulative_latency_seconds'),
                               known_cost_usd=sum(e.get('cost_usd') or 0 for e in events),
                               mock_call_detected=any(str(e.get('model', '')).startswith('MOCK') for e in events))
                    if events and all(e.get('total_tokens') is not None for e in events):
                        row['total_tokens'] = row['known_tokens']
                    if events and all(e.get('cost_usd') is not None for e in events):
                        row['cost_usd'] = row['known_cost_usd']
                    if record.get('prediction'):
                        row.update(ingredient_details(gt['ingredients'], record['prediction']['ingredients']))
                    nutrition = record.get('nutrition')
                    if nutrition:
                        for k in ('database_mass_coverage', 'database_only_mass_coverage', 'fallback_ingredient_count'):
                            row[k] = nutrition[k]
                        mass = nutrition['total_estimated_mass_g']
                        row.update(mass_prediction_g=mass, mass_abs_error_g=abs(mass - gt['mass_g']))
                        for ing in nutrition['ingredients']:
                            name = ing['prediction']['name']
                            gt_by_name = {}
                            for expected in gt['ingredients']:
                                key = label(expected['name'])
                                gt_by_name[key] = gt_by_name.get(key, 0) + expected['grams']
                            expected_g = gt_by_name.get(label(name))
                            details.append({'dish_id': dish, 'round': rnd, 'method': method, 'name': name,
                                'state': ing['prediction']['state'], 'predicted_grams': ing['grams'],
                                'predicted_share_percent': 100 * ing['grams'] / mass if mass else None,
                                'expected_grams_if_name_matched': expected_g,
                                'expected_share_percent_if_name_matched': 100 * expected_g / gt['mass_g'] if expected_g is not None and gt['mass_g'] else None,
                                'food_id': ing['food_id'], 'source_id': ing['source_id'],
                                'match_status': ing['match_status'], 'match_reason': ing['match_reason'],
                                **{k + '_source': ing['nutrient_sources'][k] for k in CORE},
                                **{k + '_per_100g': ing['per_100g'][k] for k in CORE},
                                **{k + '_contribution': ing['contribution'][k] for k in CORE}})
                        if record['status'] in COMPLETE:
                            if not nutrition['complete'] or nutrition['nutrients'] is None:
                                raise ValueError('Complete record contains incomplete nutrition')
                            scaled = []
                            for k in CORE:
                                value = nutrition['nutrients'][k]
                                numeric_metrics([gt[k]], [value])
                                error = abs(value - gt[k])
                                row.update({k + '_prediction': value, k + '_abs_error': error,
                                            k + '_ape_percent': 100 * error / gt[k] if gt[k] > 0 else None})
                                scaled.append(error / max(gt[k], FLOORS[k]))
                            row['scaled_nutrient_error'] = mean(scaled)
                rows.append(row)
    paired = {(r['dish_id'], r['round']) for r in rows if r['method'] == 'single' and r['status'] in COMPLETE} & {
              (r['dish_id'], r['round']) for r in rows if r['method'] == 'ensemble2' and r['status'] in COMPLETE}
    summaries = []
    for cohort in ('available_complete', 'paired_complete', 'database_only_paired', 'any_estimate_paired'):
        db_only = {(r['dish_id'], r['round']) for r in rows if r['status'] == 'COMPLETE_DATABASE' and
                   (r['dish_id'], r['round']) in paired}
        # A pair is DB-only only when both methods are DB-only.
        db_only = {key for key in db_only if all(next(r for r in rows if (r['dish_id'], r['round'], r['method']) == (*key, m))['status'] == 'COMPLETE_DATABASE' for m in METHODS)}
        for method in METHODS:
            for rnd in (1, 2, 3, 'all'):
                planned = [r for r in rows if r['method'] == method and (rnd == 'all' or r['round'] == rnd)]
                valid = [r for r in planned if r['status'] in COMPLETE and
                         (cohort == 'available_complete' or (r['dish_id'], r['round']) in paired) and
                         (cohort != 'database_only_paired' or (r['dish_id'], r['round']) in db_only) and
                         (cohort != 'any_estimate_paired' or (r['dish_id'], r['round']) not in db_only)]
                summary = {'method': method, 'round': rnd, 'cohort': cohort, 'planned': len(planned), 'scored': len(valid),
                           'completion_rate': sum(r['status'] in COMPLETE for r in planned) / len(planned),
                           'failed': sum(r['status'] == 'FAILED' for r in planned),
                           'incomplete': sum(r['status'] == 'INCOMPLETE' for r in planned),
                           'not_run': sum(r['status'] == 'NOT_RUN' for r in planned),
                           'http_attempts_total': sum(r['http_attempts'] for r in planned),
                           'known_tokens_total': sum(r['known_tokens'] for r in planned),
                           'total_tokens': sum(r['total_tokens'] for r in planned) if all(r['total_tokens'] is not None for r in planned) else None,
                           'cost_usd': sum(r['cost_usd'] for r in planned) if all(r['cost_usd'] is not None for r in planned) else None}
                for k in CORE:
                    metrics = numeric_metrics([r[k + '_truth'] for r in valid], [r[k + '_prediction'] for r in valid])
                    for name in ('MAE', 'RMSE', 'MAPE_percent', 'mape_n'):
                        summary[k + '_' + name] = metrics[name]
                for k in ('scaled_nutrient_error', 'mass_abs_error_g', 'ingredient_F1', 'union_weight_MAE_g', 'ingredient_share_L1_percent'):
                    summary[k + '_mean'] = mean([r[k] for r in valid])
                for k in ('database_mass_coverage', 'database_only_mass_coverage', 'fallback_ingredient_count', 'latency_seconds'):
                    summary[k + '_mean'] = mean([r[k] for r in planned])
                summaries.append(summary)
    selection = select_winner(rows, frozen, frozen['config'])
    result = {'mode': frozen['mode'], 'fingerprint': frozen['fingerprint'], 'paired_trials': len(paired),
              'rows': rows, 'summaries': summaries, 'selection': selection}
    out = run_dir / 'comparison'
    out.mkdir(exist_ok=True)
    save_json(out / 'summary.json', {k: v for k, v in result.items() if k != 'rows'})
    save_json(out / 'winner_selection.json', selection)
    save_json(out / 'per_evaluation.json', rows)
    write_csv(out / 'per_evaluation.csv', list(rows[0]), rows)
    write_csv(out / 'summary_by_method_round.csv', list(summaries[0]), summaries)
    write_csv(out / 'ingredient_breakdown.csv', list(details[0]) if details else ['dish_id', 'method', 'name'], details)
    render_report(out, result)
    return result


def render_report(out, result):
    mock = result['mode'] == 'MOCK'
    title = 'MOCK · ตรวจซอฟต์แวร์เท่านั้น ไม่ใช่ความแม่นยำจริง' if mock else 'Noura · ผลทดลอง Single vs Ensemble 2'
    table = [s for s in result['summaries'] if s['cohort'] == 'paired_complete' and s['round'] == 'all']
    def show(v):
        return '—' if v is None else f'{v:.4f}'
    header = '| วิธี | เทียบคู่สำเร็จ | kcal MAE | โปรตีน MAE (g) | คาร์บ MAE (g) | ไขมัน MAE (g) | Ingredient F1 | HTTP attempts |'
    md = ['# ' + title, '', header, '|---|---:|---:|---:|---:|---:|---:|---:|']
    html_rows = []
    for s in table:
        cells = [s['method'], str(s['scored']) + '/' + str(s['planned']), show(s['kcal_MAE']),
                 show(s['protein_g_MAE']), show(s['carbs_g_MAE']), show(s['fat_g_MAE']),
                 show(s['ingredient_F1_mean']), str(s['http_attempts_total'])]
        md.append('|' + '|'.join(cells) + '|')
        html_rows.append('<tr>' + ''.join('<td>' + html.escape(c) + '</td>' for c in cells) + '</tr>')
    selection = result['selection']
    notes = ['ผลเลือก candidate: ' + selection['status'] + '; selected=' + str(selection['selected_method']),
             selection['reason'],
             'ค่าต่อจาน = กรัมที่คาด / 100 × ค่าต่อ 100g; DATABASE มาก่อน AI_ESTIMATE; ค่าที่ขาดเป็น null',
             'Ensemble เฉลี่ย contributions จาก 2 ตัว; วัตถุดิบพบตัวเดียวใช้กรัมเฉลี่ยกับ 0g ของตัวที่ไม่พบ',
             'รายงานหลักใช้คู่ภาพ/รอบที่ทั้งสองวิธีคำนวณครบ; FAILED, INCOMPLETE, NOT_RUN ไม่ใช่ error=0',
             'แยก cohort ที่ทั้งคู่ใช้ DB ล้วนและ cohort ที่มี AI estimate ใน CSV เพื่อตรวจผลของ fallback',
             'Single ใช้ 1 response; Ensemble ใช้ 2 responses ต่อภาพต่อรอบ จึงใช้งบต่างกัน',
             'F1 ใช้ชื่อที่ normalize + synonym จำกัด ไม่ใช่การจับความหมายอัตโนมัติ; ตรวจกรณีชื่อเฉพาะ/ชื่อทั่วไป',
             'Bootstrap ใช้จานเป็นหน่วยหลังเฉลี่ย 3 รอบ; 3 รอบของภาพเดิมไม่ใช่ภาพอิสระ 3 ภาพ',
             'ดูสัดส่วนและแหล่งค่ารายวัตถุดิบใน ingredient_breakdown.csv และ JSON trial',
             'ไม่มีการเลือก Agent จาก MOCK; ผู้ชนะจริงเป็น candidate สำหรับ pilot และควรยืนยันด้วยภาพชุดใหม่']
    md += ['', *['- ' + n for n in notes]]
    (out / 'report.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    rows = ''.join(html_rows)
    note_html = ''.join('<li>' + html.escape(n) + '</li>' for n in notes)
    page = f'''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Noura candidate experiment</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6f5;color:#172d29;font:16px/1.7 system-ui,sans-serif}}
main{{max-width:1150px;margin:40px auto;padding:28px}}header{{padding:32px;background:#174c43;color:white;border-radius:22px}}
h1{{font-size:30px;line-height:1.4;margin:8px 0}}.tag{{letter-spacing:.14em;font-size:12px}}section{{background:white;padding:26px;border-radius:20px;margin-top:22px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:14px;text-align:left;border-bottom:1px solid #e4ebe8;white-space:nowrap}}
th{{color:#64756f}}strong{{color:#176853}}a{{color:#176853}}.status{{padding:14px 20px;background:#e5f1ec;border-radius:12px;margin-top:18px;overflow-wrap:anywhere}}
li{{margin-bottom:10px}}code{{font-size:13px}}@media(max-width:600px){{main{{padding:12px;margin:8px auto}}header,section{{padding:20px}}h1{{font-size:24px}}}}
</style><main><header><div class="tag">NOURA / NUTRITION AGENT CANDIDATES / V3</div><h1>{html.escape(title)}</h1>
<p>ภาพเดียวกัน · ฐานข้อมูลเดียวกัน · 3 รอบ · ดึงค่าฐานข้อมูลก่อนประมาณ</p></header>
<section><h2>ความคลาดเคลื่อนบนคู่ทดลองเดียวกัน</h2><div class="scroll"><table><thead><tr>
<th>Candidate</th><th>Scored / planned</th><th>kcal MAE</th><th>Protein MAE</th><th>Carbs MAE</th><th>Fat MAE</th><th>Ingredient F1</th><th>HTTP attempts</th>
</tr></thead><tbody>{rows}</tbody></table></div><div class="status"><strong>{html.escape(selection['status'])}</strong> · {html.escape(str(selection['selected_method']))}<br>{html.escape(selection['reason'])}</div></section>
<section><h2>อ่านผลและตรวจที่มาของค่า</h2><ul>{note_html}</ul><p>
<a href="per_evaluation.csv">ผลรายภาพ/รอบ CSV</a> · <a href="ingredient_breakdown.csv">วัตถุดิบและสัดส่วน CSV</a> ·
<a href="summary_by_method_round.csv">สรุปแต่ละรอบ CSV</a> · <a href="winner_selection.json">ผลเลือก Agent JSON</a></p></section></main></html>'''
    (out / 'report.html').write_text(page, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Evaluate candidate trials using sealed local expected labels')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--truth', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.run_dir, args.truth)
    print(f"Evaluated {len(result['rows'])} planned trials; paired complete={result['paired_trials']}")
    print('Selection: ' + result['selection']['status'])
    print('Report: ' + str(args.run_dir / 'comparison/report.html'))


if __name__ == '__main__':
    main()
