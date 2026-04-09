# assemble node+edge dicts into a NetworkX graph, preserving edge direction
#
# Node deduplication — three layers:
#
# 1. Within a file (AST): each extractor tracks a `seen_ids` set. A node ID is
#    emitted at most once per file, so duplicate class/function definitions in
#    the same source file are collapsed to the first occurrence.
#
# 2. Between files (build): NetworkX G.add_node() is idempotent — calling it
#    twice with the same ID overwrites the attributes with the second call's
#    values. Nodes are added in extraction order (AST first, then semantic),
#    so if the same entity is extracted by both passes the semantic node
#    silently overwrites the AST node. This is intentional: semantic nodes
#    carry richer labels and cross-file context, while AST nodes have precise
#    source_location. If you need to change the priority, reorder extractions
#    passed to build().
#
# 3. Semantic merge (skill): before calling build(), the skill merges cached
#    and new semantic results using an explicit `seen` set keyed on node["id"],
#    so duplicates across cache hits and new extractions are resolved there
#    before any graph construction happens.
#
from __future__ import annotations
import re
import sys
from pathlib import Path
import networkx as nx
from .validate import validate_extraction

_CODE_EXTENSIONS = {
    "py", "ts", "tsx", "js", "go", "rs", "java", "rb", "cpp", "c",
    "h", "cs", "kt", "scala", "php", "cc", "cxx", "hpp", "swift",
}
_FILE_REFERENCE_EXTENSIONS = {"py", "ts", "tsx", "js", "json", "yaml", "yml", "md", "sql", "toml"}
_DOC_WRAPPER_TOKENS = {
    "prompt", "handover", "decision", "template", "persona",
    "rubric", "framework", "report", "plan", "session", "doc",
}


def _source_ext(path: str) -> str:
    name = Path(path).name
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _tokenize_label(label: str) -> list[str]:
    if not label:
        return []
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(label))
    for ch in ("_", "-", "/", ".", ":", "[", "]", "(", ")"):
        text = text.replace(ch, " ")
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return [token for token in text.split() if token and not token.isdigit()]


def _is_test_path(path: str) -> bool:
    return "/tests/" in path or path.startswith("tests/")


def _is_file_hub(node: dict) -> bool:
    label = node.get("label", "")
    source_file = node.get("source_file", "")
    return bool(source_file) and label == Path(source_file).name


def _is_private_function(node: dict) -> bool:
    label = node.get("label", "")
    return label.startswith("_") and label.endswith("()")


def _is_method_stub(node: dict) -> bool:
    label = node.get("label", "")
    return label.startswith(".") and label.endswith("()")


def _looks_like_file_reference(label: str) -> bool:
    return bool(re.search(r"\.(?:" + "|".join(sorted(_FILE_REFERENCE_EXTENSIONS)) + r")\b", label.lower()))


def _is_doc_wrapper(node: dict) -> bool:
    tokens = set(_tokenize_label(node.get("label", "")))
    return node.get("id", "").endswith("_doc") or bool(tokens & _DOC_WRAPPER_TOKENS)


def _candidate_structural_nodes(nodes: list[dict]) -> list[tuple[str, set[str]]]:
    candidates: list[tuple[str, set[str]]] = []
    for node in nodes:
        if node.get("file_type") != "code":
            continue
        source_file = node.get("source_file", "")
        if not source_file or _is_test_path(source_file):
            continue
        if _is_file_hub(node) or _is_method_stub(node) or _is_private_function(node):
            continue
        tokens = set(_tokenize_label(node.get("label", "")))
        if len(tokens) < 2:
            continue
        candidates.append((node["id"], tokens))
    return candidates


