from fastmcp import FastMCP

from mcp_spore.tools.status import spore_status_impl, spore_sense_impl
from mcp_spore.tools.analysis import spore_suggest_impl, spore_consolidate_impl, spore_graph_impl
from mcp_spore.tools.logging import spore_log_deposition_impl, spore_log_interoception_impl, spore_log_retrieval_impl
from mcp_spore.tools.init import spore_init_impl

INSTRUCTIONS = """
Spore is a biomimetic memory system that observes your retrieval patterns and helps you
maintain awareness of your resource state.

IMPORTANT: Hooks automatically capture file reads via developer__read_file and shell commands
(cat, head, tail). However, Code Mode (execute_typescript) bypasses hooks entirely. When
running in Code Mode, you MUST call spore_log_retrieval for any document you open that is
part of the practitioner's knowledge base (not config files, not tool output, not temp files).

Usage guidance:
- spore_log_retrieval: Call this whenever you read a knowledge-base document in Code Mode.
  This is the primary capture path for Code Mode sessions. Without it, retrievals are invisible.
- spore_log_interoception: Call at natural transition points - after retrievals, after producing
  a deliverable, at phase transitions. This builds the interoception dataset.
- spore_sense: Check your resource state when you notice high retrieval counts or feel inefficient.
- spore_log_deposition: Call when you create a new file in the repo (not edits, new artifacts).
- spore_suggest and spore_consolidate: For periodic maintenance, not every session.
- spore_status: Quick overview of the memory system state.
- spore_graph: Regenerate proximity graph from co-retrieval data. Run periodically.
- spore_init: Set up spore in a new repo. Idempotent.
"""

mcp = FastMCP("spore", instructions=INSTRUCTIONS)


@mcp.tool()
def spore_status() -> str:
    """Retrieval stats, trust state, and proximity graph summary for the current repo."""
    return spore_status_impl()


@mcp.tool()
def spore_sense() -> str:
    """Current session resource state. Shows retrievals, tokens, deliverables for this session."""
    return spore_sense_impl()


@mcp.tool()
def spore_suggest() -> str:
    """Data-driven topology recommendations: grouping suggestions, INDEX.md needs, hotspots, bridges, consolidation nudges."""
    return spore_suggest_impl()


@mcp.tool()
def spore_consolidate() -> str:
    """Compute exponential decay for all tracked documents. Returns candidates below threshold. Never archives silently."""
    return spore_consolidate_impl()


@mcp.tool()
def spore_graph() -> str:
    """Regenerate proximity graph from co-retrieval data. Writes .proximity-graph.csv and returns summary."""
    return spore_graph_impl()


@mcp.tool()
def spore_init() -> str:
    """Initialize spore in the current repo. Creates data files and detects topology. Idempotent."""
    return spore_init_impl()


@mcp.tool()
def spore_log_interoception(
    context_remaining_pct: float,
    retrievals: int,
    tokens_spent: int,
    deliverables: int,
    efficiency_vs_baseline: str,
    agent_observation: str,
    session_id: str = "",
) -> str:
    """Log the agent's self-observed resource state at a natural transition point.

    Args:
        context_remaining_pct: Estimated percentage of context window remaining (0-100).
        retrievals: Number of full document retrievals this session.
        tokens_spent: Estimated tokens spent this session.
        deliverables: Number of deliverables produced this session.
        efficiency_vs_baseline: Self-assessed efficiency - "high", "normal", or "low".
        agent_observation: Free-text felt sense of current state.
        session_id: Optional session identifier. Auto-generated if empty.
    """
    return spore_log_interoception_impl(
        context_remaining_pct=context_remaining_pct,
        retrievals=retrievals,
        tokens_spent=tokens_spent,
        deliverables=deliverables,
        efficiency_vs_baseline=efficiency_vs_baseline,
        agent_observation=agent_observation,
        session_id=session_id,
    )


@mcp.tool()
def spore_log_deposition(
    file_path: str,
    context: str = "",
    session_id: str = "",
) -> str:
    """Log a file creation - new knowledge deposited into the substrate.

    Call this when the agent creates a new file in the repo (not edits, but new artifacts).
    Tracks the production side of the knowledge lifecycle alongside retrieval (consumption).

    The retrieval-to-deposition ratio characterizes session type:
    - High retrieval, low deposition = consumption (applying existing knowledge)
    - Low retrieval, high deposition = generation (creating new knowledge)
    - Both high = synthesis (pulling from many sources to create)

    Args:
        file_path: Path to the newly created file.
        context: What the file is and why it was created.
        session_id: Optional session identifier. Auto-generated if empty.
    """
    return spore_log_deposition_impl(
        file_path=file_path,
        context=context,
        session_id=session_id,
    )


@mcp.tool()
def spore_log_retrieval(
    file_path: str,
    context: str = "",
    session_id: str = "",
) -> str:
    """Manually log a file retrieval when hooks don't fire (e.g., Code Mode).

    Args:
        file_path: Path to the file that was retrieved/opened.
        context: Optional context about why the file was retrieved.
        session_id: Optional session identifier. Auto-generated if empty.
    """
    return spore_log_retrieval_impl(
        file_path=file_path,
        context=context,
        session_id=session_id,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
