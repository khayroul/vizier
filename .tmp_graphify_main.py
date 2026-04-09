"""graphify CLI - `graphify install` sets up the Claude Code skill."""
from __future__ import annotations
import argparse
import json
import platform
import re
import shutil
import sys
from pathlib import Path

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("graphifyy")
except Exception:
    __version__ = "unknown"


def _check_skill_version(skill_dst: Path) -> str | None:
    """Return the installed skill version if it is stale."""
    version_file = skill_dst.parent / ".graphify_version"
    if not version_file.exists():
        return None
    installed = version_file.read_text(encoding="utf-8").strip()
    return installed if installed != __version__ else None

_SETTINGS_HOOK = {
    "matcher": "Glob|Grep",
    "hooks": [
        {
            "type": "command",
            "command": (
                "[ -f graphify-out/graph.json ] && "
                r"""echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files."}}' """
                "|| true"
            ),
        }
    ],
}

_SKILL_REGISTRATION = (
    "\n# graphify\n"
    "- **graphify** (`~/.claude/skills/graphify/SKILL.md`) "
    "- any input to knowledge graph. Trigger: `/graphify`\n"
    "When the user types `/graphify`, invoke the Skill tool "
    "with `skill: \"graphify\"` before doing anything else.\n"
)


_PLATFORM_CONFIG: dict[str, dict] = {
    "claude": {
        "skill_file": "skill.md",
        "skill_dst": Path(".claude") / "skills" / "graphify" / "SKILL.md",
        "claude_md": True,
    },
    "codex": {
        "skill_file": "skill-codex.md",
        "skill_dst": Path(".agents") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "opencode": {
        "skill_file": "skill-opencode.md",
        "skill_dst": Path(".config") / "opencode" / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "claw": {
        "skill_file": "skill-claw.md",
        "skill_dst": Path(".claw") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "droid": {
        "skill_file": "skill-droid.md",
        "skill_dst": Path(".factory") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "trae": {
        "skill_file": "skill-trae.md",
        "skill_dst": Path(".trae") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "trae-cn": {
        "skill_file": "skill-trae.md",
        "skill_dst": Path(".trae-cn") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "windows": {
        "skill_file": "skill-windows.md",
        "skill_dst": Path(".claude") / "skills" / "graphify" / "SKILL.md",
        "claude_md": True,
    },
}


def install(platform: str = "claude") -> None:
    if platform not in _PLATFORM_CONFIG:
        print(
            f"error: unknown platform '{platform}'. Choose from: {', '.join(_PLATFORM_CONFIG)}",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = _PLATFORM_CONFIG[platform]
    skill_src = Path(__file__).parent / cfg["skill_file"]
    if not skill_src.exists():
        print(f"error: {cfg['skill_file']} not found in package - reinstall graphify", file=sys.stderr)
        sys.exit(1)

    skill_dst = Path.home() / cfg["skill_dst"]
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill_src, skill_dst)
    (skill_dst.parent / ".graphify_version").write_text(__version__, encoding="utf-8")
    print(f"  skill installed  ->  {skill_dst}")

    if cfg["claude_md"]:
        # Register in ~/.claude/CLAUDE.md (Claude Code only)
        claude_md = Path.home() / ".claude" / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            if "graphify" in content:
                print(f"  CLAUDE.md        ->  already registered (no change)")
            else:
                claude_md.write_text(content.rstrip() + _SKILL_REGISTRATION, encoding="utf-8")
                print(f"  CLAUDE.md        ->  skill registered in {claude_md}")
        else:
            claude_md.parent.mkdir(parents=True, exist_ok=True)
            claude_md.write_text(_SKILL_REGISTRATION.lstrip(), encoding="utf-8")
            print(f"  CLAUDE.md        ->  created at {claude_md}")

    print()
    print("Done. Open your AI coding assistant and type:")
    print()
    print("  /graphify .")
    print()


_CLAUDE_MD_SECTION = """\
## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
"""

_CLAUDE_MD_MARKER = "## graphify"

# AGENTS.md section for Codex, OpenCode, and OpenClaw.
# All three platforms read AGENTS.md in the project root for persistent instructions.
_AGENTS_MD_SECTION = """\
## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
"""

_AGENTS_MD_MARKER = "## graphify"

_CODEX_HOOK = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "[ -f graphify-out/graph.json ] && "
                            r"""echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files."}}' """
                            "|| true"
                        ),
                    }
                ],
            }
        ]
    }
}


