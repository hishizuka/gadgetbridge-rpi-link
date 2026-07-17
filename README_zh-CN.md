# gadgetbridge-rpi-link

[English](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README.md) | [日本語](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README_ja.md) | 简体中文

将 Android 手机作为 Raspberry Pi 的无线伴侣，为其提供通知、手机定位和简单的
互联网访问。所有这些功能均通过一条低功耗 BLE 连接实现。

项目官方仓库：<https://github.com/hishizuka/gadgetbridge-rpi-link>

## 这是什么？

[Gadgetbridge](https://gadgetbridge.org/) 是一款开源 Android 应用，无需厂商云账号
即可将智能手表和健身追踪器连接到手机。它可以通过面向
[Bangle.js](https://banglejs.com/) 的 BLE UART 协议转发通知、手机 GPS 位置和小型
HTTP 请求。

本软件包可将 Raspberry Pi 或其他小型 Linux 设备作为 Bangle.js 手表连接到
Gadgetbridge，并将收到的消息作为 Python 事件处理。UI 绘制、数据保存等功能由宿主
应用实现。协议详情请参阅
[Espruino Gadgetbridge 文档](https://www.espruino.com/Gadgetbridge)。

## 功能

- **在 Raspberry Pi 显示屏上显示 Android 通知。** Gadgetbridge 会转发 Android
  通知的新增、更新和删除，本库将其转换为便于 Python 处理的通知事件，供宿主 UI 显示。
  对于 CJK 等多字节文本，目前需要对 Gadgetbridge 源代码进行少量修改。请参阅
  [文本编码](#文本编码)。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-notification-to-raspberry-pi.svg" alt="将 Android 通知转发到 Raspberry Pi 显示屏" width="560">

- **将 Android 手机用作 Raspberry Pi 的 GPS 接收器。** 启用 Gadgetbridge 的手机
  GPS 功能后，Raspberry Pi 应用无需单独的 GPS 模块即可从手机接收位置更新。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-gps-to-raspberry-pi.svg" alt="将手机 GPS 位置转发到 Raspberry Pi" width="560">

- **在 Raspberry Pi 没有 RTC 时使用手机提供时间。** 本库会将 Gadgetbridge 发来的
  时间信息转换为 Python 事件，宿主应用可以将其应用到系统时钟。时间信息
  只会在 BLE 连接和 Gadgetbridge 同步后到达，而不是开机后立即到达，因此在此之前
  记录的时间戳可能不正确。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-time-to-raspberry-pi.svg" alt="Gadgetbridge连接后将手机时间应用到Raspberry Pi" width="560">

- **读取 Google Maps 逐向导航。** Gadgetbridge 将 Android 导航通知发送到
  Raspberry Pi。通过本库，Python 应用可以获取转向、导航指示和剩余距离。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-navigation-to-raspberry-pi.svg" alt="将 Google Maps 导航转发到 Raspberry Pi" width="560">

- **通过手机发送简单的 HTTP 请求。** 以 Android 应用作为网络桥接，可以获取文本或
  JSON 资源，也可以通过`method="POST"`和请求正文向外部 API 发送数据。当前
  Gadgetbridge 实现不支持二进制数据。请参阅
  [HTTP 下载行为](#http-下载行为)。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/raspberry-pi-http-via-phone.svg" alt="Raspberry Pi 通过手机获取文本或 JSON" width="560">

- **从 Raspberry Pi 触发 Android Intent。** 可以启动手机的语音助手，或执行用户
  明确允许的其他 Android 操作。

重要限制：HTTP 适用于文本和小型数据，通常需要 Bangle.js 版本的 Gadgetbridge；
CJK 等多字节 UART 文本需要支持 UTF-8 的自定义 Gadgetbridge 版本。详情请参阅
[Android 应用设置详情](#android-应用设置详情)。

**为什么使用 BLE？**

上述功能全部通过一条 BLE 连接传输。Raspberry Pi 无需使用 Wi-Fi 或蓝牙网络共享，
这对于自行车码表、可穿戴显示器等依靠电池全天运行的设备十分重要。

| 连接方式 | 手机耗电量 | 说明 |
| --- | --- | --- |
| BLE（本库） | 最低 | 通过一条连接传输通知、GPS 和轻量 HTTP。带宽较小，但足以处理文本和 JSON。 |
| 蓝牙网络共享 | 低 | 当 Raspberry Pi 需要完整 IP 连接时是不错的替代方案，少量流量下效率较高。 |
| Wi-Fi 网络共享 | 高 | 可提供完整带宽，但全天保持手机热点运行会消耗较多电量。 |

## 快速开始

本软件包需要 Python 3.13 或更高版本。托管 BLE UART 服务时，还需要可使用 BlueZ 的
Linux 环境。

1. 从 PyPI 安装软件包：

   ```sh
   pip install gadgetbridge-rpi-link
   ```

   如果使用`uv`，由于依赖项`bluez-peripheral`当前以 alpha 预发行版发布，
   需要允许预发行版本：

   ```sh
   uv pip install --prerelease=allow gadgetbridge-rpi-link
   ```

2. 启动随附的 BLE 主机进行手动冒烟测试：

   ```sh
   gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
   ```

3. 在 Android 上安装[Gadgetbridge](https://gadgetbridge.org/)。在设备发现页面启用
   `Discover unsupported devices`，扫描后长按 Raspberry Pi，选择`Add test device`。
   在对话框中选择`Bangle.js`并完成注册。
4. 启用所需功能对应的设置。详情请参阅
   [Android 应用设置详情](#android-应用设置详情)。

发行包名称为`gadgetbridge-rpi-link`，Python 导入名称为
`gadgetbridge_rpi_link`。本软件包会安装`bluez-peripheral`以支持 BlueZ 主机功能，
其他处理仅使用 Python 标准库。

## 库的功能范围

本软件包实现了以下功能：

- 将 BLE 接收的数据转换为 Python 可用的消息，并将发送数据拆分为适合 BLE 的大小。
- 将通知、查找设备请求、手机时间、位置、导航、HTTP 响应等数据转换为不同事件。
- 发送 GPS 电源请求、Android Intent 和 HTTP 请求。
- 将 HTTP 请求与响应对应起来，并保存下载的文本。
- 面向 Linux 的 BlueZ BLE UART 主机。

本库不会自行绘制通知、设置系统时间或发布 GPS 位置。这些适配器由宿主应用提供。

## 发送数据示例

发送消息时可以传入字典。本库会将其转换为 Gadgetbridge 所需的格式，并拆分为
适合 BLE 发送的数据块。

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL, GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
for data in protocol.encode_tx({"t": "info", "msg": "OK"}):
    # Send `data` through the BLE UART TX characteristic.
    ...

for data in protocol.encode_tx({"t": "status", "bat": "23"}):
    ...

for data in protocol.encode_tx({"t": "http", "url": DEFAULT_HTTP_TEXT_URL}):
    ...
```

## 接收数据示例

将 BLE UART 接收的字节传给本库后，本库会还原消息，并根据内容转换为不同事件：

```python
from gadgetbridge_rpi_link import GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
events = protocol.feed_rx(
    b'\x10GB({"t":"notify","title":"Chat","body":"Hello"})\n'
)
print(events[0])
```

## 系统时间设置示例

对于没有 RTC 的 Raspberry Pi，可以在 Gadgetbridge 连接后使用手机作为时间源。本库
会将接收的时间作为事件提供，实际更新系统时钟的操作由宿主应用负责。

从源码检出目录运行时，请先停止其他 BLE 主机，然后先以试运行模式启动示例：

```sh
PYTHONPATH=src python3 examples/set_system_time.py
```

确认能够收到手机时间并配置所需的系统权限后，添加`--apply`即可执行
`sudo -n date -u --set ...`：

```sh
PYTHONPATH=src python3 examples/set_system_time.py --apply
```

它不能完全替代开机后立即可用的 RTC：在 Android 连接并由 Gadgetbridge 发送时间前，
系统时钟不会得到校正。此示例尚未经过真机验证，因此请先使用试运行模式进行确认。

## 会话 HTTP 示例

```python
from gadgetbridge_rpi_link import GadgetbridgeSession

async def sender(message: str) -> None:
    # Send `message` through a BLE UART transport.
    ...

session = GadgetbridgeSession(sender=sender)
response = await session.request_http("https://example.com/data", timeout=10)
```

如需稳定的冒烟测试，请使用 Espruino Gadgetbridge 官方示例 URL：

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL

response = await session.request_http(DEFAULT_HTTP_TEXT_URL, timeout=30)
print(response.get("resp"))
```

## Android Intent 示例

宿主应用可以使用`send_intent(...)`执行 Gadgetbridge 支持的 Android 操作。例如，
以下代码会启动手机中配置的语音助手：

```python
session.send_intent(
    "android.intent.action.VOICE_COMMAND",
    flags=["FLAG_ACTIVITY_NEW_TASK"],
)
```

## BlueZ 主机示例

[快速开始](#快速开始)中安装的软件包需要 dbus-fast 版本的`bluez-peripheral`
0.2.0a3 或更高版本。撰写本文时推荐使用 0.2.0a5。

在可访问 BlueZ 的 Linux 主机上运行示例：

```sh
gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
```

该命令是一个用于手动验证的小型工具，作用类似于 D-Bus/GATT 冒烟测试脚本。它会持续
广播 Gadgetbridge UART 服务，直到用户停止，并接受以下键盘命令：

- `t`：提示输入一行要发送的 Gadgetbridge 文本，并原样发送。
- `g`：请求 Gadgetbridge 开启 GPS。
- `G`：发送 Android 语音命令 Intent。
- `h`：运行官方文本 HTTP 下载测试，并保存到本地文件。
- `q`：退出。

使用`t`命令时，请输入一行要发送给 Gadgetbridge 的消息正文。请直接使用 URL，
而不要使用 Markdown 链接。类 JSON 对象语法和严格 JSON 均可使用。例如：

```text
{t:"info", msg:"OK"}
{"t":"status","bat":"23"}
{t:"http", url:"https://pur3.co.uk/hello.txt"}
```

仅当宿主应用希望在收到手机当前的 GPS 状态后自动请求开启 GPS 时，才应使用
`--auto-gps`。

库代码可以通过专用子模块直接使用 BlueZ 传输：

```python
from gadgetbridge_rpi_link.bluez import BluezGadgetbridgeUartServer

server = BluezGadgetbridgeUartServer("gadgetbridge-rpi-link")
await server.start()
try:
    server.send({ "t": "info", "msg": "OK" })
finally:
    await server.stop()
```

## Android 应用设置详情

Android 应用端存在一些与 Bangle.js 相关的重要限制。

| 功能 | 所需 Android / Gadgetbridge 设置 |
| --- | --- |
| Android 通知 | 允许 Gadgetbridge 读取通知。如果只需转发部分应用，还应检查其通知过滤设置。 |
| 手机位置 | 授予 Android 位置权限，然后启用`Use phone GPS data`并设置合适的更新间隔。请参阅[手机位置](#手机位置)。 |
| Google Maps 导航 | 允许其通知。如果缺少转向或距离信息，请参阅[导航通知](#导航通知)。 |
| Android Intent | 启用`Allow Intents`。请参阅[Android Intent](#android-intent)。 |
| HTTP 文本/JSON 请求 | 使用 Bangle.js 版本，或在普通版本中按照官方[Internet Helper 设置步骤](https://gadgetbridge.org/basics/integrations/internet-helper/)操作。请参阅[HTTP 请求](#http-请求)。 |

### 获取 Gadgetbridge 版本

需要使用哪种 Gadgetbridge 版本取决于所需功能：

- 通知、手机 GPS、导航和 Android Intent 可使用普通 Gadgetbridge 版本。请根据
  [Gadgetbridge 官方网站](https://gadgetbridge.org/)提供的下载链接进行安装。
- 对于 HTTP 请求，最简单的方法是使用可直接访问互联网的 Bangle.js
  版本。可通过以下任一方式获取：
  1. 按照[Espruino Gadgetbridge 文档](https://www.espruino.com/Gadgetbridge)的说明，
     直接安装`Bangle.js Gadgetbridge`应用。
  2. 从源代码构建 Gadgetbridge 项目。在 Android Studio 中，将 Build Variant 从默认的
     `mainlineDebug`切换为以`banglejs`开头的版本，例如`banglejsDebug`。
- 普通版本也可以按照
  [Gadgetbridge 设置步骤](https://gadgetbridge.org/basics/integrations/internet-helper/)
  安装官方 Internet Helper 插件后使用该功能。
- CJK 等多字节通知文本需要使用修改过源代码的自定义版本。请参阅
  [文本编码](#文本编码)。

### 文本编码

Gadgetbridge 的 Bangle.js BLE UART 目前使用 Latin-1 发送和接收字符串。如需
交换 CJK 等多字节文本，需要使用自定义 Gadgetbridge 版本，将两个方向的字符编码
更改为 UTF-8。在 Android 开发者模式下安装该自定义版本后，本库即可接收 UTF-8
多字节消息。源代码构建方法请参阅
[获取 Gadgetbridge 版本](#获取-gadgetbridge-版本)。

### 手机位置

在已注册的 Bangle.js 设备设置中启用`Use phone GPS data`，并根据需要调整
`GPS data update interval`。这样，即使 Raspberry Pi 没有物理 GPS 接收器，宿主也能
从 Android 接收位置更新。

### 导航通知

Google Maps 导航依赖通知。Gadgetbridge 从 Android 通知中读取逐向导航指示，并
发送到 Raspberry Pi。在较新的 Android 版本中，Google Maps 的实时通知类别可能使
Gadgetbridge 无法读取指示详情。如果缺少转向或距离信息，请在 Android 的
Google Maps 通知设置中禁用`Live Updates`、`Live info`或
名称类似的通知类别。

### Android Intent

要发送 Android Intent，请在已注册设备的设置中启用`Allow Intents`。关闭此设置时，
Gadgetbridge 会拒绝 Raspberry Pi 发来的 Intent 请求。设置说明中还指出，在后台
使用此功能可能需要 Android 的“显示在其他应用上层”权限。

### HTTP 请求

要发送 HTTP 请求，请使用 Bangle.js 版本，或按照官方
[Internet Helper 设置步骤](https://gadgetbridge.org/basics/integrations/internet-helper/)
配置普通版 Gadgetbridge。注册 Bangle.js 设备后，请在其设置中启用
`Allow Internet Access`。

## HTTP 下载行为

附带的 HTTP 文件保存功能会将从 Gadgetbridge 收到的内容写入文件。当前 Android 版
Gadgetbridge 的 Bangle.js HTTP 支持面向文本，因此请将其用于文本和小型下载。

`binary=None|True|False`选项仅控制如何将已经收到的数据写入磁盘：

- `None`：仅当输出路径具有`.bin`、`.fit`、`.zip`等已知二进制扩展名时，才将字符串
  写为二进制。
- `True`：尽可能将旧式 Gadgetbridge 二进制字符串保留为 Latin-1 字节；对于从
  Base64 还原的 Unicode 文本，则回退到 UTF-8。
- `False`：即使输出路径扩展名通常表示二进制文件，也会使用指定编码将字符串数据
  写为文本。

以字节形式收到的数据会原样写入。本库不会嗅探响应内容；宿主应明确指定预期的下载
路径，或在写入约定更清晰时传入`binary=True|False`。

当前 Gadgetbridge Android 端的 HTTP 功能不支持任意二进制 HTTP 下载。通过
Android 文本通道返回的大型二进制响应可能在 Gadgetbridge 端已经被插入替换字符，
宿主可能无法恢复。要支持通用二进制下载，需要让 Gadgetbridge 在传输过程中保留
字节，例如发送原始字节，或将其编码为 Base64 文本。

## 开发说明

源码树不需要硬编码的 BLE 地址、设备主机名或私有本地文件系统路径。测试使用合成
数据、`example.com`以及公开的 Espruino 文本示例 URL。`__pycache__`等生成文件、
本地交接记录和设备专用日志不应包含在发布的软件包中。

## 相关库

Linux BLE 主机基于以下开源库构建：

- [bluez-peripheral](https://github.com/spacecheese/bluez_peripheral)提供使用 BlueZ
  GATT API 构建 BLE 外围设备的 Python 接口。
- [dbus-fast](https://github.com/bluetooth-devices/dbus-fast)提供
  `bluez-peripheral`与 BlueZ 通信时使用的异步 D-Bus 实现。

感谢这些项目的作者和贡献者，使本项目得以实现。

## 许可证

MIT 许可证。详情请参阅`LICENSE`。
