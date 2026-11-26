/* =====================================================================
 * UNO_Node v1.2 主机侧（PC）行为测试
 * ---------------------------------------------------------------------
 * 目的：插板之前，先把"坏帧不得开锁"这条安全铁律用程序验证一遍。
 *       对应 10-C岗 §五 ① 要求的 4 条自测，另加心跳、未知命令、
 *       门磁去抖、链路看护、复位原因。
 *
 * 用法：不要直接 g++（中文路径会让 #include 失败），运行同目录的
 *       run_test.ps1，它会把 .ino 和本文件拷到 ASCII 临时目录再编译。
 *
 * 说明：stubs\ 里是 Arduino/库的空壳头文件，只让 PC 编译器读懂 .ino；
 *       真实烧录仍用 Arduino IDE，本文件不在 sketch 目录内。
 * ===================================================================== */
#include "Arduino.h"
#include "Wire.h"
#include "SPI.h"
#include "Servo.h"
#include "IRremote.hpp"
#include "LiquidCrystal_I2C.h"
#include "U8x8lib.h"
#include "MFRC522.h"
#include "DHT.h"
#include "OneWire.h"
#include "DallasTemperature.h"

#include <cstdio>
#include <cstring>
#include <string>

/* ---------------- 假外设：把硬件状态搬到进程内存 ---------------- */
uint8_t  MCUSR = 0;
uint32_t g_ms  = 1000;
static uint8_t g_lcdRow = 0;

uint32_t millis() { return g_ms; }
void delay(uint32_t) {}

static uint8_t g_pinOut[32];
static int     g_doorLevel = HIGH;     /* A1 干簧管电平 */

void pinMode(uint8_t, uint8_t) {}
void digitalWrite(uint8_t p, uint8_t v) { if (p < 32) g_pinOut[p] = v; }
int  digitalRead(uint8_t p) {
  if (p == 15) return g_doorLevel;                 /* A1 */
  return g_pinOut[p] ? HIGH : LOW;
}
void analogWrite(uint8_t p, int v) { if (p < 32) g_pinOut[p] = (uint8_t)v; }

/* ---------------- 假串口：可喂入、可抓输出 ---------------- */
static std::string g_in;
static size_t      g_inPos = 0;
std::string        g_out;              /* 所有 Serial 输出 */
std::string        g_lcd[2];           /* LCD 两行 */

static void feed(const char* s) { g_in = s; g_inPos = 0; }

SerialStub Serial;

void SerialStub::begin(long) {}
int  SerialStub::available() { return g_inPos < g_in.size() ? 1 : 0; }
int  SerialStub::read()      { return g_inPos < g_in.size() ? (unsigned char)g_in[g_inPos++] : -1; }

void SerialStub::print(const char* s) { g_out += s; }
void SerialStub::print(char c)        { g_out += c; }
void SerialStub::print(int v)         { g_out += std::to_string(v); }
void SerialStub::print(unsigned int v){ g_out += std::to_string(v); }
void SerialStub::print(long v)        { g_out += std::to_string(v); }
void SerialStub::print(unsigned long v){ g_out += std::to_string(v); }
void SerialStub::print(float v, int d) { char b[32]; snprintf(b, sizeof(b), "%.*f", d, v); g_out += b; }
void SerialStub::println(const char* s) { g_out += s; g_out += '\n'; }
void SerialStub::println(int v)         { g_out += std::to_string(v); g_out += '\n'; }
void SerialStub::println(unsigned int v){ g_out += std::to_string(v); g_out += '\n'; }
void SerialStub::println(long v)        { g_out += std::to_string(v); g_out += '\n'; }
void SerialStub::println(unsigned long v){ g_out += std::to_string(v); g_out += '\n'; }
void SerialStub::println(float v, int d) { char b[32]; snprintf(b, sizeof(b), "%.*f", d, v); g_out += b; g_out += '\n'; }

/* ---------------- 库对象桩实现 ---------------- */
TwoWire Wire;
void TwoWire::begin() {}
void TwoWire::beginTransmission(uint8_t) {}
size_t TwoWire::write(uint8_t) { return 1; }
uint8_t TwoWire::endTransmission() { return 0; }
uint8_t TwoWire::requestFrom(uint8_t, uint8_t) { return 1; }
int TwoWire::available() { return 1; }
int TwoWire::read() { return 120; }

