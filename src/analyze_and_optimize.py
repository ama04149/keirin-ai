# analyze_and_optimize.py
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
from scipy import stats
from math import fabs

plt.rcParams['font.size'] = 10

# ---- ユーティリティ ----
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

def tickets_s1(row):
    A = row['A']; B = row['B']
    xs = list(row['abc_list']) + ([row['d']] if row['d'] else [])
    xs = [x for x in xs if x]
    t=set()
    if not A or not B: return t
    for x in xs:
        t.add(f"{A}-{B}-{x}")
        t.add(f"{B}-{A}-{x}")
    return t

def tickets_s2(row):
    A = row['A']; B = row['B']
    xs = list(row['abc_list'])
    if row['d']: xs.append(row['d'])
    if row['C']: xs.append(row['C'])
    if row['D']: xs.append(row['D'])
    seen=set(); xs2=[]
    for x in xs:
        if x and x not in seen:
            xs2.append(x); seen.add(x)
    t=set()
    if not A or not B: return t
    for x in xs2:
        t.add(f"{A}-{B}-{x}")
        t.add(f"{B}-{A}-{x}")
    return t

# ---- per-row 計算 ----
def per_row_result(row, ticket_gen):
    t = ticket_gen(row)
    cost = len(t)*100
    payout = 0
    hit = False
    if t and row['actual'] and row['actual'] in t:
        hit = True
        payout = int(row['payout'])
    profit = payout - cost
    return cost, payout, profit, hit, len(t)

# ---- simulate 日ごと（停止ルールを逐次適用可能） ----
def simulate_day(df_day, ticket_gen, stop_on_recovery120=False, filter_scores=None):
    df_day = df_day.sort_values('race_no').copy()
    cum_cost=0; cum_payout=0
    records=[]
    stopped=False
    for _, r in df_day.iterrows():
        if filter_scores is not None and round(r['score'],1) not in filter_scores:
            records.append({'race_no': r['race_no'], 'bought': False, 'cost':0, 'payout':0, 'hit':False})
            continue
        if stop_on_recovery120 and cum_cost>0 and (cum_payout / cum_cost) > 1.2:
            stopped=True
            records.append({'race_no': r['race_no'], 'bought': False, 'cost':0, 'payout':0, 'hit':False})
            continue
        cost, payout, profit, hit, n = per_row_result(r, ticket_gen)
        cum_cost += cost; cum_payout += payout
        records.append({'race_no': r['race_no'], 'bought': True, 'cost':cost, 'payout':payout, 'hit':hit})
    total_cost = sum([x['cost'] for x in records])
    total_payout = sum([x['payout'] for x in records])
    total_profit = total_payout - total_cost
    profit_rate = total_profit/total_cost if total_cost>0 else np.nan
    hit_count = sum([1 for x in records if x['hit']])
    total_tickets = sum([x['cost']/100 for x in records])
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

