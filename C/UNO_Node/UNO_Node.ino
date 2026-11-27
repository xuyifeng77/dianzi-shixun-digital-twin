/* =====================================================================
 * 电子实训 · 单节点物联网终端 —— Arduino UNO 固件
 * ---------------------------------------------------------------------
 * 版本：v1.2（2026-11-22，对应 06 审查报告 P0-4 / P1-3 / P1-4 / P1-5）
 * 上一版：v1.1（UNO_Node_v1.1.bak，勿删，答辩要讲"改了什么"）
 *
 * v1.1 → v1.2 的改动（共 8 处，逐条可在报告里对账）
 *   ① parseCmd()：加长度校验 + 开锁时长 500~10000 ms 范围校验，
 *      坏帧一律 denyBeep()，不再被 min() 钳成"合法开锁"（P0-4，安全缺陷）
 *   ② doorTask()：补 40 ms 稳定时间滤波，一次关门只发 1 条 @D（P1-3）
 *   ③ setup()：进入即 MCUSR 快照 + 清零 + wdt_disable()，防看门狗残留二次复位（P1-4）
 *   ④ 新增链路看护 lastRxAt，LCD 显示 LINK OK / LINK LOST，
 *      且**链路丢失不改变继电器状态**——本地判定必须独立于链路（P1-5）
 *   ⑤ denyTask()：相位改用 millis()-denyStart，两声短鸣不再只响一声
 *   ⑥ @E 末尾追加 rst 字段（MCUSR 原始值），坐实"是否死机重启过"（P1-4 配套）
 *   ⑦ lcdRefresh()：改用 snprintf + 定宽 16 字符，修掉第二行溢出换行
 *   ⑧ handleSerial()：超长帧改为"丢弃到本帧结束"，避免残片被当成新帧
 *   ⑨ IRremote 裁到单一协议（NEC）：Flash 28080→23254 B、SRAM 1451→1251 B，
 *      把静态占用从 70% 压到 61%，给栈和后续功能留余量（附录 A.6 实测）
 *
 * ---------------------------------------------------------------------
 * 定位：UNO 提供"物理事实"（环境感知 / 门禁执行 / 本地安全联锁），
 *       Duo 提供"语义"（视觉计数）并做云端中转。
 * 链路：UNO D0/D1 ──USB──> Duo USB-A，115200 8N1
 *       正品 UNO（ATmega16U2）= /dev/ttyACM0；CH340 克隆板 = /dev/ttyUSB0。
 *       设备名不要写死，Duo 侧用 glob 自动探测（见 duo_bridge.py v1.2）。
 * 协议：ASCII 行，'@' 起始，逗号分字段，'\n' 结尾（契约 1 v1.1）
 *   UNO→Duo  @E,t,h,smoke,flame,light,sound,rst   环境帧，2 s
 *            @D,0|1                              门磁变化（0=关 1=开）
 *            @C,<累计人次>                        光电计数
 *            @R,<UID十六进制>                     刷卡（等 Duo 鉴权）
 *            @A,<0|1|2>,<来源>                    报警等级变化
 *   Duo→UNO  @L,<ms>   开锁 ms（500~10000；越界一律拒绝）
 *            @Z         静音切换
 *            @Q         立即回一帧 @E
 *            @M,<0|1>   演示模式（1=报警不断电）
 * ---------------------------------------------------------------------
 * 铁律：Serial 只跑协议。所有调试信息走 LCD/OLED，
 *       在 Serial 打日志会污染帧、导致 Duo 侧解析失败。
 * 引脚与 接线表.md v1.0（契约 2）逐行一致，勿随意改动。
 * ===================================================================== */

#include <Wire.h>
#include <SPI.h>
#include <LiquidCrystal_I2C.h>   /* Frank de Brabander 1.1.4，用 init() */
#include <U8x8lib.h>             /* 只用文本模式：零显存，省 1KB RAM */
#include <MFRC522.h>
#include <Servo.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