def _install_codex_hook(project_dir: Path) -> None:
    """Add graphify PreToolUse hook to .codex/hooks.json."""
    hooks_path = project_dir / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)

    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    pre_tool = existing.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if any("graphify" in str(h) for h in pre_tool):
        print(f"  .codex/hooks.json  ->  hook already registered (no change)")
        return

    pre_tool.extend(_CODEX_HOOK["hooks"]["PreToolUse"])
    hooks_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  .codex/hooks.json  ->  PreToolUse hook registered")


def _uninstall_codex_hook(project_dir: Path) -> None:
    """Remove graphify PreToolUse hook from .codex/hooks.json."""
    hooks_path = project_dir / ".codex" / "hooks.json"
    if not hooks_path.exists():
        return
    try:
        existing = json.loads(hooks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    pre_tool = existing.get("hooks", {}).get("PreToolUse", [])
    filtered = [h for h in pre_tool if "graphify" not in str(h)]
    existing["hooks"]["PreToolUse"] = filtered
    hooks_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  .codex/hooks.json  ->  PreToolUse hook removed")


def _agents_install(project_dir: Path, platform: str) -> None:
    """Write the graphify section to the local AGENTS.md (Codex/OpenCode/OpenClaw)."""
    target = (project_dir or Path(".")) / "AGENTS.md"

    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _AGENTS_MD_MARKER in content:
            print(f"graphify already configured in AGENTS.md")
            return
        new_content = content.rstrip() + "\n\n" + _AGENTS_MD_SECTION
    else:
        new_content = _AGENTS_MD_SECTION

    target.write_text(new_content, encoding="utf-8")
    print(f"graphify section written to {target.resolve()}")

    if platform == "codex":
        _install_codex_hook(project_dir or Path("."))

    print()
    print(f"{platform.capitalize()} will now check the knowledge graph before answering")
    print("codebase questions and rebuild it after code changes.")
    if platform != "codex":
        print()
        print("Note: unlike Claude Code, there is no PreToolUse hook equivalent for")
        print(f"{platform.capitalize()} — the AGENTS.md rules are the always-on mechanism.")


def _agents_uninstall(project_dir: Path) -> None:
    """Remove the graphify section from the local AGENTS.md."""
    target = (project_dir or Path(".")) / "AGENTS.md"

    if not target.exists():
        print("No AGENTS.md found in current directory - nothing to do")
        return

    content = target.read_text(encoding="utf-8")
    if _AGENTS_MD_MARKER not in content:
        print("graphify section not found in AGENTS.md - nothing to do")
        return

    cleaned = re.sub(
        r"\n*## graphify\n.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    ).rstrip()
    if cleaned:
        target.write_text(cleaned + "\n", encoding="utf-8")
        print(f"graphify section removed from {target.resolve()}")
    else:
        target.unlink()
        print(f"AGENTS.md was empty after removal - deleted {target.resolve()}")


def claude_install(project_dir: Path | None = None) -> None:
    """Write the graphify section to the local CLAUDE.md."""
    target = (project_dir or Path(".")) / "CLAUDE.md"

    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _CLAUDE_MD_MARKER in content:
            print("graphify already configured in CLAUDE.md")
            return
        new_content = content.rstrip() + "\n\n" + _CLAUDE_MD_SECTION
    else:
        new_content = _CLAUDE_MD_SECTION

    target.write_text(new_content, encoding="utf-8")
    print(f"graphify section written to {target.resolve()}")

    # Also write Claude Code PreToolUse hook to .claude/settings.json
    _install_claude_hook(project_dir or Path("."))

    print()
    print("Claude Code will now check the knowledge graph before answering")
    print("codebase questions and rebuild it after code changes.")


def _install_claude_hook(project_dir: Path) -> None:
    """Add graphify PreToolUse hook to .claude/settings.json."""
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool = hooks.setdefault("PreToolUse", [])

    # Check if already installed
    if any(h.get("matcher") == "Glob|Grep" and "graphify" in str(h) for h in pre_tool):
        print(f"  .claude/settings.json  ->  hook already registered (no change)")
        return

    pre_tool.append(_SETTINGS_HOOK)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"  .claude/settings.json  ->  PreToolUse hook registered")


def _uninstall_claude_hook(project_dir: Path) -> None:
    """Remove graphify PreToolUse hook from .claude/settings.json."""
    settings_path = project_dir / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    pre_tool = settings.get("hooks", {}).get("PreToolUse", [])
    filtered = [h for h in pre_tool if not (h.get("matcher") == "Glob|Grep" and "graphify" in str(h))]
    if len(filtered) == len(pre_tool):
        return
    settings["hooks"]["PreToolUse"] = filtered
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"  .claude/settings.json  ->  PreToolUse hook removed")


