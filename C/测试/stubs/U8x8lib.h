#pragma once
#include "Arduino.h"

#define U8X8_PIN_NONE 255
extern const uint8_t u8x8_font_chroma48medium8_r[];

class U8X8 {
public:
  void begin();
  void setFont(const uint8_t*);
  void clearDisplay();
  void drawString(uint8_t, uint8_t, const char*);
};

class U8X8_SSD1306_128X64_NONAME_HW_I2C : public U8X8 {
public:
  explicit U8X8_SSD1306_128X64_NONAME_HW_I2C(uint8_t);
};