/* —— IRremote 裁剪（附录 A.6，D1 实测：Flash 28080→23254 B，SRAM 1451→1251 B）
   默认会把所有解码协议编进来，Flash 吃 4.8 KB、SRAM 吃 200 B；SRAM 70% 已压
   在警戒线上，后面的看护/诊断留不出余量，所以裁到单一协议。
   这四个宏必须写在本行 #include 之前，写在后面不生效。
   换遥控器按键无反应 → 把 DECODE_NEC 换成该遥控的协议宏（DECODE_SONY /
   DECODE_RC5 / DECODE_SAMSUNG…），或整段注释掉（退回 87%，那就得先删功能）。 */
#define DECODE_NEC
#define EXCLUDE_EXOTIC_PROTOCOLS
#define NO_LED_FEEDBACK_CODE
#define RAW_BUFFER_LENGTH 60
#include <IRremote.hpp>          /* 必须 IRremote >= 4.0 */
#include <avr/wdt.h>             /* 看门狗，8s 无喂狗自动重启 */

#ifndef UNUSED_PIN                  /* 老版 MFRC522 无此宏时兜底 */
#define UNUSED_PIN 0xFF
#endif

/* ---------------- 1. 引脚（= 接线表 v1.0） ---------------- */
#define PIN_DHT    2      /* DHT11 数据 */
#define PIN_DS18   3      /* DS18B20 DQ（4.7kΩ 上拉） */
#define PIN_BUZZ   4      /* 有源蜂鸣器 */
#define PIN_LED    5      /* 7色LED，PWM（Timer0，与 Servo 不冲突） */
#define PIN_RELAY  6      /* 继电器，低电平吸合；HIGH=释放=负载断电 */
#define PIN_SERVO  7      /* 舵机（Servo 库独占 Timer1） */
#define PIN_IR     8      /* 红外接收 VS1838B */
#define PIN_FAN    9      /* 风扇，仅 digitalWrite（Timer1 被舵机占用） */
#define PIN_SS    10      /* RC522 片选（SPI 固定 11/12/13） */
#define PIN_PHOTO A0      /* U 型光电 DO */
#define PIN_DOOR  A1      /* 干簧管 DO */
#define PIN_TOUCH A2      /* 触摸开关 */
#define PIN_AUX   A3      /* 空闲：若 LED 改 RGB 三通道模块，占这里 */

/* ---------------- 2. 地址、阈值与时间常数 ---------------- */
#define PCF_ADDR  0x48
#define LCD_ADDR  0x27
#define SMOKE_L1  120     /* 注意级（0~255，需按现场标定，见 标定记录.md） */
#define SMOKE_L2  200     /* 危险级 */
#define FLAME_L1  150
#define FLAME_L2  250
#define TEMP_L2   45.0
#define WARMUP_MS 30000UL /* MQ-2 预热期内读数作废 */
#define PHOTO_DEBOUNCE_MS 40
#define DOOR_DEBOUNCE_MS  40
#define LINK_TIMEOUT_MS   15000UL   /* 15 s 无任何合法帧 → LINK LOST */
#define LOCK_MIN_MS  500L
#define LOCK_MAX_MS  10000L
#define DENY_TOTAL_MS 400UL         /* 拒绝音两声，共 400 ms */
#define DOOR_CLOSED_LEVEL LOW  /* 门关=该电平：裸干簧管对地=LOW；模块型实测后改 HIGH */

/* ---------------- 3. 外设对象 ---------------- */
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);
U8X8_SSD1306_128X64_NONAME_HW_I2C oled(U8X8_PIN_NONE);
MFRC522 rfid(PIN_SS, UNUSED_PIN);      /* RST 接 3.3V，软件不复位 */
Servo lockServo;
DHT dht(PIN_DHT, DHT11);
OneWire oneWire(PIN_DS18);
DallasTemperature ds18(&oneWire);

/* ---------------- 4. 运行状态 ---------------- */
struct Env {                 /* 一次采样快照，避免各函数各读一遍外设 */
  uint8_t  smoke, flame, light, sound;
  float    temp, humi;
  uint16_t passes;           /* U 型光电累计人次 */
} env = {0, 0, 0, 0, NAN, NAN, 0};

