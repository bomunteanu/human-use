from mcp.server.fastmcp import FastMCP

from human_use.tools import (
    ask_free_text,
    ask_multiple_choice,
    check_progress,
    compare,
    get_results,
    rank,
)

mcp = FastMCP(name="human-use")

mcp.tool()(ask_free_text)
mcp.tool()(ask_multiple_choice)
mcp.tool()(compare)
mcp.tool()(rank)
mcp.tool()(get_results)
mcp.tool()(check_progress)


def main() -> None:
    mcp.run()
