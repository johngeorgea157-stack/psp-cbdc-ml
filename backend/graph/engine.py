import networkx as nx


def build_graph(df):
    G = nx.DiGraph()
    for _, row in df.iterrows():
        f = row.get("from_wallet")
        t = row.get("to_wallet")
        if f is None or t is None:
            continue
        G.add_edge(
            f, t, amount=float(row.get("amount", 0)), currency=row.get("currency")
        )
    return G


def graph_risk(G, node):
    out_amt = sum((d.get("amount", 0) for _, _, d in G.out_edges(node, data=True)))
    in_amt = sum((d.get("amount", 0) for _, _, d in G.in_edges(node, data=True)))

    score = 0.0
    if out_amt > 1_000_000:
        score += 1.0
    if in_amt > 1_000_000:
        score += 1.0
    if out_amt > in_amt * 2 and out_amt > 0:
        score += 0.5

    return round(score, 4)