def claude_uninstall(project_dir: Path | None = None) -> None:
    """Remove the graphify section from the local CLAUDE.md."""
    target = (project_dir or Path(".")) / "CLAUDE.md"

    if not target.exists():
        print("No CLAUDE.md found in current directory - nothing to do")
        return

    content = target.read_text(encoding="utf-8")
    if _CLAUDE_MD_MARKER not in content:
        print("graphify section not found in CLAUDE.md - nothing to do")
        return

    # Remove the ## graphify section: from the marker to the next ## heading or EOF
    cleaned = re.sub(
        r"\n*## graphify\n.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    ).rstrip()
    if cleaned:
        target.write_text(cleaned + "\n", encoding="utf-8")
        print(f"graphify section removed from {target.resolve()}")
    else:
        target.unlink()
        print(f"CLAUDE.md was empty after removal - deleted {target.resolve()}")

    _uninstall_claude_hook(project_dir or Path("."))


def _load_graph_any(graph_path: str):
    graph_file = Path(graph_path).expanduser().resolve()
    if not graph_file.exists():
        raise FileNotFoundError(f"graph file not found: {graph_file}")
    if graph_file.suffix != ".json":
        raise ValueError(f"graph file must be a .json file: {graph_file}")
    from networkx.readwrite import json_graph

    data = json.loads(graph_file.read_text(encoding="utf-8"))
    return json_graph.node_link_graph(data, edges="links")


def _communities_from_graph(G) -> dict[int, list[str]]:
    communities: dict[int, list[str]] = {}
    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        communities.setdefault(int(cid), []).append(node_id)
    return communities


def _community_labels(communities: dict[int, list[str]]) -> dict[int, str]:
    return {cid: f"Community {cid}" for cid in communities}


def _print_detect_summary(result: dict) -> None:
    print(f"Corpus: {result.get('total_files', 0)} files · ~{result.get('total_words', 0):,} words")
    if result.get("profile"):
        print(f"Profile: {result['profile']}")
    counts = result.get("files", {})
    print(f"  code:     {len(counts.get('code', []))} files")
    print(f"  docs:     {len(counts.get('document', []))} files")
    print(f"  papers:   {len(counts.get('paper', []))} files")
    print(f"  images:   {len(counts.get('image', []))} files")
    if result.get("warning"):
        print(f"Warning: {result['warning']}")
    if result.get("skipped_sensitive"):
        print(f"Sensitive skipped: {len(result['skipped_sensitive'])} file(s)")


def _run_detect_command(args: argparse.Namespace) -> int:
    from graphify.detect import detect, detect_incremental

    root = Path(args.path)
    runner = detect_incremental if args.incremental else detect
    result = runner(
        root,
        follow_symlinks=args.follow_symlinks,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    _print_detect_summary(result)
    return 0


def _run_profiles_command(args: argparse.Namespace) -> int:
    from graphify.config import available_profiles, load_project_config

    root = Path(args.path).resolve()
    config = load_project_config(root)
    profiles = available_profiles(config)
    if not profiles:
        print(f"No graphify profiles found in {root}.")
        return 0

    print(f"Profiles for {root}:")
    for profile_cfg in profiles:
        suffix = " (default)" if profile_cfg.name == config.default_profile else ""
        description = profile_cfg.description or "No description."
        print(f"- {profile_cfg.name}{suffix}: {description}")
    return 0


def _run_build_command(args: argparse.Namespace) -> int:
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect, save_manifest
    from graphify.export import to_html, to_json
    from graphify.extract import extract
    from graphify.report import generate

    root = Path(args.path).resolve()
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else root / "graphify-out"
    )

    detection = detect(
        root,
        follow_symlinks=args.follow_symlinks,
        profile=args.profile,
    )
    code_files = [Path(path) for path in detection["files"].get("code", [])]
    if not code_files:
        scope = f" for profile '{detection.get('profile')}'" if detection.get("profile") else ""
        print(f"No code files found{scope}.")
        return 0

    extraction = extract(code_files)
    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = _community_labels(communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)

    out_dir.mkdir(parents=True, exist_ok=True)
    to_json(G, communities, str(out_dir / "graph.json"))
    (out_dir / "detect.json").write_text(json.dumps(detection, indent=2), encoding="utf-8")
    (out_dir / "ast.json").write_text(json.dumps(extraction, indent=2), encoding="utf-8")
    (out_dir / "analysis.json").write_text(
        json.dumps(
            {
                "cohesion_scores": cohesion,
                "community_labels": labels,
                "god_nodes": gods,
                "surprising_connections": surprises,
                "suggested_questions": questions,
                "alignment": G.graph.get("alignment", {}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        str(root),
        suggested_questions=questions,
    )
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    save_manifest(detection["files"], manifest_path=str(out_dir / "manifest.json"))

    html_written = False
    if not args.no_html:
        try:
            to_html(G, communities, str(out_dir / "graph.html"), community_labels=labels)
            html_written = True
        except ValueError as exc:
            print(f"warning: {exc}", file=sys.stderr)

    print(
        f"Built graph: {G.number_of_nodes()} nodes · "
        f"{G.number_of_edges()} edges · {len(communities)} communities"
    )
    if detection.get("profile"):
        print(f"Profile: {detection['profile']}")
    print(f"Output directory: {out_dir}")
    if html_written:
        print(f"HTML: {out_dir / 'graph.html'}")
    return 0


def _run_query_command(args: argparse.Namespace) -> int:
    from graphify.query import query_graph_text

    G = _load_graph_any(args.graph)
    print(
        query_graph_text(
            G,
            args.question,
            mode="dfs" if args.dfs else "bfs",
            depth=max(1, min(args.depth, 6)),
            token_budget=args.budget,
        )
    )
    return 0


def _run_node_command(args: argparse.Namespace) -> int:
    from graphify.query import get_node_text

    G = _load_graph_any(args.graph)
    print(get_node_text(G, args.label))
    return 0


def _run_neighbors_command(args: argparse.Namespace) -> int:
    from graphify.query import get_neighbors_text

    G = _load_graph_any(args.graph)
    print(get_neighbors_text(G, args.label, relation_filter=args.relation or ""))
    return 0


def _run_community_command(args: argparse.Namespace) -> int:
    from graphify.query import get_community_text

    G = _load_graph_any(args.graph)
    communities = _communities_from_graph(G)
    print(get_community_text(G, communities, args.community_id))
    return 0


def _run_stats_command(args: argparse.Namespace) -> int:
    from graphify.query import graph_stats_text

    G = _load_graph_any(args.graph)
    communities = _communities_from_graph(G)
    print(graph_stats_text(G, communities))
    return 0


def _run_path_command(args: argparse.Namespace) -> int:
    from graphify.query import shortest_path_text

    G = _load_graph_any(args.graph)
    print(shortest_path_text(G, args.source, args.target, max_hops=args.max_hops))
    return 0


def _run_explain_command(args: argparse.Namespace) -> int:
    from graphify.query import explain_node_text

    G = _load_graph_any(args.graph)
    print(explain_node_text(G, args.label))
    return 0


def _run_serve_command(args: argparse.Namespace) -> int:
    from graphify.serve import serve

    serve(args.graph)
    return 0


def _run_watch_command(args: argparse.Namespace) -> int:
    from graphify.watch import watch

    watch(
        Path(args.path),
        debounce=args.debounce,
        profile=args.profile,
        follow_symlinks=args.follow_symlinks,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graphify", description="Graphify knowledge graph CLI")
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install", help="copy skill to platform config dir")
    install_parser.add_argument("--platform", dest="platform_name")

    benchmark_parser = subparsers.add_parser("benchmark", help="measure token reduction")
    benchmark_parser.add_argument("graph", nargs="?", default="graphify-out/graph.json")

    detect_parser = subparsers.add_parser("detect", help="preview a scoped corpus")
    detect_parser.add_argument("path", nargs="?", default=".")
    detect_parser.add_argument("--profile")
    detect_parser.add_argument("--follow-symlinks", action="store_true")
    detect_parser.add_argument("--incremental", action="store_true")
    detect_parser.add_argument("--json", action="store_true")

    profiles_parser = subparsers.add_parser("profiles", help="list configured graphify profiles")
    profiles_parser.add_argument("path", nargs="?", default=".")

    build_parser = subparsers.add_parser("build", help="deterministic code-only graph build")
    build_parser.add_argument("path", nargs="?", default=".")
    build_parser.add_argument("--profile")
    build_parser.add_argument("--out-dir")
    build_parser.add_argument("--follow-symlinks", action="store_true")
    build_parser.add_argument("--no-html", action="store_true")

    query_parser = subparsers.add_parser("query", help="traverse a graph for a question")
    query_parser.add_argument("question")
    query_parser.add_argument("--dfs", action="store_true")
    query_parser.add_argument("--depth", type=int, default=2)
    query_parser.add_argument("--budget", type=int, default=2000)
    query_parser.add_argument("--graph", default="graphify-out/graph.json")

    path_parser = subparsers.add_parser("path", help="find the shortest path between two concepts")
    path_parser.add_argument("source")
    path_parser.add_argument("target")
    path_parser.add_argument("--max-hops", type=int, default=8)
    path_parser.add_argument("--graph", default="graphify-out/graph.json")

    explain_parser = subparsers.add_parser("explain", help="explain a node using graph relationships")
    explain_parser.add_argument("label")
    explain_parser.add_argument("--graph", default="graphify-out/graph.json")

    node_parser = subparsers.add_parser("node", help="inspect a single node")
    node_parser.add_argument("label")
    node_parser.add_argument("--graph", default="graphify-out/graph.json")

    neighbors_parser = subparsers.add_parser("neighbors", help="inspect direct neighbors of a node")
    neighbors_parser.add_argument("label")
    neighbors_parser.add_argument("--relation")
    neighbors_parser.add_argument("--graph", default="graphify-out/graph.json")

    community_parser = subparsers.add_parser("community", help="list nodes in a community")
    community_parser.add_argument("community_id", type=int)
    community_parser.add_argument("--graph", default="graphify-out/graph.json")

    stats_parser = subparsers.add_parser("stats", help="show graph statistics")
    stats_parser.add_argument("--graph", default="graphify-out/graph.json")

    serve_parser = subparsers.add_parser("serve", help="start the MCP server")
    serve_parser.add_argument("--graph", default="graphify-out/graph.json")

    watch_parser = subparsers.add_parser("watch", help="watch a folder and auto-update code graphs")
    watch_parser.add_argument("path", nargs="?", default=".")
    watch_parser.add_argument("--profile")
    watch_parser.add_argument("--debounce", type=float, default=3.0)
    watch_parser.add_argument("--follow-symlinks", action="store_true")

    hook_parser = subparsers.add_parser("hook", help="manage graphify git hooks")
    hook_parser.add_argument("action", choices=["install", "uninstall", "status"])

    for platform_name in ("claude", "codex", "opencode", "claw", "droid", "trae", "trae-cn"):
        platform_parser = subparsers.add_parser(platform_name, help=f"manage {platform_name} integration")
        platform_parser.add_argument("action", choices=["install", "uninstall"])

    return parser


def main() -> None:
    warned_paths: set[Path] = set()
    stale_versions: list[str] = []
    for cfg in _PLATFORM_CONFIG.values():
        skill_dst = (Path.home() / cfg["skill_dst"]).resolve()
        if skill_dst in warned_paths:
            continue
        warned_paths.add(skill_dst)
        installed = _check_skill_version(skill_dst)
        if installed:
            stale_versions.append(installed)

    if stale_versions:
        versions = ", ".join(sorted(set(stale_versions)))
        count = len(stale_versions)
        noun = "skill is" if count == 1 else "skills are"
        print(
            f"  warning: {count} installed {noun} from graphify {versions}; "
            f"package is {__version__}. Run 'graphify install' to update."
        )

    parser = _build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "install":
            default_platform = "windows" if platform.system() == "Windows" else "claude"
            install(platform=args.platform_name or default_platform)
        elif args.command == "benchmark":
            from graphify.benchmark import print_benchmark, run_benchmark

            corpus_words = None
            detect_path = Path(".graphify_detect.json")
            if detect_path.exists():
                try:
                    detect_data = json.loads(detect_path.read_text(encoding="utf-8"))
                    corpus_words = detect_data.get("total_words")
                except Exception:
                    corpus_words = None
            result = run_benchmark(args.graph, corpus_words=corpus_words)
            print_benchmark(result)
        elif args.command == "detect":
            _run_detect_command(args)
        elif args.command == "profiles":
            _run_profiles_command(args)
        elif args.command == "build":
            _run_build_command(args)
        elif args.command == "query":
            _run_query_command(args)
        elif args.command == "path":
            _run_path_command(args)
        elif args.command == "explain":
            _run_explain_command(args)
        elif args.command == "node":
            _run_node_command(args)
        elif args.command == "neighbors":
            _run_neighbors_command(args)
        elif args.command == "community":
            _run_community_command(args)
        elif args.command == "stats":
            _run_stats_command(args)
        elif args.command == "serve":
            _run_serve_command(args)
        elif args.command == "watch":
            _run_watch_command(args)
        elif args.command == "hook":
            from graphify.hooks import install as hook_install, status as hook_status, uninstall as hook_uninstall

            if args.action == "install":
                print(hook_install(Path(".")))
            elif args.action == "uninstall":
                print(hook_uninstall(Path(".")))
            else:
                print(hook_status(Path(".")))
        elif args.command == "claude":
            if args.action == "install":
                claude_install()
            else:
                claude_uninstall()
        elif args.command in ("codex", "opencode", "claw", "droid", "trae", "trae-cn"):
            if args.action == "install":
                _agents_install(Path("."), args.command)
            else:
                _agents_uninstall(Path("."))
                if args.command == "codex":
                    _uninstall_codex_hook(Path("."))
        else:
            parser.error(f"unknown command: {args.command}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