uint8_t  alarmLevel = 0;                 /* 0 正常 / 1 注意 / 2 危险 */
bool     muted = false, demoMode = false, lockOpen = false;
uint32_t lockUntil = 0, bootAt = 0;
uint32_t tSample = 0, tJudge = 0, tReport = 0, tLcd = 0, tBuzz = 0;
bool     photoPrev = false;
uint32_t tPhoto = 0, denyUntil = 0, denyStart = 0;
uint32_t lastRxAt = 0;                   /* 最近一次收到合法帧的时刻（LINK 看护） */
uint8_t  resetCause = 0;                 /* 上电时 MCUSR 快照，随 @E 上报 */
char     rxBuf[48];  uint8_t rxLen = 0;
bool     rxOverflow = false;             /* 超长帧：丢弃到本帧结束 */
char     logBuf[4][21];                  /* OLED 四行滚动日志 */

/* ---------------- 5. PCF8591：四路模拟量 ---------------- */
uint8_t pcfRead(uint8_t ch) {
  Wire.beginTransmission(PCF_ADDR);
  Wire.write(0x40 | (ch & 0x03));        /* bit6=模拟输出使能，低2位=通道 */
  Wire.endTransmission();
  Wire.requestFrom(PCF_ADDR, (uint8_t)1);
  if (Wire.available()) Wire.read();     /* 首个字节是上次转换缓存，丢弃 */
  Wire.requestFrom(PCF_ADDR, (uint8_t)1);/* 第二次读才是本通道新值 */
  return Wire.available() ? Wire.read() : 0;
}

/* ---------------- 6. 显示（全 ASCII；中文需换 U8g2 中文子集字库） ---------- */
void oledLog(const char* s) {
  for (uint8_t i = 0; i < 3; i++) strcpy(logBuf[i], logBuf[i + 1]);
  strncpy(logBuf[3], s, 20); logBuf[3][20] = 0;
  oled.clearDisplay();
  for (uint8_t i = 0; i < 4; i++) oled.drawString(0, i * 2, logBuf[i]);
}

/* 定宽 16 字符：超长自动截断，短了补空格，避免残留字符与第二行换行 */
void lcdLine(uint8_t row, const char* text) {
  char buf[17];
  snprintf(buf, sizeof(buf), "%-16s", text);
  lcd.setCursor(0, row);
  lcd.print(buf);
}

void lcdRefresh() {
  bool linkOk = (millis() - lastRxAt) < LINK_TIMEOUT_MS;   /* 只影响显示，不动继电器 */
  char line[17];
  snprintf(line, sizeof(line), "T%.1fC H%d%% %s",
           env.temp, (int)env.humi, linkOk ? "OK" : "LOST");
  lcdLine(0, line);
  snprintf(line, sizeof(line), "S%u F%u L%u N%u",
           (unsigned)env.smoke, (unsigned)env.flame,
           (unsigned)alarmLevel, (unsigned)env.passes);
  lcdLine(1, line);
}

/* ---------------- 7. 采样 ---------------- */
void sampleSensors() {
  env.smoke = pcfRead(0);                /* AIN0 MQ-2 */
  env.flame = pcfRead(1);                /* AIN1 火焰 */
  env.light = pcfRead(2);                /* AIN2 光敏 */
  env.sound = pcfRead(3);                /* AIN3 声音 */

  float t = ds18.getTempCByIndex(0);     /* 9 位分辨率，阻塞约 94ms，可接受 */
  if (t > -50 && t < 125) env.temp = t;

  /* ⑥ 1 s 采一次不会 NaN：Adafruit DHT 库在间隔 <2 s 时返回上次缓存值，不是 NaN。
     但 DHT11 本身每 2 s 才更新一次湿度，所以 1 s 采样看到的是重复值，不是新数据。 */
  float h = dht.readHumidity();
  if (!isnan(h)) env.humi = h;

  if (millis() - bootAt < WARMUP_MS) env.smoke = 0;   /* 预热期不可信 */
}

/* ---------------- 8. 判定与联锁输出 ---------------- */
uint8_t judge() {
  if (env.smoke >= SMOKE_L2 || env.flame >= FLAME_L2 || env.temp >= TEMP_L2) return 2;
  if (env.smoke >= SMOKE_L1 || env.flame >= FLAME_L1) return 1;
  return 0;
}

/* 失效安全：继电器常吸合给负载持续供电；危险时释放→负载断电。
   因此 UNO 自身供电绝对不能串在触点回路里，否则报警即自锁。
   复位瞬间引脚为高阻，模块 IN 若悬空可能误导通——硬件侧在 IN 与 5V 间加
   10kΩ 上拉，保证复位期间落在"释放"，软件侧的 LOW 只是恢复常态供电。 */
