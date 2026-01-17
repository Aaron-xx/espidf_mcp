# ESP-IDF MCP Server

符合 MCP 标准的 ESP-IDF 开发运维服务器，通过 stdio 或 HTTP 提供 ESP-IDF 工具接口。

## 特性

- **MCP 标准兼容**: 完全符合 Model Context Protocol 标准
- **多协议支持**: 支持 stdio（MCP 客户端）和 HTTP/SSE（URL 访问）
- **双格式日志**: 彩色终端输出 + JSON 结构化日志（AI 友好）
- **错误诊断**: 智能错误模式识别和修复建议
- **性能监控**: 工具执行统计和瓶颈分析
- **简单优先**: 极简模块结构，易于维护
- **基于现有设施**: 复用 `idf.py` 和现有命令行工具
- **友好输出**: 人类可读的文本格式，带 emoji 标识
- **安全优先**: 不执行破坏性操作
- **自动检测**: 自动检测 ESP-IDF 项目目录

## 快速开始

### 全局安装

```bash
cd /path/to/espidf-mcp
pip install -e .
```

### 使用方式

**方式 1: 全局命令（推荐）**

```bash
# 进入 ESP-IDF 项目目录
cd /path/to/esp32_project

# 启动服务器（stdio 模式）
espidf-mcp

# 启动服务器（HTTP 模式）
espidf-mcp --http --port 8090
```

**方式 2: Python 模块**

```bash
# 进入 ESP-IDF 项目目录
cd /path/to/esp32_project

# 启动服务器（stdio 模式）
python -m espidf_mcp

# 启动服务器（HTTP 模式）
python -m espidf_mcp --http --port 8090
```

### 项目自动检测

服务器会自动检测当前目录是否为 ESP-IDF 项目：

- ✅ **有效项目**: 显示项目信息，正常启动
- ⚠️ **无效项目**: 显示警告和建议，仍然启动服务器（工具会返回错误）

检测逻辑：
1. 检查是否存在 `CMakeLists.txt`
2. 验证 `CMakeLists.txt` 内容包含 ESP-IDF 标记

### 客户端配置

在 MCP 客户端配置文件中添加（如 Claude Desktop）：

```json
{
  "mcpServers": {
    "espidf": {
      "command": "espidf-mcp",
      "cwd": "/path/to/esp32_project",
      "env": {
        "IDF_PATH": "/path/to/esp-idf"
      }
    }
  }
}
```

更多示例配置见 [examples/mcp-client-config.json](examples/mcp-client-config.json)

## 可用工具

### 核心 ESP-IDF 工具

| 工具 | 说明 |
|------|------|
| `esp_project_info` | 获取当前项目信息 |
| `esp_build` | 构建 ESP-IDF 项目 |
| `esp_flash` | 烧录固件到设备 |
| `esp_monitor` | 实时监控串口输出 |
| `esp_list_ports` | 列出可用的串口设备 |
| `esp_clean` | 清理构建文件 |
| `esp_fullclean` | 完全清理构建文件 |
| `esp_size` | 分析固件大小 |
| `esp_set_target` | 设置芯片目标 |

### 可观测性工具

| 工具 | 说明 |
|------|------|
| `esp_metrics_summary` | 获取工具性能指标（执行次数、成功率、平均耗时） |
| `esp_observability_status` | 获取可观测性系统状态和健康检查 |
| `esp_logs_view` | 查看最近的日志条目（支持级别过滤） |
| `esp_error_history` | 获取最近的错误历史和诊断信息 |
| `esp_diagnose_last_error` | 获取最近错误的诊断建议 |

## 使用示例

### 构建 ESP-IDF 项目

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "esp_build",
    "arguments": {}
  }
}
```

### 监控串口输出

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "esp_monitor",
    "arguments": {
      "port": "/dev/ttyUSB0",
      "seconds": 30
    }
  }
}
```

