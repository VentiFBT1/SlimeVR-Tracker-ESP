"""Run the actual receiver Serial.h with a bounded USB FIFO and closed host."""
from pathlib import Path
import subprocess
import sys
import tempfile

project = Path(sys.argv[1]).resolve()
stub = r'''
#pragma once
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
using String = std::string;
struct Stream {
    virtual ~Stream() = default;
    virtual size_t write(uint8_t) = 0;
    virtual size_t write(const uint8_t*, size_t) = 0;
    virtual int available() = 0;
    virtual int read() = 0;
    virtual int peek() = 0;
    virtual void flush() = 0;
};
struct HardwareSerial {
    void begin(unsigned long) {}
    int availableForWrite() { return 0; } // Unread/unavailable UART must not block.
    size_t write(const uint8_t*, size_t n) { assert(n == 0); return n; }
    int available() { return 0; }
    int read() { return -1; }
    int peek() { return -1; }
    void flush() { assert(false); }
    explicit operator bool() const { return true; }
};
extern HardwareSerial Serial0;
struct USBCDC {
    bool connected = true;
    int space = 0;
    std::vector<uint8_t> output;
    void begin() {}
    void setTxTimeoutMs(uint32_t) {}
    int availableForWrite() { return connected ? space : 0; }
    size_t write(const uint8_t* bytes, size_t length) {
        // The real Arduino driver can spin indefinitely if this is violated.
        assert(connected && length <= static_cast<size_t>(space));
        output.insert(output.end(), bytes, bytes + length);
        space -= length;
        return length;
    }
    int available() { return 0; }
    int read() { return -1; }
    int peek() { return -1; }
    void flush() { assert(false); }
    explicit operator bool() const { return connected; }
};
struct StaticSemaphore_t { bool held = false; };
using SemaphoreHandle_t = StaticSemaphore_t*;
constexpr int pdTRUE = 1;
constexpr uint32_t portMAX_DELAY = 0xffffffff;
inline bool forceBusy = false;
inline SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t* m) { return m; }
inline int xSemaphoreTake(SemaphoreHandle_t m, uint32_t wait) {
    assert(wait == 0); // Radio callbacks and logging must never wait for a host.
    if (forceBusy || m->held) return 0;
    m->held = true;
    return pdTRUE;
}
inline void xSemaphoreGive(SemaphoreHandle_t m) { assert(m->held); m->held = false; }
'''
tests = r'''
#include "Serial.h"
HardwareSerial Serial0;
USBCDC USBSerial;
void drain(HybridSerial& serial, int ticks = 100) {
    for (int i = 0; i < ticks; ++i) { USBSerial.space = 8; serial.tick(); }
}
int main() {
    HybridSerial serial;
    serial.begin();
    USBSerial.space = 4;
    std::string payload(120, 'A');
    assert(serial.writeLine(reinterpret_cast<const uint8_t*>(payload.data()), payload.size()) == 122);
    drain(serial);
    assert(std::string(USBSerial.output.begin(), USBSerial.output.end()) == payload + "\r\n");

    USBSerial.output.clear();
    USBSerial.space = 0;
    for (int i = 0; i < 10000; ++i) serial.println("Host stopped reading");
    assert(USBSerial.output.empty()); // Full TX queues drop diagnostics; they do not block.
    USBSerial.connected = false;
    serial.tick();
    USBSerial.connected = true;
    USBSerial.space = 64;
    serial.println("fresh");
    drain(serial);
    assert(std::string(USBSerial.output.begin(), USBSerial.output.end()) == "fresh\r\n");

    USBSerial.output.clear();
    USBSerial.space = 64;
    std::string tooLong(5000, 'B');
    serial.printf("%s", tooLong.c_str());
    drain(serial);
    assert(USBSerial.output.size() == 255); // vsnprintf length cannot overread the stack buffer.

    USBSerial.output.clear();
    forceBusy = true;
    assert(serial.println("drop on contention") == 0);
    forceBusy = false;
    USBSerial.space = 64;
    serial.println("next");
    serial.flush();
    drain(serial);
    assert(std::string(USBSerial.output.begin(), USBSerial.output.end()) == "next\r\n");
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'stub.h').write_text(stub)
    for name in ['Arduino.h', 'USB.h', 'USBCDC.h', 'freertos/FreeRTOS.h', 'freertos/semphr.h']:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "stub.h"\n')
    cpp = root / 'serial_backpressure.cpp'
    cpp.write_text(tests)
    exe = root / 'serial_backpressure'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(root),
                    '-I', str(project / 'src'), str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=5)
print('Serial backpressure regression passed: partial FIFO, unread host, reconnect, oversized printf, contention.')
