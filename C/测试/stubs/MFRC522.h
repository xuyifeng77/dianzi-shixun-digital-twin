#pragma once
#include "Arduino.h"

struct Uid {
  uint8_t size;
  uint8_t uidByte[10];
};

class MFRC522 {
public:
  MFRC522(uint8_t, uint8_t);
  void PCD_Init();
  bool PICC_IsNewCardPresent();
  bool PICC_ReadCardSerial();
  void PICC_HaltA();
  void PCD_StopCrypto1();
  Uid uid;
};
