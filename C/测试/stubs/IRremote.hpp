#pragma once
#include "Arduino.h"

#define DISABLE_LED_FEEDBACK false

struct DecodedIRData {
  uint8_t command;
};

class IRrecv {
public:
  void begin(uint8_t, bool = true);
  bool decode();
  void resume();
  DecodedIRData decodedIRData;
};
extern IRrecv IrReceiver;
