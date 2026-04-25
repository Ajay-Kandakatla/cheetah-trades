"""Finalize graphify pipeline: cluster, label, viz, report, JSON."""
import json
from pathlib import Path
from collections import Counter
from graphify import build, cluster, export, report, analyze

OUT = Path("graphify-out")
merged = json.loads((OUT / ".graphify_merged.json").read_text())
detect = json.loads((OUT / ".graphify_detect.json").read_text())

G = build.build_from_json(merged, directed=False)
communities = cluster.cluster(G)
cohesion = cluster.score_all(G, communities)
gods = analyze.god_nodes(G, top_n=10)
surprises = analyze.surprising_connections(G, communities, top_n=5)

# Generate community labels — pick top label by frequency in each community
labels = {}
for cid, members in communities.items():
    member_labels = []
    for nid in members:
        if nid in G.nodes:
            lbl = G.nodes[nid].get("label", nid)
            # take first word/token as theme
            for tok in str(lbl).replace("_", " ").split():
                if len(tok) > 3:
                    member_labels.append(tok.lower())
    if member_labels:
        common = Counter(member_labels).most_common(1)[0][0]
        labels[cid] = f"Community {cid}: {common}"
    else:
        labels[cid] = f"Community {cid}"

questions = analyze.suggest_questions(G, communities, labels, top_n=7)

# Token cost
sem_new = json.loads((OUT / ".graphify_semantic_new.json").read_text()) if (OUT / ".graphify_semantic_new.json").exists() else {}
ast = json.loads((OUT / ".graphify_ast.json").read_text())
token_cost = {
    "input_tokens": ast.get("input_tokens", 0),
    "output_tokens": ast.get("output_tokens", 0),
}

# Export
export.to_json(G, communities, str(OUT / "graph.json"))
export.to_html(G, communities, str(OUT / "graph.html"), community_labels=labels)
md = report.generate(G, communities, cohesion, labels, gods, surprises, detection_result=detect, token_cost=token_cost, root=".", suggested_questions=questions)
(OUT / "GRAPH_REPORT.md").write_text(md)

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")
print(f"God nodes top 5: {[g['label'] for g in gods[:5]]}")
print("Outputs: graph.html, graph.json, GRAPH_REPORT.md")
