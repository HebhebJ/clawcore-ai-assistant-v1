from src.tools.builtins.files import list_files, read_file
from src.tools.builtins.utils import get_datetime
from src.tools.builtins.web import read_url, search_web
from src.tools.schemas import Tool


def default_registry() -> dict[str, Tool]:
    tools = [
        Tool(
            id="list_files",
            name="list_files",
            description="List files in a workspace-relative directory",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            handler=list_files,
        ),
        Tool(
            id="read_file",
            name="read_file",
            description="Read a UTF-8 text file in workspace",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["path"],
            },
            handler=read_file,
        ),
        Tool(
            id="get_datetime",
            name="get_datetime",
            description="Get current UTC datetime",
            input_schema={"type": "object", "properties": {}},
            handler=get_datetime,
        ),
        Tool(
            id="search_web",
            name="search_web",
            description="Search the web and return ranked results",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
            handler=search_web,
        ),
        Tool(
            id="read_url",
            name="read_url",
            description="Fetch and extract readable text from a URL",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["url"],
            },
            handler=read_url,
        ),
    ]
    return {tool.name: tool for tool in tools}
