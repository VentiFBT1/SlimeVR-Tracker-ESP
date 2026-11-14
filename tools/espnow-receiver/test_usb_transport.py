"""Run actual USB report scheduling and console methods against host fakes."""
from pathlib import Path
import subprocess
import tempfile
import sys

project=Path(sys.argv[1])
def method(file, signature):
    text=(project/file).read_text(encoding='utf-8')
    start=text.index(signature); opening=text.index('{',start); depth=1; end=opening+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}'); end+=1
    return text[start:end]

fixture=r'''
#include <cassert>
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <deque>
#include <string>
#include <vector>
uint32_t clockMs=0;
uint32_t millis() { return clockMs; }
struct HIDDevice {
    bool isReady=true, accept=true;
    unsigned attempts=0;
    std::vector<std::array<uint8_t,64>> transfers;
    bool ready() { return isReady; }
    bool send(const uint8_t* data,size_t length) {
        assert(length==64); ++attempts;
        if(!accept) return false;
        std::array<uint8_t,64> copy{}; memcpy(copy.data(),data,64); transfers.push_back(copy); return true;
    }
};
struct Packet { uint8_t data[128]{}; };
struct Buffer {
    std::deque<Packet> items;
    uint8_t size() { return static_cast<uint8_t>(items.size()); }
    Packet& operator[](size_t i) { return items.at(i); }
    void shift() { assert(!items.empty()); items.pop_front(); }
    void add(uint8_t type,uint8_t id) { Packet p; p.data[0]=type; p.data[1]=id; items.push_back(p); }
};
struct PacketHandling {
    static constexpr size_t reportsPerTransfer=4,reportSize=16,hidTransferSize=64;
    Buffer buffer,priorityBuffer;
    uint32_t lastSendAttempt=0,acceptedUSBTransfers=0,failedUSBTransfers=0;
    void tick(HIDDevice&);
};
class String:public std::string {
public:
    using std::string::operator=;
    void trim() {
        auto first=find_first_not_of(" \t\r\n");
        if(first==npos) { clear(); return; }
        auto last=find_last_not_of(" \t\r\n");
        *this=substr(first,last-first+1);
    }
};
struct SerialInput {
    std::deque<char> input;
    unsigned reads=0;
    bool phantomAvailable=false;
    int available() { return phantomAvailable ? 1 : static_cast<int>(input.size()); }
    int read() { ++reads; if(input.empty()) return -1; char c=input.front(); input.pop_front(); return static_cast<uint8_t>(c); }
    void append(const std::string& s) { for(char c:s)input.push_back(c); }
} Serial;
std::vector<std::string> commands;
void processConsoleCommand(const String& command) { commands.push_back(command); }
struct ConsoleCommandHandler { void update(); };
'''
tests=r'''
int main() {
    PacketHandling packets; HIDDevice hid;
    // Idle receiver services SlimeVR without fabricating tracker updates.
    for(clockMs=0;clockMs<=2000;++clockMs) packets.tick(hid);
    assert(hid.transfers.size()==40);
    for(const auto& transfer:hid.transfers) for(size_t i=0;i<4;++i) {
        assert(transfer[i*16]==0xfe && transfer[i*16+1]==0xff);
        for(size_t j=2;j<16;++j) assert(transfer[i*16+j]==0);
    }
    // Not-ready endpoints do not consume pending registration or motion.
    packets.priorityBuffer.add(255,7); packets.buffer.add(1,7);
    hid.isReady=false; auto attempts=hid.attempts;
    packets.tick(hid);
    assert(hid.attempts==attempts && packets.buffer.size()==1 && packets.priorityBuffer.size()==1);
    // Failed submission must also preserve both queues for retry.
    hid.isReady=true; hid.accept=false; packets.tick(hid);
    assert(packets.failedUSBTransfers==1 && packets.buffer.size()==1 && packets.priorityBuffer.size()==1);
    hid.accept=true; packets.tick(hid);
    assert(packets.buffer.size()==0 && packets.priorityBuffer.size()==0);
    auto& last=hid.transfers.back();
    assert(last[0]==255 && last[1]==7 && last[16]==1 && last[17]==7);
    assert(last[32]==0xfe && last[33]==0xff);
    // Ten senders' reports drain through bounded four-report USB frames.
    for(int id=0;id<10;++id) packets.buffer.add(1,id);
    for(int tick=0;tick<3;++tick) packets.tick(hid);
    assert(packets.buffer.size()==0);
    ConsoleCommandHandler console;
    Serial.append(std::string(10000,'X')+"\nstatus\n");
    auto before=Serial.reads; console.update();
    assert(Serial.reads-before<=64 && !Serial.input.empty());
    while(!Serial.input.empty()) console.update();
    assert(commands.size()==1 && commands[0]=="status");
    Serial.phantomAvailable=true; before=Serial.reads; console.update();
    assert(Serial.reads-before==1);
}
'''
with tempfile.TemporaryDirectory() as d:
    root=Path(d); cpp=root/'usb_transport.cpp'; exe=root/'usb_transport'
    cpp.write_text(fixture+method('src/packetHandling.cpp','void PacketHandling::tick(')+
                   method('src/ConsoleCommandHandler.cpp','void ConsoleCommandHandler::update(')+tests,encoding='utf-8')
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-D_GLIBCXX_DEBUG',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=5)
print('USB transport regression passed: idle keep-alives, pending-report retention, ten senders, bounded console flood.')
