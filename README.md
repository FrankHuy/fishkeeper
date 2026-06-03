# fishkeeper

闲管家 (Goofish/Xianyu) Open Platform Skill — 闲鱼店铺商品管理、订单处理、库存同步的 Agent 工具包。

## 为什么叫 fishkeeper？

**fishkeeper = 闲管家** — 闲鱼（鱼 = fish）+ 管家（keeper）的英文直译。

项目名 **fishkeeper** 是本工具的品牌名，skill 名 **goofish** 则对应闲管家开放平台的官方英文名（Goofish Open Platform）。两者指向同一个东西，只是在不同层级使用：

| 层级 | 名称 | 含义 |
|------|------|------|
| 仓库名 / 项目名 | fishkeeper | 闲管家 — 品牌名，体现"管鱼"的定位 |
| Skill 名 | goofish | 闲管家开放平台的官方 API 标识，用于 agent 关键词匹配 |

在 Hermes 中引用时使用 skill 名 `goofish`，项目名 `fishkeeper` 出现在仓库地址和文档中。

## 功能

- 商品全生命周期管理（创建、编辑、上架、下架、删除、批量操作）
- 订单管理（查询、发货、改价、卡密查询）
- 类目/属性/规格查询
- 多 Agent 并行编排（库存快照、批量上架、批量发货等）
- MD5 签名认证，支持自研/ERP/业务方三种接入模式

## 项目结构

```
fishkeeper/
├── README.md
├── LICENSE
└── skills/
    └── goofish/
        ├── SKILL.md              # Skill 定义文件（触发条件、API 概览、使用说明）
        ├── config.example.yaml   # 配置模板
        ├── scripts/
        │   ├── signer.py         # MD5 签名工具
        │   ├── client.py         # API 客户端（全部 19 个端点）
        │   └── orchestrator.py   # 多 Agent 任务编排器
        └── references/
            ├── api-reference.md      # API 完整参考文档
            └── multi-agent-patterns.md  # 多 Agent 编排模式
```

## Agent 类应用安装指南

本仓库是一个 Hermes Agent Skill，可被任何支持 Hermes Skill 格式的 Agent 应用加载。以下是各类 Agent 的安装方法。

### 1. Hermes Agent

Hermes Agent 是本 Skill 的原生运行环境。

**方式 A：通过 git clone 安装（推荐）**

```bash
# 将仓库克隆到 Hermes skills 目录
git clone https://github.com/FrankHuy/fishkeeper.git ~/.hermes/skills/fishkeeper

# 或者克隆到自定义位置，然后在 config.yaml 中注册
git clone https://github.com/FrankHuy/fishkeeper.git /opt/fishkeeper
# 在 ~/.hermes/config.yaml 中添加：
# skills:
#   - /opt/fishkeeper/skills/goofish
```

**方式 B：通过 hermes CLI 安装**

```bash
hermes skills install https://github.com/FrankHuy/fishkeeper.git
```

**方式 C：手动复制**

```bash
# 只需将 skills/goofish 目录复制到 Hermes 的 skills 路径下
cp -r skills/goofish ~/.hermes/skills/goofish
```

**配置凭据**

安装完成后，配置闲管家 API 凭据：

```bash
# 方式 1：环境变量（推荐用于 Docker/CI）
export GOOFISH_APP_KEY="你的AppKey"
export GOOFISH_APP_SECRET="你的AppSecret"

# 方式 2：配置文件
mkdir -p ~/.goofish
cp skills/goofish/config.example.yaml ~/.goofish/config.yaml
# 编辑 ~/.goofish/config.yaml，填入 app_key 和 app_secret
```

**安装 Python 依赖**

```bash
pip install pyyaml requests
```

**验证安装**

```bash
# 测试 API 连接
python ~/.hermes/skills/goofish/scripts/client.py --test

# 预览编排任务
python ~/.hermes/skills/goofish/scripts/orchestrator.py --recipe inventory-sync --dry-run
```

