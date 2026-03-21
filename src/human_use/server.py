from mcp.server.fastmcp import FastMCP

from human_use.tools import (
    ask_clarifying_question,
    ask_multiple_choice,
    check_progress,
    compare,
    get_results,
    rank,
)

mcp = FastMCP(name="human-use")

mcp.tool()(ask_clarifying_question)
mcp.tool()(ask_multiple_choice)
mcp.tool()(compare)
mcp.tool()(rank)
mcp.tool()(get_results)
mcp.tool()(check_progress)


def main() -> None:
    mcp.run()
