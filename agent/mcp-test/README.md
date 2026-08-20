# MCP Test

用于测试目标 MCP HTTP 服务是否可达，并能否完成基础初始化流程。

默认目标地址：

```text
http://10.181.92.106:18081/mcp-servers/aisecurity
```

脚本会按顺序执行：

1. TCP 连通性检查
2. `GET` 探测
3. MCP `initialize`
4. `notifications/initialized`
5. `tools/list`

## 使用方式

先确保 `proxy/zhduser.ovpn` 对应的 VPN 已经连通。该配置是分流模式，只让 `10.181.92.0/24` 走 VPN。

执行：

```powershell
python .\mcp_probe.py
```

如果希望脚本自动拉起 VPN，再执行 MCP 探测：

```powershell
python .\mcp_probe.py --connect-vpn
```

探测完成后自动断开 VPN：

```powershell
python .\mcp_probe.py --connect-vpn --disconnect-vpn
```

如果你本机不是走系统 VPN，而是走本地 HTTP 代理：

```powershell
python .\mcp_probe.py --proxy http://127.0.0.1:7890
```

指定其他协议版本：

```powershell
python .\mcp_probe.py --protocol-version 2025-03-26 --protocol-version 2024-11-05
```

如果服务前面还有鉴权或网关头：

```powershell
python .\mcp_probe.py --header "Authorization: Bearer <token>" --header "X-Env: test"
```

## VPN 自动连接说明

- 当前实现基于 `OpenVPN Connect 3.x` 自带的 `ovpnconnector.exe`
- 默认会读取 [proxy/zhduser.ovpn](d:\BUS\proxy\zhduser.ovpn)
- 默认 `ovpnconnector.exe` 路径是 `C:\Program Files\OpenVPN Connect\ovpnconnector.exe`
- 该方式依赖本机已经安装过 OpenVPN Connect，并存在 `agent_ovpnconnect` 服务
- 如果是首次安装、服务不存在，仍需要管理员先完成一次初始化

自定义路径示例：

```powershell
python .\mcp_probe.py --connect-vpn `
  --vpn-connector "C:\Program Files\OpenVPN Connect\ovpnconnector.exe" `
  --vpn-profile "d:\BUS\proxy\zhduser.ovpn"
```

## 结果判断

- 返回 `MCP initialization probe succeeded.`：说明服务至少完成了初始化和 `tools/list`
- 返回 `MCP initialization probe failed.`：说明网络可达但握手或协议不匹配，日志里会打印具体阶段
- 如果 TCP 检查失败：优先检查 VPN 是否连接、路由是否生效

## 用 VPS 转发

如果你的 VPS 能访问目标内网地址，或者能访问另一个能到该内网的跳板，可以在 VPS 上运行一个最小反向代理，再由 `cloudflared` 暴露公网入口。

代理脚本：

```powershell
python .\mcp_forward_proxy.py --listen-host 127.0.0.1 --listen-port 8788 --upstream http://10.181.92.106:18081
```

这样访问：

```text
http://127.0.0.1:8788/mcp-servers/aisecurity
```

会被转发到：

```text
http://10.181.92.106:18081/mcp-servers/aisecurity
```

然后让 `cloudflared` 暴露本地 8788 端口，例如：

```powershell
cloudflared tunnel --url http://127.0.0.1:8788
```

再用生成的公网 HTTPS 地址测试：

```powershell
python .\mcp_probe.py --url https://<your-public-host>/mcp-servers/aisecurity
```

注意：

- `cloudflared` 只负责把 VPS 上的本地端口暴露出去，不负责把 VPS 接进 `10.181.92.0/24`
- 如果 VPS 本身不能访问 `10.181.92.106:18081`，这个转发链路仍然会失败
- 这个代理是最小实现，适合 MCP HTTP/SSE 调试，不适合直接当生产网关
