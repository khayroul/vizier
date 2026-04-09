"""Shared query and navigation helpers for graphify graphs."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Iterable

import networkx as nx

from graphify.analyze import _is_annotation_node, _is_concept_node, _is_file_node
from graphify.security import sanitize_label


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _split_camel(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return text.replace("_", " ").replace("-", " ")


def _tokenize(text: str) -> list[str]:
    split = _split_camel(text)
    return [tok.lower() for tok in _TOKEN_RE.findall(split) if tok]


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokenize(text))


def _term_variants(term: str) -> set[str]:
    variants = {term}
    if len(term) > 4 and term.endswith("s"):
        variants.add(term[:-1])
    if len(term) > 5 and term.endswith("es"):
        variants.add(term[:-2])
    if len(term) > 5 and term.endswith("ing"):
        variants.add(term[:-3])
    return {v for v in variants if v}


def _edge_direction(G: nx.Graph, u: str, v: str) -> tuple[str, str]:
    data = G.edges[u, v]
    return data.get("_src", u), data.get("_tgt", v)


def _edge_to_text(G: nx.Graph, u: str, v: str) -> str:
    data = G.edges[u, v]
    src_id, tgt_id = _edge_direction(G, u, v)
    src_label = sanitize_label(G.nodes[src_id].get("label", src_id))
    tgt_label = sanitize_label(G.nodes[tgt_id].get("label", tgt_id))
    relation = data.get("relation", "related_to")
    confidence = data.get("confidence", "")
    return f"EDGE {src_label} --{relation} [{confidence}]--> {tgt_label}"


def _node_weight(G: nx.Graph, node_id: str) -> float:
    degree = G.degree(node_id)
    weight = min(degree, 12) * 0.05
    source_file = str(G.nodes[node_id].get("source_file", ""))
    if source_file.startswith("tests/") or "/tests/" in source_file:
        weight -= 0.8
    if _is_file_node(G, node_id):
        weight -= 2.0
    if _is_annotation_node(G, node_id):
        weight -= 2.5
    if _is_concept_node(G, node_id):
        weight -= 0.6
    return weight


def score_nodes(G: nx.Graph, query: str | Iterable[str], limit: int | None = None) -> list[tuple[float, str]]:
    """Rank nodes for a natural-language query."""
    if isinstance(query, str):
        query_text = query
        terms = [t for t in _tokenize(query) if len(t) > 1]
    else:
        terms = [str(t).lower() for t in query if str(t).strip()]
        query_text = " ".join(terms)

    phrase = _normalize_phrase(query_text)
    scored: list[tuple[float, str]] = []

    for node_id, data in G.nodes(data=True):
        label = data.get("label", "")
        aliases = [str(alias) for alias in data.get("aliases", []) if str(alias).strip()]
        source = data.get("source_file", "")
        label_phrase = _normalize_phrase(label)
        alias_phrases = [_normalize_phrase(alias) for alias in aliases]
        id_phrase = _normalize_phrase(node_id)
        source_phrase = _normalize_phrase(source)
        label_tokens = set(_tokenize(label)) | set(_tokenize(node_id))
        for alias in aliases:
            label_tokens.update(_tokenize(alias))
        source_tokens = set(_tokenize(source))

        score = 0.0
        matched_terms = 0

        if phrase:
            if label_phrase == phrase:
                score += 18.0
            elif any(alias_phrase == phrase for alias_phrase in alias_phrases):
                score += 16.0
            elif id_phrase == phrase:
                score += 16.0
            elif phrase in label_phrase:
                score += 10.0
            elif any(phrase in alias_phrase for alias_phrase in alias_phrases):
                score += 8.5
            elif phrase in id_phrase:
                score += 8.0
            elif phrase in source_phrase:
                score += 5.0

        for term in terms:
            variants = _term_variants(term)
            local = 0.0
            if any(v in label_tokens for v in variants):
                local = 3.0
            elif any(v in label_phrase for v in variants):
                local = 2.0
            elif any(v in alias_phrase for alias_phrase in alias_phrases for v in variants):
                local = 1.75
            elif any(v in source_tokens for v in variants):
                local = 1.25
            elif any(v in source_phrase for v in variants):
                local = 0.75
            score += local
            if local > 0:
                matched_terms += 1

        if terms:
            coverage = matched_terms / len(terms)
            score += coverage * 5.0
            if matched_terms == len(terms):
                score += 4.0

        score += _node_weight(G, node_id)

        if score > 0:
            scored.append((round(score, 4), node_id))

    scored.sort(
        key=lambda item: (
            -item[0],
            len(G.nodes[item[1]].get("label", item[1])),
            G.nodes[item[1]].get("label", item[1]).lower(),
        )
    )
    if limit is not None:
        return scored[:limit]
    return scored


def find_nodes(G: nx.Graph, query: str, limit: int = 5) -> list[str]:
    """Return the best-matching node IDs for a query."""
    seen_labels: set[str] = set()
    matches: list[str] = []
    for _, node_id in score_nodes(G, query):
        label_key = G.nodes[node_id].get("label", node_id).lower()
        if label_key in seen_labels:
            continue
        seen_labels.add(label_key)
        matches.append(node_id)
        if len(matches) >= limit:
            break
    return matches


def bfs(G: nx.Graph, start_nodes: list[str], depth: int) -> tuple[set[str], list[tuple[str, str]]]:
    visited: set[str] = set(start_nodes)
    frontier = set(start_nodes)
    edges_seen: list[tuple[str, str]] = []
    for _ in range(depth):
        next_frontier: set[str] = set()
        for node in frontier:
            for neighbor in G.neighbors(node):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
                    edges_seen.append((node, neighbor))
        visited.update(next_frontier)
        frontier = next_frontier
    return visited, edges_seen


def dfs(G: nx.Graph, start_nodes: list[str], depth: int) -> tuple[set[str], list[tuple[str, str]]]:
    visited: set[str] = set()
    edges_seen: list[tuple[str, str]] = []
    stack = [(node, 0) for node in reversed(start_nodes)]
    while stack:
        node, current_depth = stack.pop()
        if node in visited or current_depth > depth:
            continue
        visited.add(node)
        for neighbor in G.neighbors(node):
            if neighbor not in visited:
                stack.append((neighbor, current_depth + 1))
                edges_seen.append((node, neighbor))
    return visited, edges_seen


def subgraph_to_text(
    G: nx.Graph,
    nodes: set[str],
    edges: list[tuple[str, str]],
    *,
    token_budget: int = 2000,
) -> str:
    """Render a subgraph to compact text within an approximate token budget."""
    char_budget = token_budget * 3
    lines: list[str] = []
    ordered_nodes = sorted(
        nodes,
        key=lambda node_id: (
            -G.degree(node_id),
            G.nodes[node_id].get("label", node_id).lower(),
        ),
    )
    for node_id in ordered_nodes:
        data = G.nodes[node_id]
        line = (
            f"NODE {sanitize_label(data.get('label', node_id))} "
            f"[src={data.get('source_file', '')} "
            f"loc={data.get('source_location', '')} "
            f"community={data.get('community', '')}]"
        )
        lines.append(line)

    seen_edges: set[tuple[str, str, str]] = set()
    for u, v in edges:
        if u not in nodes or v not in nodes:
            continue
        src_id, tgt_id = _edge_direction(G, u, v)
        relation = G.edges[u, v].get("relation", "")
        edge_key = (src_id, tgt_id, relation)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        lines.append(_edge_to_text(G, u, v))

    output = "\n".join(lines)
    if len(output) > char_budget:
        output = output[:char_budget] + f"\n... (truncated to ~{token_budget} token budget)"
    return output


def query_graph_text(
    G: nx.Graph,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 2,
    token_budget: int = 2000,
    start_limit: int = 3,
) -> str:
    """Return a rendered traversal for a natural-language question."""
    start_nodes = find_nodes(G, question, limit=start_limit)
    if not start_nodes:
        return "No matching nodes found."

    walk = dfs if mode == "dfs" else bfs
    nodes, edges = walk(G, start_nodes, depth=depth)
    start_labels = [G.nodes[node_id].get("label", node_id) for node_id in start_nodes]
    header = (
        f"Traversal: {mode.upper()} depth={depth} | "
        f"Start: {start_labels} | {len(nodes)} nodes found\n\n"
    )
    return header + subgraph_to_text(G, nodes, edges, token_budget=token_budget)


def get_node_text(G: nx.Graph, label: str) -> str:
    """Return details for the best-matching node."""
    matches = find_nodes(G, label, limit=5)
    if not matches:
        return f"No node matching '{label}' found."
    node_id = matches[0]
    data = G.nodes[node_id]
    return "\n".join(
        [
            f"Node: {data.get('label', node_id)}",
            f"  ID: {node_id}",
            f"  Source: {data.get('source_file', '')} {data.get('source_location', '')}",
            f"  Type: {data.get('file_type', '')}",
            f"  Community: {data.get('community', '')}",
            f"  Degree: {G.degree(node_id)}",
        ]
    )


def get_neighbors_text(G: nx.Graph, label: str, *, relation_filter: str = "") -> str:
    """Return direct neighbors for the best-matching node."""
    matches = find_nodes(G, label, limit=5)
    if not matches:
        return f"No node matching '{label}' found."
    node_id = matches[0]
    relation_filter = relation_filter.lower().strip()
    lines = [f"Neighbors of {G.nodes[node_id].get('label', node_id)}:"]
    neighbor_lines: list[str] = []
    for neighbor in G.neighbors(node_id):
        if _is_annotation_node(G, neighbor):
            continue
        data = G.edges[node_id, neighbor]
        relation = data.get("relation", "")
        if relation_filter and relation_filter not in relation.lower():
            continue
        src_id, tgt_id = _edge_direction(G, node_id, neighbor)
        other_id = tgt_id if src_id == node_id else src_id
        other_label = G.nodes[other_id].get("label", other_id)
        neighbor_lines.append(
            f"  --> {other_label} [{relation}] [{data.get('confidence', '')}]"
        )
    if not neighbor_lines:
        return lines[0] + "\n  (no matching neighbors)"
    return "\n".join(lines + sorted(neighbor_lines))


def get_community_text(G: nx.Graph, communities: dict[int, list[str]], community_id: int) -> str:
    """Return all nodes in a community."""
    nodes = communities.get(community_id, [])
    if not nodes:
        return f"Community {community_id} not found."
    lines = [f"Community {community_id} ({len(nodes)} nodes):"]
    for node_id in nodes:
        data = G.nodes[node_id]
        if _is_file_node(G, node_id) or _is_annotation_node(G, node_id):
            continue
        lines.append(f"  {data.get('label', node_id)} [{data.get('source_file', '')}]")
    return "\n".join(lines)


def graph_stats_text(G: nx.Graph, communities: dict[int, list[str]]) -> str:
    """Return coarse graph statistics."""
    confidences = [data.get("confidence", "EXTRACTED") for _, _, data in G.edges(data=True)]
    total = len(confidences) or 1
    return (
        f"Nodes: {G.number_of_nodes()}\n"
        f"Edges: {G.number_of_edges()}\n"
        f"Communities: {len(communities)}\n"
        f"EXTRACTED: {round(confidences.count('EXTRACTED') / total * 100)}%\n"
        f"INFERRED: {round(confidences.count('INFERRED') / total * 100)}%\n"
        f"AMBIGUOUS: {round(confidences.count('AMBIGUOUS') / total * 100)}%\n"
    )


def shortest_path_text(G: nx.Graph, source: str, target: str, *, max_hops: int = 8) -> str:
    """Return the shortest path between two concepts."""
    src_nodes = find_nodes(G, source, limit=3)
    tgt_nodes = find_nodes(G, target, limit=3)
    if not src_nodes:
        return f"No node matching source '{source}' found."
    if not tgt_nodes:
        return f"No node matching target '{target}' found."

    src_node = src_nodes[0]
    tgt_node = tgt_nodes[0]
    try:
        path_nodes = nx.shortest_path(G, src_node, tgt_node)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return (
            f"No path found between '{G.nodes[src_node].get('label', src_node)}' "
            f"and '{G.nodes[tgt_node].get('label', tgt_node)}'."
        )

    hops = len(path_nodes) - 1
    if hops > max_hops:
        return f"Path exceeds max_hops={max_hops} ({hops} hops found)."

    segments: list[str] = []
    for index in range(len(path_nodes) - 1):
        u = path_nodes[index]
        v = path_nodes[index + 1]
        data = G.edges[u, v]
        src_id, tgt_id = _edge_direction(G, u, v)
        relation = data.get("relation", "")
        confidence = data.get("confidence", "")
        confidence_str = f" [{confidence}]" if confidence else ""
        if index == 0:
            segments.append(G.nodes[u].get("label", u))
        if src_id == u and tgt_id == v:
            connector = f"--{relation}{confidence_str}--> "
        elif src_id == v and tgt_id == u:
            connector = f"<--{relation}{confidence_str}-- "
        else:
            connector = f"--{relation}{confidence_str}-- "
        segments.append(connector + G.nodes[v].get("label", v))
    return f"Shortest path ({hops} hops):\n  " + " ".join(segments)


def explain_node_text(G: nx.Graph, label: str) -> str:
    """Return a graph-grounded explanation of a node."""
    matches = find_nodes(G, label, limit=5)
    if not matches:
        return f"No node matching '{label}' found."

    node_id = matches[0]
    data = G.nodes[node_id]
    neighbors = list(G.neighbors(node_id))
    informative_neighbors = [
        neighbor
        for neighbor in neighbors
        if not _is_annotation_node(G, neighbor)
    ] or neighbors
    relation_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    community_counts: Counter[int] = Counter()

    for neighbor in informative_neighbors:
        edge = G.edges[node_id, neighbor]
        src_id, tgt_id = _edge_direction(G, node_id, neighbor)
        relation = edge.get("relation", "related_to")
        other_id = tgt_id if src_id == node_id else src_id
        other_label = G.nodes[other_id].get("label", other_id)
        relation_groups[relation].append((other_label, edge.get("confidence", "")))
        other_cid = G.nodes[other_id].get("community")
        if other_cid is not None and other_cid != data.get("community"):
            community_counts[int(other_cid)] += 1

    lines = [
        f"{data.get('label', node_id)}",
        f"  Source: {data.get('source_file', '')} {data.get('source_location', '')}",
        f"  Type: {data.get('file_type', '')} · community {data.get('community', '')} · degree {G.degree(node_id)}",
    ]

    if relation_groups:
        lines.append("")
        lines.append("Relationship summary:")
        ranked_relations = sorted(
            relation_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        for relation, items in ranked_relations[:6]:
            preview = ", ".join(
                f"{name} [{confidence}]" if confidence else name
                for name, confidence in items[:4]
            )
            suffix = f" (+{len(items) - 4} more)" if len(items) > 4 else ""
            lines.append(f"  - {relation}: {preview}{suffix}")

    if community_counts:
        lines.append("")
        lines.append(
            "Cross-community reach: "
            + ", ".join(
                f"community {cid} ({count})"
                for cid, count in community_counts.most_common(5)
            )
        )

    if informative_neighbors:
        ranked_neighbors = sorted(
            informative_neighbors,
            key=lambda other_id: (
                -G.degree(other_id),
                G.nodes[other_id].get("label", other_id).lower(),
            ),
        )
        lines.append("")
        lines.append("Most connected neighbors:")
        for other_id in ranked_neighbors[:6]:
            edge = G.edges[node_id, other_id]
            src_id, tgt_id = _edge_direction(G, node_id, other_id)
            relation = edge.get("relation", "related_to")
            other_label = (
                G.nodes[tgt_id].get("label", tgt_id)
                if src_id == node_id
                else G.nodes[src_id].get("label", src_id)
            )
            lines.append(
                f"  - {other_label} [{relation}] [{edge.get('confidence', '')}]"
            )

    return "\n".join(lines)


def estimate_query_tokens(G: nx.Graph, question: str, *, depth: int = 3) -> int:
    """Estimate token cost for a question using the same traversal logic as query."""
    start_nodes = find_nodes(G, question, limit=3)
    if not start_nodes:
        return 0
    nodes, edges = bfs(G, start_nodes, depth=depth)
    text = subgraph_to_text(G, nodes, edges, token_budget=10_000)
    return max(1, math.ceil(len(text) / 4))