# ---- main ----
def main(input_path, out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(input_path, encoding='utf-8', low_memory=False)

    # 必要列整形
    df['score'] = pd.to_numeric(df['スコア'], errors='coerce')
    df = df[(df['score']>=57.5) & (df['score']<=62.5)].copy()
    df['A'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['B'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[1] if len(parse_nums(s))>1 else None)
    df['C'] = df['3連単_1着'].apply(lambda s: parse_nums(s)[2] if len(parse_nums(s))>2 else None)
    df['abc_list'] = df['3連単_3着以内'].apply(lambda s: parse_nums(s))
    df['d'] = df['3着以内_補欠'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['D'] = df['1着_補欠'].apply(lambda s: parse_nums(s)[0] if parse_nums(s) else None)
    df['actual'] = df['3連単_的中'].apply(triple_eq_str)
    df['payout'] = pd.to_numeric(df['3連単_配当金(円)'], errors='coerce').fillna(0).astype(int)
    df['race_no'] = df['レース番号'].apply(race_no_to_int)
    df['score_round1'] = df['score'].round(1)

    # --- スコア別の集計（s1） ---
    rows=[]
    for score, g in df.groupby('score_round1'):
        total_cost=0; total_profit=0; hits=0; payouts=[]
        for _, r in g.iterrows():
            c,p,pr,h,n = per_row_result(r, tickets_s1)
            total_cost += c; total_profit += pr
            if h:
                hits += 1; payouts.append(p)
        profit_rate = total_profit / total_cost if total_cost>0 else np.nan
        avg_payout = np.mean(payouts) if payouts else np.nan
        rows.append({'score_round1':score,'races':len(g),'total_cost_s1':total_cost,'total_profit_s1':total_profit,
                     'hit_rate_s1': hits/len(g) if len(g)>0 else np.nan,'profit_rate_s1':profit_rate,'avg_payout_on_hit_s1':avg_payout})
    score_dist = pd.DataFrame(rows).sort_values('score_round1')
    score_dist.to_csv(out_dir / "score_dist_s1.csv", index=False, encoding='utf-8-sig')

    # ---- プロット: スコア vs profit_rate, hit_rate ----
    plt.figure(figsize=(8,4))
    plt.plot(score_dist['score_round1'], score_dist['profit_rate_s1'], marker='o')
    plt.axhline(0, color='gray', linestyle='--')
    plt.title('Score vs Profit Rate (s1)')
    plt.xlabel('Score')
    plt.ylabel('Profit Rate')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_dir / "score_profit_rate_s1.png")
    plt.close()

    plt.figure(figsize=(8,4))
    plt.plot(score_dist['score_round1'], score_dist['hit_rate_s1'], marker='o')
    plt.title('Score vs Hit Rate (s1)')
    plt.xlabel('Score')
    plt.ylabel('Hit Rate')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_dir / "score_hit_rate_s1.png")
    plt.close()

    # ---- s1 vs s2 の有意差検定 ----
    per_rows=[]
    for idx,r in df.iterrows():
        c1,p1,pr1,h1,n1 = per_row_result(r, tickets_s1)
        c2,p2,pr2,h2,n2 = per_row_result(r, tickets_s2)
        per_rows.append({'index':idx,'hit_s1':h1,'hit_s2':h2,'payout_s1':p1,'payout_s2':p2,'n1':n1,'n2':n2})
    per_df = pd.DataFrame(per_rows)
    # ① McNemar (paired binary test) — only counts
    b01 = sum((per_df['hit_s1']==0) & (per_df['hit_s2']==1))
    b10 = sum((per_df['hit_s1']==1) & (per_df['hit_s2']==0))
    mcnemar_stat = (fabs(b01-b10)-1)**2 / (b01+b10) if (b01+b10)>0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar_stat, df=1) if (b01+b10)>0 else 1.0

    # ② Payout distribution: Mann-Whitney U Test (nonparametric)
    u_stat, p_u = stats.mannwhitneyu(per_df['payout_s1'], per_df['payout_s2'], alternative='two-sided')

    # ---- 日別停止ルール効果の検出（s1） ----
    days = sorted(df['SourceFileName'].unique())
    day_effects=[]
    for day in days:
        day_df = df[df['SourceFileName']==day]
        res_no = simulate_day(day_df, tickets_s1, stop_on_recovery120=False)
        res_stop = simulate_day(day_df, tickets_s1, stop_on_recovery120=True)
        day_effects.append({'day':day,'profit_no_stop':res_no['total_profit'],'profit_stop':res_stop['total_profit'],
                            'cost_no_stop':res_no['total_cost'],'cost_stop':res_stop['total_cost'],
                            'effect': res_stop['total_profit'] > res_no['total_profit']})
    day_effect_df = pd.DataFrame(day_effects)
    day_effect_df.to_csv(out_dir / "day_effects_s1.csv", index=False, encoding='utf-8-sig')

    # ---- 累積損益推移プロット（s1 no_stop vs s1 stop） ----
    day_summary=[]
    for day in days:
        day_df = df[df['SourceFileName']==day]
        r_no = simulate_day(day_df, tickets_s1, stop_on_recovery120=False)
        r_stop = simulate_day(day_df, tickets_s1, stop_on_recovery120=True)
        day_summary.append({'day':day,'profit_no':r_no['total_profit'],'profit_stop':r_stop['total_profit']})
    day_summary_df = pd.DataFrame(day_summary)
    # convert day filename to date if possible
    def day_to_date(s):
        m = re.search(r'(\d{8})', s)
        if m:
            return pd.to_datetime(m.group(1), format='%Y%m%d')
        return pd.NaT
    day_summary_df['date'] = day_summary_df['day'].apply(day_to_date)
    day_summary_df = day_summary_df.sort_values('date')
    # cumulative
    day_summary_df['cum_no'] = day_summary_df['profit_no'].cumsum()
    day_summary_df['cum_stop'] = day_summary_df['profit_stop'].cumsum()
    plt.figure(figsize=(10,4))
    plt.plot(day_summary_df['date'], day_summary_df['cum_no'], marker='o', label='s1 no_stop')
    plt.plot(day_summary_df['date'], day_summary_df['cum_stop'], marker='o', label='s1 stop')
    plt.legend(); plt.grid(True); plt.title('Cumulative Profit s1'); plt.tight_layout()
    plt.savefig(out_dir / "cumulative_profit_s1.png"); plt.close()
    day_summary_df.to_csv(out_dir / "day_summary_s1.csv", index=False, encoding='utf-8-sig')

    # ---- 120%停止の発動レース一覧（s1） ----
    trigger_rows=[]
    for day, g in df.groupby('SourceFileName'):
        g_sorted = g.sort_values('race_no')
        cum_cost=0; cum_payout=0; triggered=False
        for _, r in g_sorted.iterrows():
            t = tickets_s1(r)
            cost = len(t)*100
            payout = 0
            if t and r['actual'] and r['actual'] in t:
                payout = r['payout']
            cum_cost += cost; cum_payout += payout
            if not triggered and cum_cost>0 and (cum_payout/cum_cost) > 1.2:
                trigger_rows.append({'day':day,'trigger_race_no':r['race_no'],'cum_cost':cum_cost,'cum_payout':cum_payout,'ratio':cum_payout/cum_cost})
                triggered=True
                break
        if not triggered:
            trigger_rows.append({'day':day,'trigger_race_no':None,'cum_cost':cum_cost,'cum_payout':cum_payout,'ratio':(cum_payout/cum_cost if cum_cost>0 else 0)})
    trigger_df = pd.DataFrame(trigger_rows)
    trigger_df.to_csv(out_dir / "stop_triggers_s1.csv", index=False, encoding='utf-8-sig')

    # ---- 改善案: "スコア帯選択 + 120%停止" の簡易バックテスト ----
    # スコア帯のうち profit_rate_s1 > 0 を選ぶ（改善案の一例）
    pos_scores = score_dist[score_dist['profit_rate_s1']>0]['score_round1'].tolist()
    # policy simulation across days
    policy_rows=[]
    for day, g in df.groupby('SourceFileName'):
        g_sorted = g.sort_values('race_no')
        cum_cost=0; cum_payout=0; stopped=False
        for _, r in g_sorted.iterrows():
            if round(r['score'],1) not in pos_scores:
                policy_rows.append({'day':day,'race_no':r['race_no'],'bought':False,'cost':0,'payout':0,'hit':False})
                continue
            if not stopped and cum_cost>0 and (cum_payout/cum_cost)>1.2:
                stopped=True
                policy_rows.append({'day':day,'race_no':r['race_no'],'bought':False,'cost':0,'payout':0,'hit':False})
                continue
            t = tickets_s1(r)
            cost = len(t)*100
            payout = 0; hit=False
            if t and r['actual'] and r['actual'] in t:
                payout=r['payout']; hit=True
            cum_cost += cost; cum_payout += payout
            policy_rows.append({'day':day,'race_no':r['race_no'],'bought':True,'cost':cost,'payout':payout,'hit':hit})
    policy_df = pd.DataFrame(policy_rows)
    policy_summary = policy_df.groupby('day').agg(total_cost=('cost','sum'), total_payout=('payout','sum'))
    policy_summary['profit'] = policy_summary['total_payout'] - policy_summary['total_cost']
    policy_summary['profit_rate'] = policy_summary['profit'] / policy_summary['total_cost']
    policy_summary.to_csv(out_dir / "policy_summary.csv", encoding='utf-8-sig')

    # ---- summary outputs ----
    score_dist.to_csv(out_dir / "score_dist_full.csv", index=False, encoding='utf-8-sig')
    per_df.to_csv(out_dir / "per_race_hits.csv", index=False, encoding='utf-8-sig')
    # test stats to text
    with open(out_dir / "stat_tests.txt", "w", encoding="utf-8") as f:
        f.write(f"McNemar b01 (s1=0,s2=1)={b01}, b10 (s1=1,s2=0)={b10}\n")
        f.write(f"McNemar approx stat={mcnemar_stat:.4f}, p-value={p_mcnemar:.6f}\n")
        f.write(f"Mann-Whitney U on payouts: U={u_stat}, p-value={p_u:.6f}\n")

    print("Outputs saved to", out_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='input merged csv path')
    parser.add_argument('--out', required=True, help='output directory')
    args = parser.parse_args()
    main(args.input, args.out)