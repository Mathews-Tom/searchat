# MCP Setup

Searchat ships an MCP server so tools like Claude Desktop (and other MCP clients) can query your local Searchat index without manual curl commands.

## Install

```bash
pip install "searchat[mcp]"
```

## Run the MCP server

```bash
searchat-mcp
```

The MCP server uses stdio. It reads your Searchat config (`~/.searchat/config/settings.toml`) and defaults to the shared dataset directory (`~/.searchat/`).

## Claude Desktop configuration

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "searchat": {
      "command": "searchat-mcp"
    }
  }
}
```

Restart Claude Desktop.

## Available tools

- `search_conversations`: query indexed conversations
- `get_conversation`: fetch a conversation by id
- `list_projects`: list indexed project ids
- `get_statistics`: basic index stats

## Notes

- If your data directory is non-default, set `SEARCHAT_DATA_DIR` (or update your config) so the MCP server points at the correct dataset.
- The MCP tools accept an optional `search_dir` parameter if you want to target a specific dataset directory.