int g_servoAngle = -1;
void Servo::attach(int) {}
void Servo::write(int a) { g_servoAngle = a; }

LiquidCrystal_I2C::LiquidCrystal_I2C(uint8_t, uint8_t, uint8_t) {}
void LiquidCrystal_I2C::init() {}
void LiquidCrystal_I2C::backlight() {}
void LiquidCrystal_I2C::setCursor(uint8_t, uint8_t row) {
  g_lcdRow = row < 2 ? row : 0;
  g_lcd[g_lcdRow].clear();
}
void LiquidCrystal_I2C::print(const char* s) { g_lcd[g_lcdRow] += s; }
void LiquidCrystal_I2C::print(char c) { g_lcd[g_lcdRow] += c; }
void LiquidCrystal_I2C::print(int v) { g_lcd[g_lcdRow] += std::to_string(v); }
void LiquidCrystal_I2C::print(unsigned int v) { g_lcd[g_lcdRow] += std::to_string(v); }
void LiquidCrystal_I2C::print(float v, int d) {
  char b[32]; snprintf(b, sizeof(b), "%.*f", d, v); g_lcd[g_lcdRow] += b;
}

const uint8_t u8x8_font_chroma48medium8_r[1] = {0};
void U8X8::begin() {}
void U8X8::setFont(const uint8_t*) {}
void U8X8::clearDisplay() {}
void U8X8::drawString(uint8_t, uint8_t, const char*) {}
U8X8_SSD1306_128X64_NONAME_HW_I2C::U8X8_SSD1306_128X64_NONAME_HW_I2C(uint8_t) {}

MFRC522::MFRC522(uint8_t, uint8_t) { uid.size = 0; }
void MFRC522::PCD_Init() {}
bool MFRC522::PICC_IsNewCardPresent() { return false; }
bool MFRC522::PICC_ReadCardSerial() { return false; }
void MFRC522::PICC_HaltA() {}
void MFRC522::PCD_StopCrypto1() {}

DHT::DHT(uint8_t, uint8_t) {}
void DHT::begin() {}
float DHT::readHumidity() { return 50.0f; }
float DHT::readTemperature() { return 25.0f; }

OneWire::OneWire(uint8_t) {}
DallasTemperature::DallasTemperature(OneWire*) {}
void DallasTemperature::begin() {}
void DallasTemperature::setResolution(uint8_t) {}
float DallasTemperature::getTempCByIndex(uint8_t) { return 25.0f; }

IRrecv IrReceiver;
void IRrecv::begin(uint8_t, bool) {}
bool IRrecv::decode() { return false; }
void IRrecv::resume() {}

/* ---------------- 把被测固件整体编进来 ----------------
 * 本文件必须与 UNO_Node.ino 位于同一目录才能 include，
 * 由 run_test.ps1 负责把两者拷到 ASCII 临时目录。 */
#include "UNO_Node.ino"

/* ---------------- 测试框架 ---------------- */
static int g_pass = 0, g_fail = 0;

static void check(bool ok, const char* name, const char* detail = "") {
  if (ok) { ++g_pass; printf("  PASS  %s\n", name); }
  else    { ++g_fail; printf("  FAIL  %s  %s\n", name, detail); }
}

/* 清掉上一帧的可观测状态：舵机角度、拒绝音、串口输出 */
static void resetObserve() {
  g_servoAngle = -1;
  denyUntil = 0;
  lockOpen  = false;
  g_out.clear();
}

static void sendFrame(const char* f) {
  feed(f);
  handleSerial();
}

