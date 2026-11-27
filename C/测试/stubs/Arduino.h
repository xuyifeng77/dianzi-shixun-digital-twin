#pragma once
/* 仅用于 g++ -fsyntax-only 静态检查的 Arduino 桩头文件，不参与烧录 */
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>

#define F(x) x
using std::isnan;   /* AVR 的 math.h 把 isnan 当宏/全局函数，桩里等效 */
using std::isinf;
#define HIGH 0x1
#define LOW  0x0
#define INPUT 0x0
#define OUTPUT 0x1
#define INPUT_PULLUP 0x2
#define A0 14
#define A1 15
#define A2 16
#define A3 17
#define A4 18
#define A5 19

extern uint8_t MCUSR;
uint32_t millis();
void pinMode(uint8_t, uint8_t);
void digitalWrite(uint8_t, uint8_t);
int  digitalRead(uint8_t);
void analogWrite(uint8_t, int);
void delay(uint32_t);

struct SerialStub {
  void begin(long);
  int  available();
  int  read();
  void print(const char*);
  void print(char);
  void print(int);
  void print(unsigned int);
  void print(long);
  void print(unsigned long);
  void print(float, int = 2);
  void println(const char* = "");
  void println(int);
  void println(unsigned int);
  void println(long);
  void println(unsigned long);
  void println(float, int = 2);
};
extern SerialStub Serial;
