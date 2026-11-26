#pragma once
#include "Arduino.h"

class TwoWire {
public:
  void begin();
  void beginTransmission(uint8_t);
  size_t write(uint8_t);
  uint8_t endTransmission();
  uint8_t requestFrom(uint8_t, uint8_t);
  int available();
  int read();
};
extern TwoWire Wire;