### 烧录固件

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "esp_flash",
    "arguments": {
      "port": "/dev/ttyUSB0",
      "baud": 460800
    }
  }
}
```

## 工具参数详情

### esp_project_info

获取当前项目信息

无参数

### esp_build

构建 ESP-IDF 项目（在当前目录）

无参数

### esp_flash

烧录固件到设备

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| port | string | ❌ | 串口设备（默认自动检测） |
| baud | int | ❌ | 波特率（默认: 460800） |

### esp_monitor

实时监控串口输出

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| port | string | ✅ | 串口设备（如 /dev/ttyUSB0） |
| baud | int | ❌ | 波特率（默认: 115200） |
| seconds | int | ❌ | 监控时长，秒（默认: 60） |

### esp_list_ports

列出可用的串口设备

无参数

### esp_clean / esp_fullclean

清理/完全清理构建文件

无参数

### esp_size

分析固件大小

无参数

### esp_set_target

设置芯片目标

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| target | string | ✅ | 芯片型号（esp32, esp32s2, esp32c3, esp32s3, esp32c2, esp32h2, esp32p4, esp32c6, esp32c5） |

## 可观测性

ESP-IDF MCP Server 内置了可观测性系统，提供双格式日志、性能监控和错误诊断功能。

### 日志系统

日志存储在 `.espidf-mcp/logs/` 目录：

```
.espidf-mcp/
├── logs/
│   ├── workflow.log          # 人类可读日志
│   ├── structured/           # JSON 结构化日志
│   │   ├── espidf_mcp.jsonl  # 主服务器日志
│   │   └── workflow.jsonl    # 工作流日志
│   └── archive/              # 日志轮转备份
```

**特性**：
- 彩色终端输出（INFO=绿色, WARNING=黄色, ERROR=红色）
- JSONL 格式结构化日志（AI 友好）
- 自动日志轮转（10MB，保留 5 个备份）

### 错误诊断

系统内置 15+ 种常见错误模式识别：

| 错误类型 | 模式 | 建议 |
|---------|------|------|
| 环境错误 | IDF_PATH not set | source ~/esp/esp-idf/export.sh |
| 构建错误 | region.*overflow | 减少组件大小，检查分区表 |
| 硬件错误 | Failed to connect | 检查 USB 连接，检查串口权限 |
| 烧录错误 | Failed to write | 降低波特率，检查 USB 线质量 |

### 工具参数详情

### esp_metrics_summary

获取工具性能指标摘要

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tool_name | string | ❌ | 指定工具名称（空则返回所有） |

返回：调用次数、成功率、平均耗时、最后调用时间

### esp_observability_status

获取可观测性系统状态和健康检查

无参数

返回：日志文件状态、指标收集状态、诊断引擎状态

### esp_logs_view

查看最近的日志条目

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| level | string | ❌ | 日志级别（DEBUG/INFO/WARNING/ERROR，默认: INFO） |
| tail | int | ❌ | 返回最近条目数（默认: 50） |

### esp_error_history

获取最近的错误历史和诊断信息

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| count | int | ❌ | 返回错误条数（默认: 10） |

### esp_diagnose_last_error

获取最近错误的诊断建议

无参数

返回：匹配的错误模式、修复建议、严重级别

## 环境要求

- Python 3.10+
- ESP-IDF 环境已配置（需先 source export.sh）
- pyserial（用于串口操作）

## 开发安装

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/ -v
```

### 测试覆盖率

```bash
pytest tests/ --cov=espidf_mcp --cov-report=html
```

## 依赖项

### 生产依赖

```
fastmcp>=2.14.2
mcp>=1.10.0
pyserial>=3.5
```

### 开发依赖

```
pytest>=8.0.0
pytest-cov>=4.1.0
pytest-asyncio>=0.23.0
pytest-mock>=3.14.0
```

## 技术栈

- **FastMCP**: MCP 服务器框架
- **MCP**: Model Context Protocol SDK
- **PySerial**: 串口操作库

## 文件结构

```
espidf-mcp/
├── pyproject.toml          # 项目配置和元数据
├── README.md               # 使用说明
├── LICENSE                 # MIT 许可证
├── MANIFEST.in             # 打包清单
│
├── espidf_mcp/             # Python 包
│   ├── __init__.py         # 包初始化
│   ├── __main__.py         # Python 模块入口
│   ├── cli.py              # CLI 命令入口
│   ├── server.py           # MCP 服务器核心
│   ├── project.py          # 项目检测模块
│   │
│   ├── observability/      # 可观测性模块
│   │   ├── __init__.py     # 公共 API
│   │   ├── logger.py       # 双格式日志系统
│   │   ├── metrics.py      # 性能指标收集
│   │   ├── diagnostics.py  # 错误诊断引擎
│   │   └── formatters.py   # 输出格式化
│   │
│   └── workflow/           # 工作流管理（可选）
│       ├── file_state.py   # 文件状态管理
│       └── manager.py      # 工作流编排器
│
├── tests/                  # 测试套件
│   ├── conftest.py         # pytest 配置
│   ├── test_server.py      # 服务器测试
│   ├── test_tools.py       # 工具测试
│   ├── test_e2e.py         # 端到端测试
│   └── test_observability.py # 可观测性测试
│
└── examples/               # 示例配置
    └── mcp-client-config.json
```

## 安全说明

- 不执行破坏性操作（如格式化 eFuse）
- 需要正确配置 ESP-IDF 环境
- 建议在受信任的网络环境中使用

## License

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v0.2.0 (2025-01-11)

- ✨ 新增可观测性系统
  - 双格式日志：彩色终端输出 + JSON 结构化日志
  - 性能监控：工具执行统计和瓶颈分析
  - 错误诊断：15+ 种常见错误模式识别
- ✨ 新增 5 个可观测性 MCP 工具
  - `esp_metrics_summary` - 性能指标查询
  - `esp_observability_status` - 系统状态检查
  - `esp_logs_view` - 日志查看器
  - `esp_error_history` - 错误历史查询
  - `esp_diagnose_last_error` - 错误诊断建议
- ✨ 完整的可观测性测试覆盖（31 个测试用例）
- ✨ 工作流状态管理增强

### v0.1.0 (2025-01-09)

- ✨ 首次发布
- ✨ 支持全局安装和命令行工具
- ✨ 自动检测 ESP-IDF 项目
- ✨ 友好的错误提示和建议
- ✨ 9 个 MCP 工具
- ✨ 完整的测试覆盖
