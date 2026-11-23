/* ============================================================
 * buzzer_check.ino  ·  蜂鸣器模块类型判定 + 节奏演示
 * ------------------------------------------------------------
 * 用途：现场 30 秒判明"有源 / 无源 / 低电平触发"，避免整机接好了才发现不响。
 * 接线：模块 VCC→5V，GND→GND，I/O→D4（与正式固件同一个脚，判完不用挪线）
 * 串口：115200
 *
 * 判定原理
 *   有源模块内部自带振荡电路 —— 给恒定高电平就响；
 *   无源模块只是电磁/压电片   —— 必须给 2~5 kHz 方波（tone）才响。
 *
 * 流程
 *   上电 → ① 高电平 1.5 s → ② 低电平 1.5 s → ③ 2700 Hz 方波 1.5 s
 *   每一步串口都会问"响了吗"，答 y/n，最后打印结论。
 * ============================================================ */

const uint8_t PIN_BUZZ = 4;

static bool waitYesNo(const __FlashStringHelper* q) {
  Serial.println(q);
  Serial.println(F("  y = 响了    n = 没响"));
  while (true) {
    while (!Serial.available()) {}
    char c = (char)Serial.read();
    if (c == 'y' || c == 'Y') { Serial.println(F("  -> 响")); return true; }
    if (c == 'n' || c == 'N') { Serial.println(F("  -> 不响")); return false; }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);

  Serial.println();
  Serial.println(F("=== buzzer_check · 蜂鸣器类型判定 ==="));
  Serial.println(F("接线: VCC->5V  GND->GND  I/O->D4"));
  Serial.println(F("判定期间请盯着/听着蜂鸣器，每一步都要回答。"));
  Serial.println();

  /* ① 恒定高电平：有源模块应当直接响 */
  Serial.println(F("[1/4] 输出恒定 HIGH 1.5 s"));
  digitalWrite(PIN_BUZZ, HIGH);
  delay(1500);
  digitalWrite(PIN_BUZZ, LOW);
  delay(300);
  bool dcSound = waitYesNo(F("① 恒定高电平(1.5 s) 响了吗？"));

  /* ② 恒定低电平：抓"低电平触发"的模块 */
  Serial.println(F("[2/4] 输出恒定 LOW 1.5 s"));
  digitalWrite(PIN_BUZZ, LOW);
  delay(1500);
  bool lowSound = waitYesNo(F("② 恒定低电平(1.5 s) 响了吗？"));

  /* ③ 2.7 kHz 方波：无源模块应当响 */
  Serial.println(F("[3/4] 输出 2700 Hz 方波 1.5 s"));
  tone(PIN_BUZZ, 2700, 1500);
  delay(1800);
  noTone(PIN_BUZZ);
  digitalWrite(PIN_BUZZ, LOW);
  bool toneSound = waitYesNo(F("③ 2700 Hz 方波(1.5 s) 响了吗？"));

  /* ④ 结论 */
  Serial.println();
  Serial.println(F("=== 结论 ==="));
  if (dcSound && !lowSound) {
    Serial.println(F("有源 · 高电平触发 —— 本项目要求，直接可用。"));
    Serial.println(F("正式固件 UNO_Node.ino 的 buzzTask()/denyTask() 不用改。"));
  } else if (dcSound && lowSound) {
    Serial.println(F("有源 · 两个电平都响？多半是模块常响或接线短到 5V，先查线。"));
  } else if (!dcSound && toneSound) {
    Serial.println(F("无源模块 —— 不适用本项目。请换套件第 19 项【有源蜂鸣器】。"));
    Serial.println(F("临时可用 tone(PIN_BUZZ,2700)，但必须同时停用 IRremote（Timer2 冲突）。"));
  } else if (!dcSound && !toneSound && lowSound) {
    Serial.println(F("有源 · 低电平触发 —— 可用，但固件电平要取反（HIGH/LOW 全部对调）。"));
  } else {
    Serial.println(F("都没响 —— 依次查：5V 供电、GND 共地、I/O 是否真的在 D4、模块是否损坏。"));
  }
  Serial.println();

  /* 节奏演示：判完顺手听一遍三级语义（只在有源高电平触发时有意义） */
  if (dcSound && !lowSound) {
    Serial.println(F("=== 节奏演示（正式固件的三级语义）==="));
    Serial.println(F("危险 L2: 响1000ms / 停500ms ×3"));
    for (uint8_t i = 0; i < 3; i++) {
      digitalWrite(PIN_BUZZ, HIGH); delay(1000);
      digitalWrite(PIN_BUZZ, LOW);  delay(500);
    }
    Serial.println(F("注意 L1: 响150ms / 停2850ms ×2"));
    for (uint8_t i = 0; i < 2; i++) {
      digitalWrite(PIN_BUZZ, HIGH); delay(150);
      digitalWrite(PIN_BUZZ, LOW);  delay(2850);
    }
    Serial.println(F("拒绝音: 80ms 响 / 120ms 停 ×2"));
    for (uint8_t i = 0; i < 2; i++) {
      digitalWrite(PIN_BUZZ, HIGH); delay(80);
      digitalWrite(PIN_BUZZ, LOW);  delay(120);
    }
    Serial.println(F("=== 演示结束，可烧回 UNO_Node.ino ==="));
  }
}

void loop() {
  /* 一次性判定，loop 空转；要重测就按复位 */
}
