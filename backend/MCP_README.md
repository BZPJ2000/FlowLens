# PoltAIshow MCP Server

为 Claude Desktop 和 Cursor 提供项目结构上下文的 MCP (Model Context Protocol) 服务器。

## 功能

MCP 服务器暴露以下工具，让 AI 助手直接查询项目结构：

| 工具 | 描述 |
|------|------|
| `get_project_structure` | 获取项目文件树、语言分布、架构角色统计 |
| `get_file_analysis` | 获取文件详细分析（摘要、输入输出、函数、类） |
| `get_dependencies` | 获取文件依赖关系（导入/被导入） |
| `analyze_impact` | 变更影响分析（修改文件会影响哪些其他文件 + 风险评分） |
| `search_files` | 搜索文件（按名称、语言、架构角色） |
| `get_data_flow` | 获取两文件间数据流路径（最短路径） |

## 安装配置

### 1. Claude Desktop

编辑配置文件 `~/.config/claude/config.json` (macOS/Linux) 或 `%APPDATA%\Claude\config.json` (Windows):

```json
{
  "mcpServers": {
    "poltaishow": {
      "command": "python",
      "args": ["E:\\Github_Project\\PoltAIshow\\backend\\mcp_server.py"],
      "env": {
        "PYTHONPATH": "E:\\Github_Project\\PoltAIshow\\backend"
      }
    }
  }
}
```

重启 Claude Desktop 后，在对话中可以使用：

```
请使用 poltaishow 工具查看项目结构，分析 ID 是 abc-123-def
```

### 2. Cursor

Cursor 的 MCP 支持正在开发中。当前可以通过 API 方式集成：

```typescript
// .cursor/mcp.json
{
  "servers": {
    "poltaishow": {
      "command": "python",
      "args": ["path/to/mcp_server.py"]
    }
  }
}
```

## 使用示例

### 获取项目结构

```
使用 get_project_structure 工具，分析 ID: abc-123
```

返回：
```json
{
  "total_files": 42,
  "languages": {
    "typescript": 30,
    "python": 10,
    "css": 2
  },
  "roles": {
    "controller": 5,
    "service": 8,
    "model": 6,
    "view": 12,
    "util": 11
  },
  "files": [...]
}
```

### 分析文件依赖

```
使用 get_dependencies 工具查看 src/auth/login.ts 的依赖关系
```

### 变更影响分析

```
如果我修改 src/utils/api.ts，会影响哪些文件？使用 analyze_impact 工具
```

返回按风险评分排序的影响文件列表。

### 搜索文件

```
搜索所有 controller 角色的 TypeScript 文件
```

## 工作原理

1. MCP 服务器通过 stdio 与 Claude/Cursor 通信（JSON-RPC 2.0）
2. 直接读取 SQLite 数据库 `poltaishow.db`
3. 调用 `graph_builder.analyze_impact()` 等核心函数
4. 返回 JSON 格式的结构化数据

## 依赖

- Python 3.9+
- SQLite3（内置）
- FastAPI 项目的核心模块（`app.core.graph_builder`, `app.models.schemas`）

## 故障排查

### Claude Desktop 无法连接

1. 检查配置文件路径是否正确
2. 确保 Python 路径正确（`which python` / `where python`）
3. 查看 Claude Desktop 日志：`~/Library/Logs/Claude/` (macOS)

### 工具调用失败

1. 确保数据库文件 `poltaishow.db` 存在
2. 检查 `analysis_id` 是否有效（从 Web UI 获取）
3. 查看 stderr 输出：`python mcp_server.py 2> error.log`

## 开发

测试 MCP 服务器：

```bash
# 手动发送 JSON-RPC 请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python mcp_server.py

# 测试工具调用
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python mcp_server.py
```

## 参考

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Claude Desktop MCP 配置](https://docs.anthropic.com/claude/docs/mcp)
