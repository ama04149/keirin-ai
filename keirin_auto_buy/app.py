from flask import Flask, render_template, request, redirect, url_for
import pandas as pd

app = Flask(__name__)

CSV_PATH = "keirin_race_summary.csv"


# CSV読み込み
def load_data():
    df = pd.read_csv(CSV_PATH)
    return df


# トップ画面
@app.route("/")
def index():

    df = load_data()

    # A率フィルタ
    a_filter = request.args.get("a_filter") == "1"

    if a_filter and "A率" in df.columns:
        df = df[df["A率"] < 0.8]

    races = df.values.tolist()

    return render_template(
        "index.html",
        races=races,
        a_filter=a_filter
    )


# 確認画面
@app.route("/confirm", methods=["POST"])
def confirm():

    df = load_data()

    selected = request.form.getlist("selected")

    if not selected:
        return redirect(url_for("index"))

    indices = list(map(int, selected))

    rows = df.loc[indices].values.tolist()

    return render_template(
        "confirm.html",
        rows=rows,
        indices=",".join(selected)
    )


# 購入処理
@app.route("/buy", methods=["POST"])
def buy():

    indices = request.form.get("indices")

    if not indices:
        return redirect(url_for("index"))

    df = load_data()

    index_list = list(map(int, indices.split(",")))

    results = []

    for i in index_list:

        row = df.iloc[i]

        first = str(row[6])  # 7カラム目
        box = str(row[7])    # 8カラム目

        digits = list(box)

        bets = []

        # 3連単生成
        for a in digits:
            for b in digits:
                for c in digits:
                    if len({a, b, c}) == 3 and a == first:
                        bet = f"{a}-{b}-{c}"
                        bets.append(bet)

        # 実際の投票処理はここに書く
        results.append({
            "race": row[0],
            "bets": bets
        })

    return render_template(
        "result.html",
        message=f"{len(results)}レースの購入処理を実行しました（ダミー）"
    )


if __name__ == "__main__":
    app.run(debug=True)