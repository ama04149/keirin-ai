# save as analyze_keirin.py and run: python analyze_keirin.py
import pandas as pd
import numpy as np
import re
from pathlib import Path

INPUT_PATH = r"C:\Users\wolfs\Desktop\MergedWithFileName.csv"  # あなたのアップロードファイルパス
OUT_DIR = Path(r"C:\Users\wolfs\Desktop\data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_nums(s):
    if pd.isna(s): return []
    return re.findall(r'\d+', str(s))

def triple_eq_str(order):
    nums = parse_nums(order)
    return "-".join(nums) if nums else None

def race_no_to_int(x):
    if pd.isna(x): return 0
    m = re.search(r'(\d+)', str(x))
    return int(m.group(1)) if m else 0

def generate_tickets_A_eq_B_abcd(row):
    A=row['A']; B=row['B']; xs = list(row['abc_list']) + ([row['d']] if row['d'] else [])
    xs = [x for x in xs if x]
    tickets=set()
    if not A or not B:
        return tickets
    for x in xs:
        tickets.add(f"{A}-{B}-{x}")
        tickets.add(f"{B}-{A}-{x}")
    return tickets

def generate_tickets_with_CD(row):
    A=row['A']; B=row['B']
    xs = list(row['abc_list'])
    if row['d']: xs.append(row['d'])
    if row['C']: xs.append(row['C'])
    if row['D']: xs.append(row['D'])
    # dedupe while preserving order
    seen=set(); xs2=[]
    for x in xs:
        if x and x not in seen:
            xs2.append(x); seen.add(x)
    tickets=set()
    if not A or not B:
        return tickets
    for x in xs2:
        tickets.add(f"{A}-{B}-{x}")
        tickets.add(f"{B}-{A}-{x}")
    return tickets

def simulate_day(df_day, ticket_generator, stop_on_recovery120=False):
    df_day = df_day.sort_values('race_no').copy()
    cum_cost=0; cum_payout=0
    records=[]
    stopped=False
    for _, r in df_day.iterrows():
        if stop_on_recovery120 and cum_cost>0 and (cum_payout / cum_cost) > 1.2:
            stopped=True
            records.append({'race_index': r.name, 'bought': False, 'tickets': set(), 'cost':0, 'payout':0, 'hit':False})
            continue
        tickets = ticket_generator(r)
        cost = len(tickets) * 100
        hit=False; payout=0
        if tickets and r['actual']:
            if r['actual'] in tickets:
                hit=True
                payout = int(r['payout'])
        cum_cost += cost
        cum_payout += payout
        records.append({'race_index': r.name, 'bought': True, 'tickets': tickets, 'cost':cost, 'payout':payout, 'hit':hit})
    total_cost = sum(rec['cost'] for rec in records)
    total_payout = sum(rec['payout'] for rec in records)
    total_profit = total_payout - total_cost
    profit_rate = (total_profit / total_cost) if total_cost>0 else np.nan
    hit_count = sum(1 for rec in records if rec['hit'])
    total_tickets = sum(len(rec['tickets']) for rec in records)
    return {
        'records': records,
        'total_cost': total_cost,
        'total_payout': total_payout,
        'total_profit': total_profit,
        'profit_rate': profit_rate,
        'hit_count': hit_count,
        'total_tickets': total_tickets,
        'stopped_early': stopped
    }

def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8", low_memory=False)

    # normalize and parse useful columns
    df['score'] = pd.to_numeric(df['スコア'], errors='coerce')
    df['A'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['B'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[1] if len(parse_nums(s))>1 else None)
    df['C'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[2] if len(parse_nums(s))>2 else None)
    df['abc_list'] = df['3連単_3着以内'].apply(lambda s: parse_nums(s))
    df['d'] = df['3着以内_補欠'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['D'] = df['1着_補欠'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['actual'] = df['3連単_的中'].apply(triple_eq_str)
    df['payout'] = pd.to_numeric(df['3連単_配当金(円)'], errors='coerce').fillna(0).astype(int)
    df['race_no'] = df['レース番号'].apply(race_no_to_int)

    # filter by score range requested
    df_sf = df[(df['score']>=57.5) & (df['score']<=62.5)].copy()

    # 1) day-by-day simulation summaries (both strategies, with/without stop)
    days = sorted(df_sf['SourceFileName'].unique())
    day_summary_rows=[]
    for day in days:
        day_df = df_sf[df_sf['SourceFileName']==day]
        s1_no = simulate_day(day_df, generate_tickets_A_eq_B_abcd, stop_on_recovery120=False)
        s1_stop = simulate_day(day_df, generate_tickets_A_eq_B_abcd, stop_on_recovery120=True)
        s2_no = simulate_day(day_df, generate_tickets_with_CD, stop_on_recovery120=False)
        s2_stop = simulate_day(day_df, generate_tickets_with_CD, stop_on_recovery120=True)
        day_summary_rows.append({
            'day': day,
            's1_profit_no_stop': s1_no['total_profit'],
            's1_cost_no_stop': s1_no['total_cost'],
            's1_profit_rate_no_stop': s1_no['profit_rate'],
            's1_profit_stop': s1_stop['total_profit'],
            's1_cost_stop': s1_stop['total_cost'],
            's1_profit_rate_stop': s1_stop['profit_rate'],
            's2_profit_no_stop': s2_no['total_profit'],
            's2_cost_no_stop': s2_no['total_cost'],
            's2_profit_rate_no_stop': s2_no['profit_rate'],
            's2_profit_stop': s2_stop['total_profit'],
            's2_cost_stop': s2_stop['total_cost'],
            's2_profit_rate_stop': s2_stop['profit_rate'],
        })
    day_summary = pd.DataFrame(day_summary_rows).sort_values('day')
    day_summary.to_csv(OUT_DIR / 'analysis_day_summary.csv', index=False, encoding='utf-8-sig')

    # 2) score別の利益率分布（scoreを小数第1位で丸めて集計）
    df_sf['score_round1'] = df_sf['score'].round(1)

    # per-row profit for strategies (no stop)
    def per_row_result(row, ticket_gen):
        tickets = ticket_gen(row)
        cost = len(tickets)*100
        payout = 0
        hit = False
        if tickets and row['actual'] and row['actual'] in tickets:
            hit=True
            payout = row['payout']
        profit = payout - cost
        return pd.Series({'cost':cost,'payout':payout,'profit':profit,'hit':hit,'n_tickets':len(tickets)})

    per1 = df_sf.apply(lambda r: per_row_result(r, generate_tickets_A_eq_B_abcd), axis=1)
    per2 = df_sf.apply(lambda r: per_row_result(r, generate_tickets_with_CD), axis=1)
    df_sf[['cost_s1','payout_s1','profit_s1','hit_s1','n_tix_s1']] = per1
    df_sf[['cost_s2','payout_s2','profit_s2','hit_s2','n_tix_s2']] = per2

    # 修正後のコード (total_cost_s1とtotal_profit_s1を使って利益率を後で計算)
    score_dist = df_sf.groupby('score_round1').agg(
        races=('競輪場','size'),
        total_cost_s1=('cost_s1','sum'),
        total_profit_s1=('profit_s1','sum'),
        hit_rate_s1=('hit_s1','mean'),
        # avg_payout_on_hit_s1 は同様に外部参照しているので、修正が必要です
        # これもグループ内で完結するように修正
        payout_on_hit_sum_s1=('payout_s1', lambda x: x[df_sf.loc[x.index, 'hit_s1']].sum()),
        hit_count_s1=('hit_s1', 'sum')

    ).reset_index().sort_values('score_round1')

    # 集計後に利益率と平均配当を計算 (外部データフレーム参照の回避)
    score_dist['profit_rate_s1'] = np.where(
        score_dist['total_cost_s1'] > 0,
        score_dist['total_profit_s1'] / score_dist['total_cost_s1'],
        np.nan
    )
    score_dist['avg_payout_on_hit_s1'] = np.where(
        score_dist['hit_count_s1'] > 0,
        score_dist['payout_on_hit_sum_s1'] / score_dist['hit_count_s1'],
        np.nan
    )
    # 不要な中間列を削除
    score_dist = score_dist.drop(columns=['payout_on_hit_sum_s1', 'hit_count_s1'])
    score_dist.to_csv(OUT_DIR / 'analysis_score_distribution.csv', index=False, encoding='utf-8-sig')

    # 3) 競輪場ごとの利益率（no-stop and stop）
    venues = df_sf['競輪場'].unique()
    venue_rows=[]
    for v in venues:
        vdf = df_sf[df_sf['競輪場']==v]
        tp1 = vdf['profit_s1'].sum(); tc1 = vdf['cost_s1'].sum()
        pr1 = tp1/tc1 if tc1>0 else np.nan
        hr1 = vdf['hit_s1'].mean()
        ap1 = vdf[vdf['hit_s1']]['payout_s1'].mean() if vdf['hit_s1'].any() else np.nan

        tp2 = vdf['profit_s2'].sum(); tc2 = vdf['cost_s2'].sum()
        pr2 = tp2/tc2 if tc2>0 else np.nan
        hr2 = vdf['hit_s2'].mean()
        ap2 = vdf[vdf['hit_s2']]['payout_s2'].mean() if vdf['hit_s2'].any() else np.nan

        # stop rule aggregated across days for this venue
        stop_profit_s1=stop_cost_s1=0
        stop_profit_s2=stop_cost_s2=0
        for d in vdf['SourceFileName'].unique():
            ddf = df_sf[df_sf['SourceFileName']==d]
            r1 = simulate_day(ddf, generate_tickets_A_eq_B_abcd, stop_on_recovery120=True)
            r2 = simulate_day(ddf, generate_tickets_with_CD, stop_on_recovery120=True)
            stop_profit_s1 += r1['total_profit']; stop_cost_s1 += r1['total_cost']
            stop_profit_s2 += r2['total_profit']; stop_cost_s2 += r2['total_cost']

        venue_rows.append({
            'venue': v,
            'profit_s1_no_stop': tp1, 'cost_s1_no_stop': tc1, 'profit_rate_s1_no_stop': pr1, 'hit_rate_s1_no_stop': hr1, 'avg_payout_hit_s1': ap1,
            'profit_s2_no_stop': tp2, 'cost_s2_no_stop': tc2, 'profit_rate_s2_no_stop': pr2, 'hit_rate_s2_no_stop': hr2, 'avg_payout_hit_s2': ap2,
            'profit_s1_stop': stop_profit_s1, 'cost_s1_stop': stop_cost_s1, 'profit_rate_s1_stop': (stop_profit_s1/stop_cost_s1 if stop_cost_s1>0 else np.nan),
            'profit_s2_stop': stop_profit_s2, 'cost_s2_stop': stop_cost_s2, 'profit_rate_s2_stop': (stop_profit_s2/stop_cost_s2 if stop_cost_s2>0 else np.nan)
        })
    venue_df = pd.DataFrame(venue_rows).sort_values('venue')
    venue_df.to_csv(OUT_DIR / 'analysis_venue_summary.csv', index=False, encoding='utf-8-sig')

    # 4) 的中率・平均配当の統計（全体）
    overall = {
        's1_total_races': df_sf.shape[0],
        's1_total_hits': df_sf['hit_s1'].sum(),
        's1_hit_rate': df_sf['hit_s1'].mean(),
        's1_avg_payout_on_hit': df_sf.loc[df_sf['hit_s1'],'payout_s1'].mean() if df_sf['hit_s1'].any() else np.nan,
        's2_total_hits': df_sf['hit_s2'].sum(),
        's2_hit_rate': df_sf['hit_s2'].mean(),
        's2_avg_payout_on_hit': df_sf.loc[df_sf['hit_s2'],'payout_s2'].mean() if df_sf['hit_s2'].any() else np.nan
    }
    pd.DataFrame([overall]).to_csv(OUT_DIR / 'analysis_overall_stats.csv', index=False, encoding='utf-8-sig')

    print("完了しました。出力ファイル：")
    print(OUT_DIR / 'analysis_day_summary.csv')
    print(OUT_DIR / 'analysis_score_distribution.csv')
    print(OUT_DIR / 'analysis_venue_summary.csv')
    print(OUT_DIR / 'analysis_overall_stats.csv')

if __name__ == "__main__":
    main()
