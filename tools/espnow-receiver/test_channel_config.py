"""Host regression test of the actual patched receiver channel-save method.

The ESP32 API returns ESP_OK (zero), not bool. Exercise the real method against
radio/storage fakes so a reversed success check cannot pass build validation.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

project = Path(sys.argv[1])
source = (project / 'src/configuration.cpp').read_text()
start = source.index('void Configuration::setWifiChannel(')
opening = source.index('{', start)
depth = 1
end = opening + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
method = source[start:end]

fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
constexpr int ESP_OK = 0;
constexpr int WIFI_SECOND_CHAN_NONE = 0;
int radioResult = 0;
int writes = 0;
int disconnects = 0;
bool openOK = true;
bool writeOK = true;
int esp_wifi_set_channel(uint8_t, int) { return radioResult; }
struct File {
    explicit operator bool() const { return openOK; }
    size_t write(uint8_t*, size_t) { ++writes; return writeOK ? 1 : 0; }
    void close() {}
};
struct FS {
    File open(const char*, const char*, bool) { return {}; }
} LittleFS;
struct Log {
    template<class... T> void printf(const char*, T...) {}
    void println(const char*) {}
} Serial;
class ESPNowCommunication {
public:
    static uint8_t channel;
    static ESPNowCommunication& getInstance() { static ESPNowCommunication x; return x; }
    void disconnectAllTrackers() { ++disconnects; }
};
uint8_t ESPNowCommunication::channel = 0;
namespace SlimeVR {
    struct SerialCom { static bool comEnabled() { return false; } };
    namespace SerialComMessages { struct UpdateChannel { static void print() {} }; }
}
class Configuration {
public:
    const char* wifiChannelPath = "/wifiChannel.bin";
    void setWifiChannel(uint8_t channel);
};
'''
tests = r'''
int main() {
    Configuration config;
    config.setWifiChannel(6); // ESP_OK must persist the selected channel.
    assert(writes == 1 && disconnects == 1 && ESPNowCommunication::channel == 6);
    radioResult = 0x3001;
    writes = disconnects = 0;
    config.setWifiChannel(11); // Failed radio change must not be persisted.
    assert(writes == 0 && disconnects == 0 && ESPNowCommunication::channel == 6);
    radioResult = ESP_OK;
    openOK = false;
    config.setWifiChannel(8); // Storage failure must not erase the live channel.
    assert(writes == 0 && ESPNowCommunication::channel == 8);
    openOK = true;
    writeOK = false;
    config.setWifiChannel(9);
    assert(writes == 1 && disconnects == 0 && ESPNowCommunication::channel == 9);
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    cpp = path / 'channel_config.cpp'
    exe = path / 'channel_config'
    cpp.write_text(fixture + method + tests)
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('Channel-save regression passed: ESP_OK persists, radio errors do not, storage failures retain live channel.')