void applyOutputs() {
  uint8_t lv = alarmLevel;
  if (demoMode && lv > 0) lv = 1;                        /* 演示模式不断电 */

  digitalWrite(PIN_RELAY, lv >= 2 ? HIGH : LOW);         /* HIGH=释放=断开 */
  digitalWrite(PIN_FAN,   lv >= 1 ? HIGH : LOW);         /* 注意级即通风排烟 */
  analogWrite(PIN_LED, lv == 0 ? 30 : (lv == 1 ? 120 : 240)); /* 绿/黄/红，按实物微调 */
}

void judgeAndAct() {
  uint8_t lv = judge();
  if (lv != alarmLevel) {                                /* 只在变化时上报，省串口 */
    alarmLevel = lv;
    tBuzz = millis();                                    /* 报警节奏重新起拍 */
    const char* src = "NONE";
    if (env.smoke >= (lv >= 2 ? SMOKE_L2 : SMOKE_L1))      src = "SMOKE";
    else if (env.flame >= (lv >= 2 ? FLAME_L2 : FLAME_L1)) src = "FLAME";
    else if (env.temp >= TEMP_L2)                          src = "TEMP";
    Serial.print(F("@A,")); Serial.print(lv);
    Serial.print(',');      Serial.println(src);

    char line[16]; snprintf(line, sizeof(line), "ALARM L%u", (unsigned)lv); oledLog(line);
  }
  applyOutputs();
}

/* ---------------- 9. 非阻塞蜂鸣器：节奏编码报警 ---------------- */
void buzzTask() {
  if (muted || alarmLevel == 0) { digitalWrite(PIN_BUZZ, LOW); return; }
  uint16_t period = (alarmLevel >= 2) ? 1500 : 3000;   /* 危险=长鸣，注意=短促 */
  uint16_t onMs   = (alarmLevel >= 2) ? 1000 : 150;
  digitalWrite(PIN_BUZZ, ((millis() - tBuzz) % period) < onMs ? HIGH : LOW);
}

/* ---------------- 10. 上报 ---------------- */
void sendEnv() {
  Serial.print(F("@E,"));
  Serial.print(env.temp, 1);  Serial.print(',');
  Serial.print(env.humi, 1);  Serial.print(',');
  Serial.print(env.smoke);    Serial.print(',');
  Serial.print(env.flame);    Serial.print(',');
  Serial.print(env.light);    Serial.print(',');
  Serial.print(env.sound);    Serial.print(',');
  Serial.println(resetCause);   /* v1.2 追加：0=正常上电，其余位见 MCUSR */
}

/* ---------------- 11. 门禁执行 ---------------- */
void openLock(uint16_t ms) {
  /* 范围校验已在 parseCmd() 完成。这里不再"钳位救场"：
     坏帧在上游就被拒绝，绝不允许把异常值兜底成一次合法开锁。 */
  lockServo.write(90);
  lockOpen = true;
  lockUntil = millis() + ms;
  oledLog("DOOR OPEN");
}

void denyBeep() {                          /* 拒绝：两声短鸣，非阻塞 */
  denyStart = millis();
  denyUntil = denyStart + DENY_TOTAL_MS;
  oledLog("ACCESS DENY");
}

void denyTask() {                          /* (millis()-denyStart) 相位，两声都不会吞 */
  if (denyUntil == 0) return;
  if (muted) { denyUntil = 0; digitalWrite(PIN_BUZZ, LOW); return; }  /* 静音时拒绝音同样静默 */
  uint32_t r = millis() - denyStart;
  if (r >= DENY_TOTAL_MS) { denyUntil = 0; digitalWrite(PIN_BUZZ, LOW); return; }
  digitalWrite(PIN_BUZZ, (r < 80 || (r >= 200 && r < 280)) ? HIGH : LOW);
}

void lockTask() {                          /* 到时自动回锁 */
  if (lockOpen && (int32_t)(millis() - lockUntil) >= 0) {
    lockServo.write(0);
    lockOpen = false;
    oledLog("DOOR LOCK");
  }
}

/* ---------------- 12. 串口协议解析（Duo → UNO） ---------------- */

