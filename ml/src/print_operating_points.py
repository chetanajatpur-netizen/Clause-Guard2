import json

with open("ml/artifacts/operating_points_abc.json") as f:
    d = json.load(f)

for m_key, m_name in [("model_a", "Model A (Positives + 3k Random Negatives)"), 
                      ("model_b", "Model B (Model A + 650 Hard Negatives, w=0.5)"), 
                      ("model_c", "Model C (Model A + 88 Verified Negatives, w=1.0)")]:
    print("\n" + "=" * 125)
    print(f"OPERATING-POINTS TABLE: {m_name}")
    print("=" * 125)
    header = (
        f"{'Target FA/c':<12} {'Actual FA/c':<12} {'Thresh':<8} {'Flags':<8} "
        f"{'FA':<6} {'TP':<6} {'Prec':<9} {'Overall Rec':<13} "
        f"{'Non-Compete':<13} {'Exclusivity':<13} {'Uncapped Liab':<15} {'Liq Damages'}"
    )
    print(header)
    print("-" * 125)
    rows = d[m_key]
    for r in rows:
        t_fa = r["target_fa_per_contract"]
        a_fa = r["actual_fa_per_contract"]
        t = r["threshold"]
        fl = r["flags"]
        fa = r["fa_count"]
        tp = r["tp_count"]
        pr = f"{r['precision'] * 100:.2f}%"
        rec = f"{r['overall_recall'] * 100:.2f}%"
        nc = f"{r['class_recalls']['Non-Compete'] * 100:.2f}%"
        exc = f"{r['class_recalls']['Exclusivity'] * 100:.2f}%"
        unc = f"{r['class_recalls']['Uncapped Liability'] * 100:.2f}%"
        ld = f"{r['class_recalls']['Liquidated Damages'] * 100:.2f}%"
        line = (
            f"{t_fa:<12.0f} {a_fa:<12.2f} {t:<8.3f} {fl:<8d} "
            f"{fa:<6d} {tp:<6d} {pr:<9} {rec:<13} "
            f"{nc:<13} {exc:<13} {unc:<15} {ld}"
        )
        print(line)
