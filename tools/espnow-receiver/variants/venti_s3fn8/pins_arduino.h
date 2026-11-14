#pragma once
#include <stdint.h>
#include <stdbool.h>

#define USB_VID 0x1209
#define USB_PID 0x7690
#define USB_MANUFACTURER "VentiFBT"
#define USB_PRODUCT "Venti ESP-NOW Receiver Test"
#define USB_SERIAL "VENTI-ESPNOW"

static const uint8_t TX = 43;
static const uint8_t RX = 44;
static const uint8_t USER_BUTTON = 0;
static const bool USER_BUTTON_ACTIVE_LEVEL = false;
static const uint8_t LED_BUILTIN = 1;
#define LED_BUILTIN LED_BUILTIN
#define BUILTIN_LED LED_BUILTIN
static const bool LED_ACTIVE_LEVEL = true;