def _candidate_file_nodes(nodes: list[dict]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    for node in nodes:
        if node.get("file_type") != "code" or not _is_file_hub(node):
            continue
        source_file = node.get("source_file", "")
        if not source_file:
            continue
        name = Path(source_file).name.lower()
        stem = Path(source_file).stem.lower()
        matches.setdefault(name, []).append(node["id"])
        matches.setdefault(stem, []).append(node["id"])
    return matches


def _alignment_plan(extraction: dict) -> tuple[dict[str, str], list[dict], dict[str, int]]:
    nodes = extraction.get("nodes", [])
    structural_candidates = _candidate_structural_nodes(nodes)
    file_candidates = _candidate_file_nodes(nodes)

    canonical_map: dict[str, str] = {}
    bridge_edges: list[dict] = []
    stats = {"canonicalized_nodes": 0, "bridge_edges": 0, "file_reference_nodes": 0}

    for node in nodes:
        source_file = node.get("source_file", "")
        if node.get("file_type") == "code" or _source_ext(source_file) in _CODE_EXTENSIONS:
            continue

        label = node.get("label", "")
        label_lower = label.lower()

        # Exact file references are the safest case - fold them into the file hub.
        if _looks_like_file_reference(label):
            file_matches: list[str] = []
            for key, ids in file_candidates.items():
                if key and key in label_lower:
                    file_matches.extend(ids)
            file_matches = list(dict.fromkeys(file_matches))
            if len(file_matches) == 1:
                canonical_map[node["id"]] = file_matches[0]
                stats["canonicalized_nodes"] += 1
                stats["file_reference_nodes"] += 1
                continue

        semantic_tokens = set(_tokenize_label(label))
        if len(semantic_tokens) < 2:
            continue

        scored: list[tuple[float, str, set[str]]] = []
        for candidate_id, candidate_tokens in structural_candidates:
            overlap = len(semantic_tokens & candidate_tokens)
            if overlap < 2:
                continue
            containment = min(overlap / len(candidate_tokens), overlap / len(semantic_tokens))
            jaccard = overlap / len(semantic_tokens | candidate_tokens)
            bonus = 0.0
            if candidate_tokens <= semantic_tokens or semantic_tokens <= candidate_tokens:
                bonus += 0.4
            if semantic_tokens == candidate_tokens:
                bonus += 1.0
            score = jaccard + containment + bonus
            if score >= 1.35:
                scored.append((score, candidate_id, candidate_tokens))

        scored.sort(reverse=True)
        if not scored:
            continue
        if len(scored) > 1 and (scored[0][0] - scored[1][0]) < 0.2:
            continue

        top_score, target_id, target_tokens = scored[0]
        if semantic_tokens == target_tokens and not _is_doc_wrapper(node):
            canonical_map[node["id"]] = target_id
            stats["canonicalized_nodes"] += 1
            continue

        bridge_edges.append(
            {
                "source": node["id"],
                "target": target_id,
                "relation": "references",
                "confidence": "INFERRED",
                "confidence_score": round(min(0.95, max(0.7, top_score / 2.5)), 2),
                "source_file": source_file,
                "source_location": None,
                "weight": 0.85,
            }
        )
        stats["bridge_edges"] += 1

    return canonical_map, bridge_edges, stats


def _reconcile_extraction(extraction: dict) -> dict:
    canonical_map, bridge_edges, stats = _alignment_plan(extraction)
    if not canonical_map and not bridge_edges:
        return extraction

    alias_map: dict[str, set[str]] = {}
    remapped_nodes: list[dict] = []
    seen_nodes: set[str] = set()

    for node in extraction.get("nodes", []):
        canonical_id = canonical_map.get(node["id"], node["id"])
        if canonical_id != node["id"]:
            alias_map.setdefault(canonical_id, set()).add(node.get("label", node["id"]))
            continue
        if canonical_id in seen_nodes:
            continue
        remapped_nodes.append(dict(node))
        seen_nodes.add(canonical_id)

    for node in remapped_nodes:
        aliases = sorted(alias_map.get(node["id"], set()) - {node.get("label")})
        if aliases:
            existing = set(node.get("aliases", []))
            node["aliases"] = sorted(existing | set(aliases))

    remapped_edges: list[dict] = []
    seen_edges: set[tuple[str, str, str, str | None, str | None]] = set()

    def _append_edge(edge: dict) -> None:
        source = canonical_map.get(edge["source"], edge["source"])
        target = canonical_map.get(edge["target"], edge["target"])
        if source == target:
            return
        new_edge = dict(edge)
        new_edge["source"] = source
        new_edge["target"] = target
        edge_key = (
            min(source, target),
            max(source, target),
            new_edge.get("relation", ""),
            new_edge.get("source_file"),
            new_edge.get("source_location"),
        )
        if edge_key in seen_edges:
            return
        seen_edges.add(edge_key)
        remapped_edges.append(new_edge)

    for edge in extraction.get("edges", []):
        _append_edge(edge)
    for edge in bridge_edges:
        _append_edge(edge)

    remapped_hyperedges: list[dict] = []
    for hyperedge in extraction.get("hyperedges", []):
        nodes = [canonical_map.get(node_id, node_id) for node_id in hyperedge.get("nodes", [])]
        deduped_nodes = list(dict.fromkeys(nodes))
        if len(deduped_nodes) < 3:
            continue
        new_hyperedge = dict(hyperedge)
        new_hyperedge["nodes"] = deduped_nodes
        remapped_hyperedges.append(new_hyperedge)

    updated = dict(extraction)
    updated["nodes"] = remapped_nodes
    updated["edges"] = remapped_edges
    updated["hyperedges"] = remapped_hyperedges
    updated["alignment"] = stats
    return updated


def build_from_json(extraction: dict) -> nx.Graph:
    extraction = _reconcile_extraction(extraction)
    errors = validate_extraction(extraction)
    # Dangling edges (stdlib/external imports) are expected - only warn about real schema errors.
    real_errors = [e for e in errors if "does not match any node id" not in e]
    if real_errors:
        print(f"[graphify] Extraction warning ({len(real_errors)} issues): {real_errors[0]}", file=sys.stderr)
    G = nx.Graph()
    for node in extraction.get("nodes", []):
        G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
    node_set = set(G.nodes())
    for edge in extraction.get("edges", []):
        src, tgt = edge["source"], edge["target"]
        if src not in node_set or tgt not in node_set:
            continue  # skip edges to external/stdlib nodes - expected, not an error
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        # Preserve original edge direction - undirected graphs lose it otherwise,
        # causing display functions to show edges backwards.
        attrs["_src"] = src
        attrs["_tgt"] = tgt
        G.add_edge(src, tgt, **attrs)
    hyperedges = extraction.get("hyperedges", [])
    if hyperedges:
        G.graph["hyperedges"] = hyperedges
    if extraction.get("alignment"):
        G.graph["alignment"] = extraction["alignment"]
    return G


def build(extractions: list[dict]) -> nx.Graph:
    """Merge multiple extraction results into one graph.

    Extractions are merged in order. For nodes with the same ID, the last
    extraction's attributes win (NetworkX add_node overwrites). Pass AST
    results before semantic results so semantic labels take precedence, or
    reverse the order if you prefer AST source_location precision to win.
    """
    combined: dict = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
    for ext in extractions:
        combined["nodes"].extend(ext.get("nodes", []))
        combined["edges"].extend(ext.get("edges", []))
        combined["hyperedges"].extend(ext.get("hyperedges", []))
        combined["input_tokens"] += ext.get("input_tokens", 0)
        combined["output_tokens"] += ext.get("output_tokens", 0)
    return build_from_json(combined)