安装成功后，Hermes Agent 在对话中遇到闲鱼/闲管家相关任务时会自动加载此 Skill。

### 2. Claude Code (Anthropic)

Claude Code 通过 CLAUDE.md 和文件系统发现项目 Skill。

```bash
# 克隆到项目目录
git clone https://github.com/FrankHuy/fishkeeper.git /path/to/your-project/fishkeeper

# 在项目根目录的 CLAUDE.md 中添加引用：
# When working with 闲鱼/闲管家/Xianyu API, read and follow the skill at fishkeeper/skills/goofish/SKILL.md
```

Claude Code 会在读取 CLAUDE.md 后按需加载 Skill 指令。

### 3. OpenAI Codex CLI

Codex CLI 通过 AGENTS.md 发现项目规则和工具。

```bash
# 克隆到项目目录
git clone https://github.com/FrankHuy/fishkeeper.git /path/to/your-project/fishkeeper

# 在项目根目录的 AGENTS.md 中添加：
# ## 闲管家 (Goofish) Skill
# For Xianyu/闲管家 API operations, use the client at fishkeeper/skills/goofish/scripts/client.py.
# Read fishkeeper/skills/goofish/SKILL.md for full usage instructions and API details.
# Dependencies: pip install pyyaml requests
```

### 4. Cursor / Windsurf / 其他 AI IDE

这些 IDE 通常通过 `.cursorrules` 或项目级指令文件集成。

```bash
# 克隆到项目目录
git clone https://github.com/FrankHuy/fishkeeper.git /path/to/your-project/fishkeeper

# 在 .cursorrules 中添加：
# When the user asks about 闲鱼/闲管家/Xianyu store management, refer to fishkeeper/skills/goofish/SKILL.md for API documentation and use the Python client at fishkeeper/skills/goofish/scripts/client.py.
```

### 5. 通用 MCP Server 集成

如果你的 Agent 应用支持 MCP (Model Context Protocol)，可以将本 Skill 封装为 MCP Tool：

```python
# 示例：将 GoofishClient 方法暴露为 MCP tools
from skills.goofish.scripts.client import GoofishClient

client = GoofishClient()

# 每个 client 方法可直接映射为 MCP tool：
# - goofish_query_stores
# - goofish_query_products
# - goofish_create_product
# - goofish_ship_order
# ... 等等
```

### 6. 自定义 Agent 框架

任何 Agent 框架只要能执行 Python 脚本，都可以使用本 Skill：

```python
import sys
sys.path.insert(0, "/path/to/fishkeeper/skills/goofish/scripts")

from client import GoofishClient

client = GoofishClient()  # 自动从环境变量或配置文件加载凭据

# 调用任意 API
stores = client.query_stores()
products = client.query_all_products()
orders = client.query_all_orders()
```

## 快速开始

```bash
# 1. 安装依赖
pip install pyyaml requests

# 2. 配置凭据
export GOOFISH_APP_KEY="你的AppKey"
export GOOFISH_APP_SECRET="你的AppSecret"

# 3. 测试连接
python skills/goofish/scripts/client.py --test

# 4. 使用编排器
python skills/goofish/scripts/orchestrator.py --recipe inventory-sync --dry-run
```

## API 覆盖

| 类别 | 端点数 |
|------|--------|
| 用户（店铺查询） | 1 |
| 商品（CRUD + 类目/属性/规格） | 12 |
| 订单（列表/详情/发货/改价/卡密） | 5 |
| 推送（Webhook 回调） | 3（入站） |
| 其他（快递公司查询） | 1 |
| **合计** | **19 API + 3 Webhook** |

完整 API 文档见 `skills/goofish/references/api-reference.md`。

## License

MIT — see [LICENSE](LICENSE)


## 🔗 Friend Links

- 🐧 [**LinuxDO**](https://linux.do) — A community for tech enthusiasts