/* 只有通过校验的帧才会调用到这里；返回值不用，统一从 rxBuf 读 */
void parseCmd() {
  if (rxBuf[0] != '@') return;
  char* p = rxBuf + 1;
  const size_t n = strlen(p);
  if (n < 1) return;                       /* 只有 '@' 一个字符：无命令，忽略 */

  switch (p[0]) {
    case 'L': {                            /* @L,3000 */
      if (n < 4) { denyBeep(); return; }   /* "@L" / "@L," 短帧：拒绝，不开锁 */
      long ms = atol(p + 2);
      if (ms >= LOCK_MIN_MS && ms <= LOCK_MAX_MS) openLock((uint16_t)ms);
      else denyBeep();                     /* 负数 / 0 / 越界 / 垃圾 → 拒绝 */
      break;
    }
    case 'Z': muted = !muted; oledLog(muted ? "MUTE ON" : "MUTE OFF"); break;
    case 'Q': sendEnv(); break;            /* 心跳回执 */
    case 'M':
      if (n >= 3) { demoMode = (p[2] == '1'); oledLog(demoMode ? "DEMO" : "NORMAL"); }
      break;
    default: break;                        /* 未知命令忽略，不回应、不动作 */
  }
}

void handleSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      rxBuf[rxLen] = 0;
      if (rxLen) {
        /* 任何以 '@' 起始的完整帧都算链路存活：
           断线时一个字节都收不到，比"解析成功"更能反映物理链路状态。 */
        if (rxBuf[0] == '@') lastRxAt = millis();
        parseCmd();
      }
      rxLen = 0; rxOverflow = false;
    } else if (rxOverflow) {
      /* 丢弃到本帧结束，防止超长帧的残片被当成新帧 */
    } else if (rxLen < sizeof(rxBuf) - 1) {
      rxBuf[rxLen++] = c;
    } else {
      rxLen = 0; rxOverflow = true;        /* 超长帧整帧作废 */
    }
  }
}

/* ---------------- 13. 现场输入 ---------------- */
void photoTask() {                          /* U 型光电：遮挡沿计数（真值来源），40ms 去抖 */
  bool now = (digitalRead(PIN_PHOTO) == LOW);
  if (now == photoPrev) return;             /* 无变化 */
  if (millis() - tPhoto < PHOTO_DEBOUNCE_MS) return;  /* 抖动窗口内忽略 */
  tPhoto = millis(); photoPrev = now;
  if (!now) return;                         /* 只数遮挡沿 */
  env.passes++;
  Serial.print(F("@C,")); Serial.println(env.passes);
  char line[12]; snprintf(line, sizeof(line), "PASS %u", (unsigned)env.passes); oledLog(line);
}

/* 干簧管：闭合=门关，极性见 DOOR_CLOSED_LEVEL。
   簧片在门扇停下的瞬间会抖 3~10 ms，必须等电平稳定 40 ms 才认；
   首次稳定读数为"未知→实际"，保证上电后一定发出一次 @D。 */
void doorTask() {
  static int      doorRaw    = -1;
  static uint32_t doorEdgeAt = 0;
  static int      doorClosed = -1;          /* -1 = 未知 */

  uint32_t now = millis();
  int raw = digitalRead(PIN_DOOR);
  if (raw != doorRaw) { doorRaw = raw; doorEdgeAt = now; return; }
  if (now - doorEdgeAt < DOOR_DEBOUNCE_MS) return;

  int closed = (raw == DOOR_CLOSED_LEVEL) ? 1 : 0;
  if (closed == doorClosed) return;
  doorClosed = closed;
  Serial.print(F("@D,")); Serial.println(closed ? 0 : 1);
  oledLog(closed ? "DOOR CLOSED" : "DOOR OPEN");
}

void handleTouch() {                        /* 触摸：消音；边沿触发，200ms 去抖 */
  static uint32_t t = 0; static bool prev = false;
  bool now = (digitalRead(PIN_TOUCH) == HIGH);
  if (now && !prev && millis() - t > 200) {
    t = millis();
    muted = !muted;
    oledLog(muted ? "MUTE ON" : "MUTE OFF");
  }
  prev = now;
}

