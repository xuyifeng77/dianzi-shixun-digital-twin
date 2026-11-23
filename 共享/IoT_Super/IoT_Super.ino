/* =====================================================================
 * 创乐博 CLB · Arduino UNO R3 IOT SUPER
 * 物联网最小系统：温湿度 + 光照上云 / 超温自动散热 / 本地声光报警
 * ---------------------------------------------------------------------
 * 接线：D7 DHT11 | A0 光敏AO | D6 继电器 | D4 蜂鸣器
 *       D2←ESP TXD | D3→ESP RXD | D13 板载状态灯 | 全部共地
 * 平台：ThingSpeak（HTTP 80 端口，免 HTTPS；免费版间隔 ≥15s）
 * 依赖：DHT sensor library (Adafruit) + Adafruit Unified Sensor
 * 指令：1 继电器吸合 / 0 断开 / a 恢复自动 / m 静音切换
 * 注意：上传走 D0/D1，与软串口 D2/D3 互不干扰，烧录无需拔线
 * ===================================================================== */

#include <SoftwareSerial.h>
#include <DHT.h>

/* ---------------- 1. 引脚 ---------------- */
#define PIN_DHT    7      // DHT11 数据
#define PIN_RELAY  6      // 继电器 IN（低电平吸合；若为高电平触发，互换 LOW/HIGH）
#define PIN_BUZZ   4      // 有源蜂鸣器 IN（高电平响）
#define PIN_LIGHT  A0     // 光敏模块 AO
#define PIN_LED    13     // 板载 LED，状态指示
#define ESP_RX     2      // UNO 收 ← ESP 的 TXD
#define ESP_TX     3      // UNO 发 → ESP 的 RXD

/* ---------------- 2. 必须修改：网络与平台 ---------------- */
const char* WIFI_SSID = "你的WiFi名称";          // 仅 2.4GHz，不支持 5G
const char* WIFI_PASS = "你的WiFi密码";
const char* TS_KEY    = "你的ThingSpeak写APIKey";  // Write API Key，不是 Read

/* ---------------- 3. 周期与阈值 ---------------- */
#define ESP_BAUD 9600                  // 需先用 AT+UART_DEF=9600,8,1,0,0 改速
const unsigned long READ_MS    = 2000;   // 采样周期（DHT11 ≥1s，留余量）
const unsigned long UPLOAD_MS  = 20000;  // 上传周期（ThingSpeak 下限 15s）
const unsigned long WIFI_RETRY = 15000;  // 断网重试间隔
const float FAN_ON  = 30.0;              // ≥30℃ 开风扇（继电器吸合）
const float FAN_OFF = 28.0;              // ≤28℃ 关风扇（2℃ 回差防抖）
const float ALARM_T = 35.0;              // ≥35℃ 蜂鸣器长鸣

SoftwareSerial esp(ESP_RX, ESP_TX);
DHT dht(PIN_DHT, DHT11);

float temp = NAN, humi = NAN;            // 最近一次有效读数
int   lightPct = 0;                      // 亮度 0~100（近似）
bool  fanOn = false, manual = false, muted = false, online = false;
unsigned long tRead = 0, tUp = 0, tRetry = 0;

/* ---------------- 4. ESP-01 AT 指令底层 ---------------- */

// 在 timeout 毫秒内等待应答出现 expect；出现 ERROR/FAIL 立即失败
bool atWait(const char* expect, unsigned int timeout = 2000) {
  String buf;
  unsigned long t0 = millis();
  while (millis() - t0 < timeout) {
    while (esp.available()) {
      buf += (char)esp.read();
      if (buf.indexOf(expect) >= 0) return true;              // 命中期望关键字
      if (buf.indexOf("ERROR") >= 0 || buf.indexOf("FAIL") >= 0) {
        Serial.print(F("[ESP] ")); Serial.println(buf);       // 打印原始应答便于排障
        return false;
      }
      if (buf.length() > 300) buf.remove(0, 150);             // 防长响应吃满 2KB SRAM
    }
  }
  Serial.print(F("[ESP] 超时: ")); Serial.println(expect);
  return false;
}

// 清残留 → 发一条 AT 指令 → 等应答
bool atCmd(const String& cmd, const char* expect, unsigned int timeout = 2000) {
  while (esp.available()) esp.read();   // 丢掉上一轮残留，避免误匹配
  esp.println(cmd);
  return atWait(expect, timeout);
}

// 联网：心跳 → 关回显 → STA 模式 → 单连接 → 连路由器
bool wifiJoin() {
  if (!atCmd("AT", "OK", 1500)) return false;   // 模块活着吗
  atCmd("ATE0", "OK");                          // 关回显，应答更干净
  atCmd("AT+CWMODE=1", "OK");                   // 1 = STA 客户端
  atCmd("AT+CIPMUX=0", "OK");                   // 0 = 单连接
  String c = String("AT+CWJAP=\"") + WIFI_SSID + "\",\"" + WIFI_PASS + "\"";
  return atCmd(c, "OK", 20000);                 // 联网最长等 20s
}