int main() {
  printf("UNO_Node v1.2 解析与联锁测试\n\n");

  printf("[P0-4] @L 四类坏帧必须拒绝、不得开锁\n");
  struct { const char* frame; const char* name; } bad[] = {
    { "@L\n",       "@L        短帧" },
    { "@L,-1\n",    "@L,-1     负数" },
    { "@L,99999\n", "@L,99999  超上限（旧版会开 10 s）" },
    { "@L,0\n",     "@L,0      零" },
  };
  for (auto& b : bad) {
    resetObserve();
    sendFrame(b.frame);
    check(g_servoAngle == -1 && denyUntil != 0, b.name);
  }

  resetObserve();
  sendFrame("@L,3000\n");
  check(g_servoAngle == 90 && lockOpen, "@L,3000   合法帧必须开锁");

  resetObserve();
  sendFrame("@L,500\n");
  check(g_servoAngle == 90, "@L,500    下边界应接受");
  resetObserve();
  sendFrame("@L,10000\n");
  check(g_servoAngle == 90, "@L,10000  上边界应接受");

  printf("\n[协议] 心跳回执与未知命令\n");
  resetObserve();
  env.temp = 25.3f; env.humi = 45.0f; env.smoke = 12;
  env.flame = 3; env.light = 88; env.sound = 7;
  sendFrame("@Q\n");
  check(g_out.rfind("@E,", 0) == 0, "@Q 立即回一帧 @E");
  check(g_out.find("25.3") != std::string::npos, "@E 含温度");
  {
    size_t commas = 0;
    for (char c : g_out) if (c == ',') ++commas;
    check(commas == 7, "@E 共 8 字段（7 个逗号），rst 已追加");
  }

  resetObserve();
  sendFrame("@X\n");
  check(g_servoAngle == -1 && denyUntil == 0 && g_out.empty(), "@X 未知命令：不动作、不回应");

  resetObserve();
  sendFrame("garbage\n");
  check(g_servoAngle == -1 && denyUntil == 0, "非 @ 起始的杂行被忽略");

  printf("\n[P1-3] 门磁去抖：一次关门只发一条 @D\n");
  {
    resetObserve();
    /* 先让初始状态稳定：门关 */
    g_doorLevel = LOW;
    for (int i = 0; i < 3; ++i) { g_ms += 20; doorTask(); }
    g_out.clear();

    /* 模拟关门抖动：5 ms 级来回 6 次，最终稳定在"关"，状态没变 */
    for (int i = 0; i < 6; ++i) {
      g_doorLevel = (i % 2) ? LOW : HIGH;
      g_ms += 5; doorTask();
    }
    g_doorLevel = LOW;
    g_ms += 50; doorTask();
    g_ms += 50; doorTask();

    size_t n = 0;
    for (size_t i = g_out.find("@D,"); i != std::string::npos; i = g_out.find("@D,", i + 1)) ++n;
    check(n == 0, "关门抖动 6 次不产生 @D（状态未变）");

    /* 开 → 关 的真实动作：稳定后应恰好各 1 条 */
    g_out.clear();
    g_doorLevel = HIGH;
    for (int i = 0; i < 4; ++i) { g_ms += 20; doorTask(); }
    g_doorLevel = LOW;
    for (int i = 0; i < 4; ++i) { g_ms += 20; doorTask(); }
    n = 0;
    for (size_t i = g_out.find("@D,"); i != std::string::npos; i = g_out.find("@D,", i + 1)) ++n;
    check(n == 2, "开→关 各发一条（共 2 条，抖动被滤掉）");
  }

  printf("\n[P1-5] 链路看护：15 s 无帧 → LOST，且继电器不动\n");
  {
    lastRxAt = g_ms;
    g_ms += 16000;
    applyOutputs();                       /* 本地判定照常执行 */
    uint8_t relayBefore = g_pinOut[6];
    lcdRefresh();
    check(g_lcd[0].find("LOST") != std::string::npos, "LCD 第一行出现 LOST");
    check(g_pinOut[6] == relayBefore, "链路丢失不改变继电器状态");

    sendFrame("@Q\n");
    lcdRefresh();
    check(g_lcd[0].find("OK") != std::string::npos, "收到帧后恢复 OK");
  }

  printf("\n[P1-4] 复位原因随 @E 上报\n");
  {
    resetCause = 0x08;                    /* WDRF：看门狗复位 */
    resetObserve();
    sendFrame("@Q\n");
    check(g_out.size() >= 2 && g_out[g_out.size() - 2] == '8', "@E 末字段 rst=8");
  }

  printf("\n结果：%d 通过 / %d 失败\n", g_pass, g_fail);
  return g_fail == 0 ? 0 : 1;
}