/* ---------------- 14. 刷卡 / 红外 ---------------- */
void handleRFID() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  char uid[12]; uint8_t n = 0;
  for (uint8_t i = 0; i < rfid.uid.size && n < 10; i++)
    n += snprintf(uid + n, sizeof(uid) - n, "%02X", rfid.uid.uidByte[i]);
  Serial.print(F("@R,")); Serial.println(uid);   /* 鉴权在 Duo/PC 侧 */
  oledLog("CARD READ");
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

/* 遥控按键码需现场自测：按一下看 OLED 打印的 IR xx，填到下面三行 */
#define IR_KEY_MUTE 0x45
#define IR_KEY_LOCK 0x46
#define IR_KEY_DEMO 0x47

void handleIR() {
  if (!IrReceiver.decode()) return;
  uint8_t cmd = IrReceiver.decodedIRData.command;
  char line[12]; snprintf(line, sizeof(line), "IR %02X", cmd); oledLog(line);
  if (cmd == IR_KEY_MUTE) muted = !muted;
  if (cmd == IR_KEY_LOCK) openLock(3000);
  if (cmd == IR_KEY_DEMO) demoMode = !demoMode;
  IrReceiver.resume();
}

/* ---------------- 15. 初始化 ---------------- */
void setup() {
  /* 先存复位原因、清标志、关掉可能残留的看门狗 —— 必须早于一切外设初始化。
     若上一轮是看门狗复位，WDRF 置位且 WDT 仍在跑（可能已被 bootloader 拉短到
     15 ms），到 wdt_enable() 之间的窗口足以再次复位，表现为"间歇性起不来"。 */
  resetCause = MCUSR;
  MCUSR = 0;
  wdt_disable();

  Serial.begin(115200);                    /* 协议口，同时也是下载口 */
  Wire.begin();

  pinMode(PIN_BUZZ, OUTPUT);  digitalWrite(PIN_BUZZ, LOW);
  /* 继电器：模块为低电平吸合，上电即吸合给负载供电。
     高阻期由 IN 线上的 10kΩ 上拉保证"释放"，见 接线表.md §3。 */
  pinMode(PIN_RELAY, OUTPUT); digitalWrite(PIN_RELAY, LOW);
  pinMode(PIN_FAN, OUTPUT);   digitalWrite(PIN_FAN, LOW);
  pinMode(PIN_LED, OUTPUT);   analogWrite(PIN_LED, 30);
  pinMode(PIN_PHOTO, INPUT);
  pinMode(PIN_DOOR, INPUT_PULLUP);   /* 裸干簧管用；模块型推挽输出可改 INPUT */
  pinMode(PIN_TOUCH, INPUT);

  lcd.init();  lcd.backlight();
  lcdLine(0, "UNO NODE BOOT");
  oled.begin(); oled.setFont(u8x8_font_chroma48medium8_r);
  for (uint8_t i = 0; i < 4; i++) logBuf[i][0] = 0;
  oledLog("BOOT");

  dht.begin();
  ds18.begin();
  ds18.setResolution(9);               /* 9 位 ≈94ms 转换，避免采样阻塞 */
  rfid.PCD_Init();
  lockServo.attach(PIN_SERVO); lockServo.write(0);   /* 0°=锁闭 */
  IrReceiver.begin(PIN_IR, DISABLE_LED_FEEDBACK); /* 反馈 LED 与 D13(SCK) 共用，勿启用 */

  bootAt = millis();
  lastRxAt = bootAt;                   /* 启动给 15 s 宽限，之后靠 @Q 心跳续期 */
  oledLog("MQ-2 WARMUP 30s");
  wdt_enable(WDTO_8S);                   /* 之后 loop 每秒喂狗 */
}

/* ---------------- 16. 主循环（全程非阻塞） ---------------- */
void loop() {
  wdt_reset();
  handleSerial();

  uint32_t now = millis();
  if (now - tSample >= 1000)  { tSample = now; sampleSensors(); }
  if (now - tJudge  >= 1000)  { tJudge  = now; judgeAndAct(); }
  if (now - tReport >= 2000)  { tReport = now; sendEnv(); }
  if (now - tLcd    >= 500)   { tLcd    = now; lcdRefresh(); }

  handleIR();
  handleRFID();
  handleTouch();
  photoTask();
  doorTask();
  lockTask();
  buzzTask();
  denyTask();        /* 在 buzzTask 之后调用，拒绝音优先级更高 */
}
