# gadgetbridge-rpi-link

[English](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README.md) | 日本語 | [简体中文](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README_zh-CN.md)

Androidスマートフォンを、Raspberry Piに通知・位置情報・簡易的なインターネット
アクセスを提供するワイヤレスコンパニオンとして利用します。これらの機能は、
省電力な1本のBLE接続で利用できます。

正規リポジトリ: <https://github.com/hishizuka/gadgetbridge-rpi-link>

## これは何?

[Gadgetbridge](https://gadgetbridge.org/) は、ベンダーのクラウドアカウントなしで
スマートウォッチやフィットネストラッカーをスマートフォンに接続できるオープンソースの
Androidアプリです。[Bangle.js](https://banglejs.com/)向けのBLE UARTプロトコルを
使い、通知、スマートフォンのGPS位置情報、小さなHTTPリクエストを転送できます。

本パッケージを使うと、Raspberry Piなどの小型LinuxデバイスをBangle.jsウォッチ
としてGadgetbridgeに接続し、受信したメッセージをPythonのイベントとして扱えます。
UIの描画やデータの保存などは、ホストアプリケーション側で実装します。プロトコルの
詳細は[Espruino Gadgetbridgeドキュメント](https://www.espruino.com/Gadgetbridge)を
参照してください。

## できること

- **Androidの通知をRaspberry Piのディスプレイに表示する。** Gadgetbridgeが
  Androidの通知の追加/更新/削除パケットを転送し、本ライブラリがそれらを型付きの
  通知イベントにパースするので、ホストUIでそのまま描画できます。CJKなどの
  マルチバイト文字については、現状Gadgetbridgeのソースへの小さな修正が必要です。
  [テキストエンコーディング](#テキストエンコーディング)を参照してください。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-notification-to-raspberry-pi.svg" alt="AndroidからRaspberry Piのディスプレイへ転送された通知" width="560">

- **AndroidスマートフォンをRaspberry PiのGPS受信機として使う。** Gadgetbridgeの
  スマホGPS機能を有効にすると、Raspberry Pi側のアプリケーションはGPSモジュール
  なしでスマートフォンから位置情報の更新を受け取れます。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-gps-to-raspberry-pi.svg" alt="スマホのGPS位置情報をRaspberry Piへ転送" width="560">

- **RTCを搭載しないRaspberry Piの時刻をスマートフォンから取得する。** 本ライブラリ
  はGadgetbridgeの`setTime(...)`メッセージを`SetTimeEvent`としてパースし、ホスト
  アプリケーションでシステム時刻に反映できます。時刻情報は起動直後ではなく、BLE
  接続とGadgetbridgeの同期後に届くため、それ以前に記録したタイムスタンプは正しく
  ない場合があります。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-time-to-raspberry-pi.svg" alt="Gadgetbridge接続後にスマートフォンの時刻をRaspberry Piへ反映" width="560">

- **Google Mapsのターンバイターンナビゲーションを読み取る。** Gadgetbridgeは
  Androidのナビゲーション通知をナビゲーションパケットに変換し、本ライブラリが
  距離/アクション/指示の各フィールドにパースします。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-navigation-to-raspberry-pi.svg" alt="Google MapsのナビゲーションをRaspberry Piへ転送" width="560">

- **スマートフォン経由で簡単なHTTPリクエストを行う。** Androidアプリをネットワーク
  ブリッジとして、テキストやJSONリソースの取得、さらに`method="POST"`とリクエスト
  ボディによる外部APIへのデータ送信ができます。バイナリペイロードは現在の
  Gadgetbridgeの実装ではサポートされていません。
  [HTTPダウンロードの挙動](#httpダウンロードの挙動)を参照してください。

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/raspberry-pi-http-via-phone.svg" alt="Raspberry Piからスマホ経由でテキスト/JSONを取得" width="560">

- **Raspberry Pi側からAndroidインテントを発行する。** スマートフォンの音声
  アシスタントの起動など、ユーザーが意図的に許可したAndroidのアクションを実行
  できます。

重要な制約として、HTTPはテキストおよび小さなペイロード向けで、通常はBangle.js
フレーバーのGadgetbridgeビルドが必要です。また、CJKなどのマルチバイトUART
テキストにはUTF-8対応のカスタムビルドが必要です。詳しくは
[Androidアプリ側の設定詳細](#androidアプリ側の設定詳細)を参照してください。

**なぜBLEなのか?**

上記のすべては1本のBLE接続でやり取りされます。Raspberry PiにはWi-Fiテザリングも
Bluetoothテザリングも不要です。これはサイクルコンピュータやウェアラブル
ディスプレイのような、バッテリー駆動で終日使う構成では重要なポイントです。

| 接続方式 | スマホのバッテリー消費 | 備考 |
| --- | --- | --- |
| BLE (本ライブラリ) | 最小 | 通知・GPS・軽量なHTTPを1本の接続で。帯域は小さいものの、テキスト/JSONには十分。 |
| Bluetoothテザリング | 小 | Raspberry Piに本物のIP接続が必要な場合の良い代替手段。トラフィックを軽く保つ限り効率的。 |
| Wi-Fiテザリング | 大 | 帯域はフルに使えるが、スマホのホットスポット用無線を終日動かし続けるのはコストが高い。 |

## クイックスタート

本パッケージにはPython 3.13以降が必要です。BLE UARTサービスをホストする場合は、
BlueZを利用できるLinux環境も必要です。

1. パッケージをインストールします。

   ```sh
   pip install gadgetbridge-rpi-link
   ```

2. 手動スモークテスト用のBLEホストを起動します。

   ```sh
   gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
   ```

3. Androidに[Gadgetbridge](https://gadgetbridge.org/)をインストールします。
   検出画面で`未サポートのデバイスも表示する`を有効にしてスキャンし、Raspberry Pi
   を長押しして`テスト デバイスを追加する`を選びます。ダイアログで`Bangle.js`を
   選択して登録します。
4. 使う機能に必要な設定を有効にします。詳しくは
   [Androidアプリ側の設定詳細](#androidアプリ側の設定詳細)を参照してください。

配布名は`gadgetbridge-rpi-link`、Pythonのインポート名は
`gadgetbridge_rpi_link`です。パース処理とセッションモジュールはPython標準
ライブラリのみを使い、配布パッケージはBlueZホスト用に`bluez-peripheral`を
インストールします。

## ライブラリの範囲

本パッケージには次の機能が実装されています。

- UARTフレームのデコード、TXチャンクのエンコード、`GB(...)`形式のJSON風
  メッセージのパース。
- 通知、デバイス探索、スマートフォン時刻(`setTime(...)`)、位置情報、
  ナビゲーション、HTTPレスポンス、パース失敗、未知メッセージの型付きイベント。
- GPS電源要求、Androidインテント、HTTPリクエストの送信。
- HTTPリクエストの非同期追跡とテキスト向けダウンロードヘルパー。
- Linux向けBlueZ BLE UARTホスト。

本ライブラリ自身は通知の描画、システム時刻の設定、GPS位置情報の配信を行いません。
それらのアダプターはホストアプリケーションが提供します。

## プロトコルAPIの例

送信メッセージは辞書として渡せます。`FrameEncoder`がGadgetbridge UART TXパスに
必要なフレーミングと末尾改行を追加します。

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL, GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
for chunk in protocol.encode_tx({"t": "info", "msg": "OK"}):
    # Send `chunk` through the BLE UART TX characteristic.
    ...

for chunk in protocol.encode_tx({"t": "status", "bat": "23"}):
    ...

for chunk in protocol.encode_tx({"t": "http", "url": DEFAULT_HTTP_TEXT_URL}):
    ...
```

## パーサーの例

受信したGadgetbridgeメッセージは、UARTストリームから`GB(...)`ラッパーを受け取った
後にパースされます:

```python
from gadgetbridge_rpi_link import GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
events = protocol.feed_rx(
    b'\x10GB({"t":"notify","title":"Chat","body":"Hello"})\n'
)
print(events[0])
```

## システム時刻設定の例

RTCを搭載しないRaspberry Piでは、Gadgetbridge接続後にスマートフォンを時刻情報源
として利用できます。本ライブラリは`SetTimeEvent`を生成し、実際のシステム時刻への
反映はホストアプリケーションが行います。

ソースチェックアウトから、ほかのBLEホストを停止したうえで、まずdry-runモードで
exampleを実行します。

```sh
PYTHONPATH=src python3 examples/set_system_time.py
```

`setTime`イベントを受信できることを確認し、必要なシステム権限を設定した後、
`--apply`を付けると`sudo -n date -u --set ...`を実行します。

```sh
PYTHONPATH=src python3 examples/set_system_time.py --apply
```

これは起動直後から利用できるRTCの完全な代替ではありません。Androidが接続し、
Gadgetbridgeから時刻が届くまで時計は補正されません。このexampleは実機検証前の
ため、最初はdry-runモードで確認してください。

## セッションHTTPの例

```python
from gadgetbridge_rpi_link import GadgetbridgeSession

async def sender(message: str) -> None:
    # Send `message` through a BLE UART transport.
    ...

session = GadgetbridgeSession(sender=sender)
response = await session.request_http("https://example.com/data", timeout=10)
```

安定したスモークチェックには、Espruino Gadgetbridge公式のサンプルURLを使って
ください:

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL

response = await session.request_http(DEFAULT_HTTP_TEXT_URL, timeout=30)
print(response.get("resp"))
```

## Androidインテントの例

ホストアプリケーションは、Gadgetbridgeがサポートするアクションに対して
`send_intent(...)`を使えます。たとえば、次の例はスマートフォンに設定された
音声アシスタントを起動します:

```python
session.send_intent(
    "android.intent.action.VOICE_COMMAND",
    flags=["FLAG_ACTIVITY_NEW_TASK"],
)
```

## BlueZホストの例

[クイックスタート](#クイックスタート)でインストールする本パッケージには、
dbus-fastベースのアルファ系列である`bluez-peripheral`
0.2.0a3以降が必要です。執筆時点では0.2.0a5が推奨リリースです。

BlueZにアクセスできるLinuxホストでサンプルを実行します:

```sh
gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
```

このコマンドは、DBus/GATTのスモークテストスクリプトに近い目的の小さな手動プローブ
です。停止されるまでGadgetbridge UARTサービスをアドバタイズし、簡単なキーボード
コマンドを受け付けます:

- `t`: 送信するGadgetbridgeテキスト1行の入力を促し、そのまま送信します。
- `g`: GadgetbridgeにGPS ONを要求します。
- `G`: Androidの音声コマンドインテントを送信します。
- `h`: 公式のテキストHTTPダウンロードテストを実行し、ローカルファイルに保存します。
- `q`: 終了します。

`t`コマンドには、受信時の`GB(...)`ラッパーを付けずにGadgetbridgeメッセージを
1行で入力します。MarkdownリンクではなくURLをそのまま使ってください。JSON風の
オブジェクト構文と厳密なJSONのどちらも利用できます。例:

```text
{t:"info", msg:"OK"}
{"t":"status","bat":"23"}
{t:"http", url:"https://pur3.co.uk/hello.txt"}
```

`--auto-gps`は、`is_gps_active`受信後にホストアプリケーションが意図的に
Gadgetbridge GPSを要求したい場合にのみ使用してください。

リポジトリには、同じインストール済みコマンドの薄いソースチェックアウト用
ラッパーとして`examples/callback_bluez_service.py`も残しています。

ライブラリコードからは、専用サブモジュール経由でBlueZトランスポートを
直接使えます:

```python
from gadgetbridge_rpi_link.bluez import BluezGadgetbridgeUartServer

server = BluezGadgetbridgeUartServer("gadgetbridge-rpi-link")
await server.start()
try:
    server.send({ "t": "info", "msg": "OK" })
finally:
    await server.stop()
```

## Androidアプリ側の設定詳細

Androidアプリ側には、Bangle.js固有の重要な制約がいくつかあります。

| 機能 | 必要なAndroid / Gadgetbridge設定 |
| --- | --- |
| Androidの通知 | Gadgetbridgeに通知アクセスを許可します。一部のアプリだけ転送する場合は通知フィルターも確認します。 |
| スマホの位置情報 | Androidの位置情報権限を付与し、`Android の GPS データを使用する`と実用的な更新間隔を設定します。詳しくは[スマートフォンの位置情報](#スマートフォンの位置情報)を参照してください。 |
| Google Mapsナビゲーション | 通知を許可します。`nav`パケットが空の場合は[ナビゲーション通知](#ナビゲーション通知)を参照してください。 |
| Androidインテント | `インテントを許可する`を有効にします。詳しくは[Androidインテント](#androidインテント)を参照してください。 |
| HTTPテキスト/JSONリクエスト | Bangle.jsフレーバーのビルドを使うか、通常版で公式の[Internet Helper設定手順](https://gadgetbridge.org/basics/integrations/internet-helper/)に従います。詳しくは[HTTPリクエスト](#httpリクエスト)を参照してください。 |

### Gadgetbridgeビルドの入手

必要なGadgetbridgeビルドは、使いたい機能によって異なります:

- 通知、スマホGPS、ナビゲーション、Androidインテントは、通常のGadgetbridge
  リリースで動作します。[Gadgetbridge公式サイト](https://gadgetbridge.org/)の
  ダウンロード案内からインストールしてください。
- HTTPリクエスト(`t:"http"`)には、直接インターネットへアクセスできる
  Bangle.jsフレーバーのビルドを使うのが最も簡単です。次のいずれかの方法で
  入手します:
  1. [Espruino Gadgetbridgeドキュメント](https://www.espruino.com/Gadgetbridge)
     の説明に沿って、`Bangle.js Gadgetbridge`アプリを直接インストールする。
  2. Gadgetbridgeプロジェクトをソースからビルドする。Android Studioの
     Build Variantsをデフォルトの`mainlineDebug`から`banglejsDebug`など
     `banglejs`で始まるものに切り替えてビルドします。
- 通常版でも、公式のInternet Helperアドオンを
  [Gadgetbridgeの設定手順](https://gadgetbridge.org/basics/integrations/internet-helper/)
  に従って導入すれば利用できます。
- CJKなどのマルチバイト通知テキストには、ソースを修正したカスタムビルドが
  必要です。[テキストエンコーディング](#テキストエンコーディング)を参照して
  ください。

### テキストエンコーディング

GadgetbridgeのBangle.js UART実装は、現在、Gadgetbridgeプロジェクト内の
`app/src/main/java/nodomain/freeyourgadget/gadgetbridge/service/devices/banglejs/BangleJSDeviceSupport.java`
において、UART文字列の送受信に`StandardCharsets.ISO_8859_1`を使用しています。
確認したソースでは、スマホからデバイスへの送信処理(`uartTx(...)`)とデバイスから
スマホへの受信処理の両方にこの記述があります。このUARTプロトコルで直接マルチバイトテキストをやり取りする
必要がある場合は、Bangle.js UARTの文字セット指定を`StandardCharsets.UTF_8`に
変更したカスタムGadgetbridgeビルドが必要です。そのカスタムビルドをAndroidの
開発者モードでインストールすれば、UTF-8のマルチバイトメッセージを本ライブラリで
受信できます。ソースからのビルド手順は
[Gadgetbridgeビルドの入手](#gadgetbridgeビルドの入手)を参照してください。

### スマートフォンの位置情報

登録済みBangle.jsデバイスの設定で`Android の GPS データを使用する`をONにし、
必要に応じて`GPS データの更新間隔`を調整してください。これにより、Raspberry Piに
物理的なGPS受信機がなくても、ホストはAndroidから位置情報の更新を受け取れます。

### ナビゲーション通知

Google Mapsのナビゲーションは通知ベースです。GadgetbridgeはAndroidの通知から
ターンバイターンの指示を読み取り、`nav`パケットとして送信します。最近のAndroid
バージョンでは、Google Mapsのライブ通知カテゴリによって指示の詳細がGadgetbridge
から見えなくなることがあります。`action`や`distance`などのフィールドを含まない
`nav`パケットが届く場合は、AndroidのGoogle Maps通知設定で`Live Updates`、
`ライブ情報`などの名称の通知カテゴリを無効にしてください。

### Androidインテント

送信側の`t:"intent"`パケットには、登録済みデバイスの設定`インテントを許可する`
(`device_intents`)が必要です。Gadgetbridgeのソースでは、このスイッチがオフの
場合`handleIntent(...)`がインテントパケットを拒否します。Gadgetbridgeの日本語UI
ではこの設定は`インテントを許可する`と表示され、その説明には、バックグラウンド
での使用にはAndroidの他のアプリの上に重ねて表示する権限が必要になる場合があると
記載されています。

### HTTPリクエスト

HTTPリクエストには、Bangle.jsフレーバーのビルドを使うか、通常版Gadgetbridgeを
公式の[Internet Helper設定手順](https://gadgetbridge.org/basics/integrations/internet-helper/)
に従って構成します。Bangle.jsデバイスを登録した後、その設定で
`インターネット接続を許可する`(`device_internet_access`)を有効にしてください。

## HTTPダウンロードの挙動

`GadgetbridgeSession.download_http_file(...)`は、GadgetbridgeのHTTPレスポンスの
`resp`フィールドを書き出します。現在のAndroid版Gadgetbridge Bangle.js HTTP
サポートはテキスト指向のため、このヘルパーはテキスト/小さなペイロードの
ダウンロードパスとして扱ってください。

`binary=None|True|False`オプションは、すでに受信済みのペイロードをディスクに
どう書き込むかだけを制御します:

- `None`は、出力パスが`.bin`、`.fit`、`.zip`などの既知のバイナリ拡張子を持つ
  場合にのみ、文字列ペイロードをバイナリとして書き込みます。
- `True`は、可能な場合はレガシーなGadgetbridgeバイナリ文字列をLatin-1バイト列
  として保持し、`atob(...)`からデコードされたUnicodeテキストについてはUTF-8に
  フォールバックします。
- `False`は、出力パスの拡張子が通常バイナリとして扱われる場合でも、文字列
  ペイロードを指定されたエンコーディングのテキストとして書き込みます。

バイトペイロードは常にバイト列として書き込まれます。本ライブラリは意図的に
レスポンス内容のスニッフィングを行いません。ホスト側で期待するダウンロードパスを
定義するか、書き込み契約が明確な場合は`binary=True|False`を渡してください。

任意のバイナリHTTPダウンロードは、現在のGadgetbridge Android側`t:"http"`実装では
サポートされていません。Androidのテキストパス経由で返される大きなバイナリ
レスポンスは、Gadgetbridge側ですでに置換文字が挿入された状態で届くことがあり、
ホスト側では復元できない場合があります。汎用的なバイナリダウンロードに対応する
には、Gadgetbridge側のHTTPハンドラーをバイト保存型のレスポンスパスに変更する
必要があります。たとえば生バイトのトランスポートや、テキストリーダーの代わりに
文書化されたbase64/`atob(...)`契約などです。

## 開発者向け情報

ソースツリーは、ハードコードされたBLEアドレス、デバイスのホスト名、ローカル
ファイルシステムの個人的なパスを必要としません。テストは合成ペイロード、
`example.com`、および公開されているEspruinoのテキストサンプルURLを使用します。
`__pycache__`などの生成ファイル、ローカルの引き継ぎメモ、デバイス固有のログは
公開パッケージに含めないでください。

## 関連ライブラリ

Linux向けBLEホストは、次のオープンソースライブラリを利用しています。

- [bluez-peripheral](https://github.com/spacecheese/bluez_peripheral)は、BlueZの
  GATT APIを使ってBLEペリフェラルを構築するためのPythonインターフェースを提供
  します。
- [dbus-fast](https://github.com/bluetooth-devices/dbus-fast)は、
  `bluez-peripheral`がBlueZと通信するために使う非同期D-Bus実装を提供します。

本プロジェクトを支える作者およびコントリビューターの皆様に感謝します。

## ライセンス

MITライセンス。詳細は`LICENSE`を参照してください。
