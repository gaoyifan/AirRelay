# AirRelay - 短信转发到 Telegram 的桥接器

AirRelay 是一个低成本的系统，让您在 Telegram 中接收和回复短信。它将 Air780E 设备连接到 Telegram 群组，按电话号码将对话组织到不同的主题中。

![Telegram截图](docs/telegram-screenshot.png)

## 目录

- [特性](#特性)
- [要求](#要求)
- [快速开始](#快速开始)
- [配置](#配置)
- [设备设置](#设备设置)
- [Telegram 设置](#telegram-设置)
- [机器人命令](#机器人命令)
- [故障排除](#故障排除)
- [许可证](#许可证)

## 特性

- **桥接短信和 Telegram**：Air780E 硬件接收短信，AirRelay 将其转发到 Telegram
- **在 Telegram 中阅读短信**：所有收到的短信都会显示在您的 Telegram 群组中
- **通过 Telegram 回复**：直接从 Telegram 回复短信
- **组织对话**：每个电话号码都有自己的主题
- **设备状态**：监控设备的连接和信号强度
- **多个管理员**：添加其他 Telegram 用户作为管理员
- **送达状态**：查看短信何时送达

有关系统架构的更多详细信息，请参阅[系统概述](docs/system_overview.md)。

## 要求

- **硬件**：
  - [Air780E](https://detail.tmall.com/item.htm?id=709647275715)
  - 具有短信和数据功能的 SIM 卡（需要移动网络连接）
  - USB 电源

- **软件**：
  - 用于运行桥接器的 Docker

- **账户**：
  - Telegram API 凭据（从 [Telegram API 开发工具](https://my.telegram.org/apps) 获取）
  - Telegram 机器人（通过 [BotFather](https://t.me/BotFather) 创建）
  - Cloudflare Workers KV 账户（[在此注册](https://developers.cloudflare.com/workers/wrangler/workers-kv/)）

- **网络**：
  - 具有公共 IP 地址的 MQTT 代理，可由 Air780E 设备访问

## 快速开始

1. **克隆仓库**：
   ```bash
   git clone https://github.com/gaoyifan/AirRelay.git
   cd AirRelay
   ```

2. **配置设置**：
   ```bash
   cp .env.example .env
   # 编辑 .env 填入您的凭据
   ```

3. **启动服务**：
   ```bash
   docker compose up -d
   ```

4. **查看日志**（可选）：
   ```bash
   docker compose logs -f
   ```

## 配置

使用您的凭据编辑 `.env` 文件：

### Telegram 设置
- `TG_API_ID`：您的 Telegram API ID（[在此获取](https://my.telegram.org/apps)）
- `TG_API_HASH`：您的 Telegram API Hash（[在此获取](https://my.telegram.org/apps)）
- `TG_BOT_TOKEN`：您从 [BotFather](https://t.me/BotFather) 获取的机器人令牌

### MQTT 设置
- `MQTT_HOST`：MQTT 代理主机名（默认：localhost）
- `MQTT_PORT`：MQTT 代理端口（默认：8883）
- `MQTT_USER`：MQTT 用户名（可选）
- `MQTT_PASSWORD`：MQTT 密码（可选）
- `MQTT_USE_TLS`：为 MQTT 使用 TLS（默认：true）

### EMQX 仪表板
- `EMQX_DASHBOARD_USER`：EMQX 仪表板用户名
- `EMQX_DASHBOARD_PASSWORD`：EMQX 仪表板密码

有关详细的 EMQX 配置，请参阅 [EMQX 文档](https://www.emqx.io/docs/en/v5.0/configuration/configuration.html)。

### Cloudflare Workers KV
- `CF_ACCOUNT_ID`：您的 Cloudflare 账户 ID
- `CF_NAMESPACE_ID`：您的 KV 命名空间 ID
- `CF_API_KEY`：您的 Cloudflare API 密钥

## 设备设置

### 所需硬件
- Air780E
- 具有短信功能的 SIM 卡
- USB 电源

### 设置步骤

1. **刷入固件**：
   - 下载 [LuaTools](https://wiki.luatos.com/boardGuide/flash.html)
   - 将 `luatos/main.lua` 和 `luatos/config.lua` 上传到您的 Air780E

2. **在 `config.lua` 文件中配置 MQTT**：
   ```lua
   return {
       host = "your.mqtt.server.com", -- 您的服务器 IP 或域名
       port = 8883,                   -- MQTT 端口
       isssl = true,                  -- 使用 SSL/TLS
       user = "your_username",        -- MQTT 用户名
       pass = "your_password"         -- MQTT 密码
   }
   ```

3. **开启**设备并检查是否成功连接

4. **找到您的 IMEI 号码**：
   - 将 Air780E 连接到 LuaTools
   - 设备日志可在 LuaTools 的主界面中查看
   - 查找包含 "IMEI:" 的日志条目（通常在启动时出现）
   - 将设备链接到 Telegram 时需要使用此 IMEI

## Telegram 设置

1. **创建一个启用论坛主题的 Telegram 群组**
   - 这需要创建一个超级群组并在群组设置中启用"主题"
   - 仅在 Telegram Desktop、移动应用或网页版上可用

2. **将您的机器人**添加到群组

3. **将机器人设为管理员**，具有以下权限：
   - 仅需要"管理主题"权限
   - 其他权限可保持禁用

4. **使用 `/add_admin` 命令初始化管理员访问权限**
   - 第一个运行此命令的人将成为管理员

5. **使用 `/link_device <imei>` 链接您的设备**（替换为您设备的 IMEI）
   - 使用您在 LuaTools 日志中找到的 IMEI

6. **测试设置**，向您设备的号码发送短信
   - 它应该出现在您的 Telegram 群组中

## 机器人命令

- `/start` - 介绍和帮助信息
- `/help` - 显示可用命令
- `/link_device <imei>` - 将设备连接到此群组
- `/unlink_device [imei]` - 移除设备连接
- `/link_phone <phone>` - 为电话号码创建主题
- `/unlink_phone [phone]` - 移除电话号码主题
- `/phone_info` - 显示当前主题链接的电话号码
- `/status` - 检查设备是否在线及信号强度
- `/add_admin [@username]` - 添加另一个管理员用户
- `/list_admins` - 显示所有管理员用户

## 故障排除

### 桥接器问题

- **检查日志**：运行 `docker compose logs -f` 查看错误信息
- **Telegram 凭据**：验证 API ID、Hash 和机器人令牌
- **Cloudflare 访问**：确保您的 API 密钥具有正确的权限
- **机器人权限**：机器人必须是您 Telegram 群组中的管理员，并具有"管理主题"权限
- **主题已启用**：确保您的 Telegram 群组已启用主题功能

### 设备问题

- **网络连接**：检查 SIM 卡和信号强度
- **MQTT 连接**：验证您的 MQTT 代理地址和凭据
- **SIM 卡**：确保 SIM 卡具有短信功能并启用移动数据
- **配置文件**：仔细检查 `config.lua` 文件中的值
- **IMEI 号码**：验证您在 `/link_device` 命令中使用了正确的 IMEI

## 许可证

本项目采用 MIT 许可证。 