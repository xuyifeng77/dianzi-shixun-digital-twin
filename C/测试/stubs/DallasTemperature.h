#pragma once
#include "Arduino.h"
#include "OneWire.h"

class DallasTemperature {
public:
  explicit DallasTemperature(OneWire*);
  void begin();
  void setResolution(uint8_t);
  float getTempCByIndex(uint8_t);
};