// 上传一帧数据到 ThingSpeak（4 个字段）
bool upload() {
  String req = String("GET /update?api_key=") + TS_KEY;
  req += "&field1=" + String(temp, 1);            // 温度，1 位小数
  req += "&field2=" + String(humi, 1);            // 湿度
  req += "&field3=" + String(lightPct);           // 光照
  req += "&field4=" + String(fanOn ? 1 : 0);      // 风扇状态
  req += " HTTP/1.1\r\nHost: api.thingspeak.com\r\nConnection: close\r\n\r\n";

  if (!atCmd("AT+CIPSTART=\"TCP\",\"api.thingspeak.com\",80", "OK", 8000))
    return false;                                  // 建 TCP 连接
  if (!atCmd("AT+CIPSEND=" + String(req.length()), ">", 3000))
    return false;                                  // 声明字节数，等 '>' 提示
  esp.print(req);                                  // 发 HTTP 请求
  if (!atWait("SEND OK", 8000)) return false;      // 发送完成
  atCmd("AT+CIPCLOSE", "OK", 3000);                // 收尾（服务器可能已断开，忽略返回值）
  return true;
}

/* ---------------- 5. 采集与本地控制 ---------------- */

// 读 DHT11 + 光敏；DHT11 读失败时保留上次有效值
void readSensors() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (!isnan(h) && !isnan(t)) { humi = h; temp = t; }

  int raw = analogRead(PIN_LIGHT);
  lightPct = map(raw, 0, 1023, 0, 100);   // 若你的模块方向相反，改为 100 - map(...)

  Serial.print(F("T="));   Serial.print(temp, 1);  Serial.print(F("C  "));
  Serial.print(F("H="));   Serial.print(humi, 0);  Serial.print(F("%  "));
  Serial.print(F("L="));   Serial.print(lightPct); Serial.print(F("%  "));
  Serial.print(F("风扇=")); Serial.println(fanOn ? F("ON") : F("OFF"));
}

// 回差控制：≥FAN_ON 吸合，≤FAN_OFF 释放，中间保持
void fanTask() {
  if (manual || isnan(temp)) return;               // 手动模式不干预
  if (!fanOn && temp >= FAN_ON)  fanOn = true;
  if ( fanOn && temp <= FAN_OFF) fanOn = false;
  digitalWrite(PIN_RELAY, fanOn ? LOW : HIGH);     // 低电平吸合
}

// 超过报警温度且未静音时蜂鸣
void buzzTask() {
  digitalWrite(PIN_BUZZ, (!muted && temp > ALARM_T) ? HIGH : LOW);
}

// 状态灯：在线常亮 / 离线快闪 / 报警慢闪
void ledTask() {
  static unsigned long t = 0;
  static bool phase = false;
  if (online && temp <= ALARM_T) { digitalWrite(PIN_LED, HIGH); return; }
  unsigned long gap = online ? 800 : 150;
  if (millis() - t >= gap) { t = millis(); phase = !phase; digitalWrite(PIN_LED, phase); }
}

// 串口指令：1 开 / 0 关 / a 自动 / m 静音
void serialTask() {
  if (!Serial.available()) return;
  switch (Serial.read()) {
    case '1': manual = true; fanOn = true;  digitalWrite(PIN_RELAY, LOW);
              Serial.println(F("[手动] 继电器 ON"));  break;
    case '0': manual = true; fanOn = false; digitalWrite(PIN_RELAY, HIGH);
              Serial.println(F("[手动] 继电器 OFF")); break;
    case 'a': case 'A': manual = false;
              Serial.println(F("[自动] 回差控制已恢复")); break;
    case 'm': case 'M': muted = !muted;
              Serial.println(muted ? F("[静音] 开") : F("[静音] 关")); break;
  }
}

/* ---------------- 6. 初始化与主循环 ---------------- */

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_RELAY, OUTPUT); digitalWrite(PIN_RELAY, HIGH);  // 上电默认断开
  pinMode(PIN_BUZZ, OUTPUT);  digitalWrite(PIN_BUZZ, LOW);
  dht.begin();
  esp.begin(ESP_BAUD);

  tRetry = millis() - WIFI_RETRY;   // 无符号回绕，使第一轮立即尝试联网
  Serial.println(F("== 创乐博 UNO R3 IOT SUPER · 物联网最小系统 =="));
  Serial.println(F("指令: 1开 0关 a自动 m静音"));
}

void loop() {
  ledTask();
  serialTask();
  buzzTask();

  if (millis() - tRead >= READ_MS) {   // 定时采样 + 自动控制
    tRead = millis();
    readSensors();
    fanTask();
  }

  if (!online) {                        // 断网：按间隔重连
    if (millis() - tRetry >= WIFI_RETRY) {
      tRetry = millis();
      Serial.println(F("[WiFi] 连接中…"));
      online = wifiJoin();
      Serial.println(online ? F("[WiFi] 成功") : F("[WiFi] 失败，稍后重试"));
    }
  } else if (millis() - tUp >= UPLOAD_MS) {   // 在线：定时上云
    tUp = millis();
    if (isnan(temp)) {
      Serial.println(F("[上云] 温湿度无效，本轮跳过"));
    } else if (upload()) {
      Serial.print(F("[上云] OK  T=")); Serial.println(temp, 1);
    } else {
      Serial.println(F("[上云] 失败，转入重连"));
      online = false;                 // 下次循环重新走联网流程
    }
  }

  delay(5);                           // 让出时间给软串口收数据
}
