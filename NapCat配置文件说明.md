# NapCat配置文件说明

## 配置文件位置

```
E:\MaiM\NapCat.Shell\config\
├── onebot11_2477702109.json  # 君君的OneBot11配置 ✓
├── onebot11_1033245881.json  # 伊伊的OneBot11配置 ✓ (已配置)
├── napcat_2477702109.json    # 君君的NapCat配置
├── napcat_1033245881.json    # 伊伊的NapCat配置
└── napcat.json               # 全局NapCat配置
```

---

## 已配置的文件

### onebot11_1033245881.json (伊伊)

**配置内容**:
```json
{
  "network": {
    "websocketClients": [
      {
        "name": "WsClient-YiYi",
        "enable": true,
        "url": "ws://127.0.0.1:8097",
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "reconnectInterval": 5000,
        "token": "",
        "debug": false,
        "heartInterval": 30000
      }
    ]
  },
  "enableLocalFile2Url": true,
  "parseMultMsg": true
}
```

**说明**:
- **url**: `ws://127.0.0.1:8097` - 连接到伊伊的适配器（端口8097）
- **heartInterval**: 30000ms (30秒) - 心跳间隔
- **enableLocalFile2Url**: true - 启用本地文件转URL（用于发送图片）
- **parseMultMsg**: true - 解析合并转发消息

---

## 配置模式说明

### WebSocket Client模式（当前使用）

NapCat作为客户端，主动连接到适配器：

```
NapCat (Client) ──连接──> 适配器 (Server)
     ↓                        ↓
  QQ账号                   MaiBot
```

**优点**:
- 适配器不需要等待连接
- 重连机制更可靠
- 配置更简单

**配置**:
```json
"websocketClients": [
  {
    "url": "ws://127.0.0.1:8097"  // NapCat主动连接这个地址
  }
]
```

### WebSocket Server模式（备选）

NapCat作为服务器，等待适配器连接：

```
NapCat (Server) <──连接── 适配器 (Client)
     ↓                        ↓
  QQ账号                   MaiBot
```

**配置**:
```json
"websocketServers": [
  {
    "host": "0.0.0.0",
    "port": 8097  // NapCat监听这个端口
  }
]
```

---

## 适配器配置对应关系

### 君君的配置

**NapCat配置** (`onebot11_2477702109.json`):
```json
"websocketClients": [
  {
    "url": "ws://127.0.0.1:8096"  // 连接到8096端口
  }
]
```

**适配器配置** (`MaiBot-Napcat-Adapter/config.toml`):
```toml
[napcat_server]
port = 8096  // 监听8096端口
```

### 伊伊的配置

**NapCat配置** (`onebot11_1033245881.json`):
```json
"websocketClients": [
  {
    "url": "ws://127.0.0.1:8097"  // 连接到8097端口
  }
]
```

**适配器配置** (`MaiBot-Napcat-Adapter-Yiyi/config.toml`):
```toml
[napcat_server]
port = 8097  // 监听8097端口
```

---

## 配置验证

### 检查配置是否正确

1. **检查端口一致性**:
   - NapCat的url端口 = 适配器的监听端口
   - 君君: 8096
   - 伊伊: 8097

2. **检查心跳间隔一致性**:
   - NapCat的heartInterval = 适配器的heartbeat_interval
   - 都是30000ms (30秒)

3. **检查连接方向**:
   - NapCat使用websocketClients（主动连接）
   - 适配器监听端口（被动接受）

---

## 其他配置选项

### enableLocalFile2Url

**作用**: 将本地文件路径转换为URL

**建议**: `true`

**原因**:
- 发送图片时需要
- 发送表情包时需要
- 发送文件时需要

### parseMultMsg

**作用**: 解析合并转发消息

**建议**: `true`

**原因**:
- 可以读取转发消息的内容
- 可以处理群聊中的转发消息

### musicSignUrl

**作用**: 音乐卡片签名服务URL

**建议**: 留空（除非需要发送音乐卡片）

---

## 常见问题

### Q1: 修改配置后需要重启吗？

A: 是的，修改OneBot11配置后需要重启NapCat。

### Q2: 如何验证配置是否生效？

A: 启动NapCat后，查看日志：
```
[INFO] WebSocket client connected to ws://127.0.0.1:8097
```

### Q3: 端口冲突怎么办？

A: 同时修改两个文件：
1. NapCat配置中的url端口
2. 适配器配置中的监听端口

### Q4: 为什么要用不同的端口？

A: 因为两个机器人需要独立的通信通道，避免消息混乱。

---

## 配置检查清单

启动前检查：

- [x] onebot11_1033245881.json 已配置
- [x] websocketClients.url = ws://127.0.0.1:8097
- [x] heartInterval = 30000
- [x] enableLocalFile2Url = true
- [x] parseMultMsg = true
- [x] 适配器端口 = 8097
- [x] 端口不与君君冲突（君君用8096）

---

## 总结

✓ **已完成配置**: `onebot11_1033245881.json`

**配置要点**:
1. 使用WebSocket Client模式
2. 连接到 ws://127.0.0.1:8097
3. 心跳间隔30秒
4. 启用本地文件转URL
5. 启用合并消息解析

**下一步**: 启动NapCat和适配器，验证连接是否成功。
