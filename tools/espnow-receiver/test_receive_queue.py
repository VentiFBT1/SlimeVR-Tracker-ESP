"""Compile the real RX queue/callback/drain and disconnect cleanup on the host.

Checks transient SDK buffers are copied, Wi-Fi callbacks never execute handlers,
full queues never wait, and ten 100-Hz simulated senders can be drained fairly.
This tests software scheduling, not RF/USB throughput on ten physical trackers.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

project = Path(sys.argv[1])
source = (project / 'src/espnow/espnow.cpp').read_text(encoding='utf-8')

def method(signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

fixture = r'''
#include <cassert>
#include <array>
#include <vector>
#include <functional>
#include <cstdint>
#include <algorithm>
#include "receiveQueue.h"
bool inWifiCallback = false;
struct Log { template<class... T> void printf(const char*, T...) {} void println(const char*) {} } Serial;
enum class ESPNowMessageTypes : uint8_t { TRACKER_DATA=6 };
class ESPNowCommunication {
public:
    struct Tracker { std::array<uint8_t,6> mac{}; uint8_t trackerId=0; };
    ESPNowReceiveQueue receiveQueue;
    bool scanningEnvironment=false, sendRateUpdateNextTick=false;
    std::vector<Tracker> connectedTrackers;
    std::vector<uint8_t> disconnected;
    std::array<uint32_t,10> delivered{};
    size_t handlers = 0;
    static ESPNowCommunication& getInstance() { static ESPNowCommunication value; return value; }
    static void onReceive(const esp_now_recv_info_t*, const uint8_t*, int);
    void processReceivedMessages();
    void handleMessage(const esp_now_recv_info_t* info, const uint8_t* data, int size) {
        assert(!inWifiCallback);
        assert(info->rx_ctrl->rssi == -42);
        assert(size == 18 && data[0] == 6 && data[1] == 16 && data[2] == 1);
        assert(info->src_addr[0] < delivered.size());
        ++delivered[info->src_addr[0]];
        ++handlers;
    }
    bool deletePeer(const uint8_t*) { assert(!inWifiCallback); return true; }
    void invokeTrackerDisconnectedEvent(Tracker t) { disconnected.push_back(t.trackerId); }
    bool disconnectSingleTracker(const uint8_t*);
    void disconnectAllTrackers();
};
'''
tests = r'''
int main() {
    auto& receiver = ESPNowCommunication::getInstance();
    assert(receiver.receiveQueue.begin());
    uint8_t mac[6]{};
    wifi_pkt_rx_ctrl_t radio{}; radio.rssi = -42;
    esp_now_recv_info_t info{}; info.src_addr=mac; info.rx_ctrl=&radio;
    uint8_t payload[18]{}; payload[0]=6; payload[1]=16; payload[2]=1;
    auto receive = [&]() {
        inWifiCallback=true;
        ESPNowCommunication::onReceive(&info,payload,sizeof(payload));
        inWifiCallback=false;
    };
    // Mutating callback-owned storage cannot alter an already-queued frame.
    receive(); mac[0]=9; payload[0]=255; radio.rssi=0;
    receiver.processReceivedMessages();
    assert(receiver.delivered[0]==1);
    payload[0]=6; radio.rssi=-42;
    // Ten trackers, 100 motion packets/s each, for a simulated minute.
    auto initialHandlers=receiver.handlers;
    for (int tick=0; tick<6000; ++tick) {
        for (int tracker=0; tracker<10; ++tracker) { mac[0]=tracker; receive(); }
        auto before=receiver.handlers;
        receiver.processReceivedMessages();
        assert(receiver.handlers-before==10);
        // Returning here lets the main loop service USB/buttons/serial each pass.
    }
    assert(receiver.handlers-initialHandlers==60000);
    for (int tracker=0; tracker<10; ++tracker) assert(receiver.delivered[tracker]==6000+(tracker==0));
    assert(receiver.receiveQueue.droppedFrames()==0);
    // A stopped consumer must not block its Wi-Fi producer indefinitely.
    for (int i=0; i<100000; ++i) receive();
    assert(receiver.receiveQueue.droppedFrames()==100000-ESPNowReceiveQueue::Capacity);
    auto before=receiver.handlers;
    receiver.processReceivedMessages();
    assert(receiver.handlers-before==ESPNowReceiveQueue::Capacity);
    // Scanning discards queued radio frames without processing stale peers.
    receive(); receiver.scanningEnvironment=true; receiver.processReceivedMessages();
    receiver.scanningEnvironment=false;
    assert(receiver.handlers-before==ESPNowReceiveQueue::Capacity);
    ESPNowReceiveQueue::Frame frame;
    assert(!receiver.receiveQueue.pop(frame));
    assert(!receiver.receiveQueue.push(nullptr,payload,18));
    assert(!receiver.receiveQueue.push(&info,nullptr,18));
    assert(!receiver.receiveQueue.push(&info,payload,0));
    assert(!receiver.receiveQueue.push(&info,payload,251));
    // Remove multiple saved connections without iterating an invalidated vector.
    for (int i=0;i<10;++i) { ESPNowCommunication::Tracker t; t.mac[0]=i; t.trackerId=i; receiver.connectedTrackers.push_back(t); }
    receiver.disconnectAllTrackers();
    assert(receiver.connectedTrackers.empty() && receiver.disconnected.size()==10);
    std::sort(receiver.disconnected.begin(),receiver.disconnected.end());
    for(int i=0;i<10;++i) assert(receiver.disconnected[i]==i);
}
'''

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path/'freertos').mkdir()
    (path/'freertos/FreeRTOS.h').write_text('#pragma once\nconstexpr int pdTRUE=1;\n', encoding='utf-8')
    (path/'freertos/queue.h').write_text(r'''
#pragma once
#include <deque>
#include <vector>
#include <cstring>
#include <cassert>
struct StaticQueue_t { size_t capacity=0, itemSize=0; std::deque<std::vector<uint8_t>> items; };
using QueueHandle_t=StaticQueue_t*;
inline QueueHandle_t xQueueCreateStatic(size_t n,size_t size,uint8_t*,StaticQueue_t* q) { q->capacity=n; q->itemSize=size; return q; }
inline int xQueueSend(QueueHandle_t q,const void* item,int wait) {
    assert(wait==0);
    if(q->items.size()==q->capacity) return 0;
    const auto* p=static_cast<const uint8_t*>(item);
    q->items.emplace_back(p,p+q->itemSize); return 1;
}
inline int xQueueReceive(QueueHandle_t q,void* item,int wait) {
    assert(wait==0);
    if(q->items.empty()) return 0;
    memcpy(item,q->items.front().data(),q->itemSize); q->items.pop_front(); return 1;
}
''', encoding='utf-8')
    (path/'esp_now.h').write_text('''#pragma once
#include <cstdint>
constexpr int ESP_NOW_MAX_DATA_LEN=250;
struct wifi_pkt_rx_ctrl_t { int8_t rssi; };
struct esp_now_recv_info_t { uint8_t* src_addr; uint8_t* des_addr; wifi_pkt_rx_ctrl_t* rx_ctrl; };
''', encoding='utf-8')
    (path/'receiveQueue.h').write_text((project/'src/espnow/receiveQueue.h').read_text(encoding='utf-8'), encoding='utf-8')
    cpp = path/'receive_queue.cpp'
    actual = '\n'.join(method(x) for x in [
        'void ESPNowCommunication::onReceive(', 'void ESPNowCommunication::processReceivedMessages(',
        'bool ESPNowCommunication::disconnectSingleTracker(', 'void ESPNowCommunication::disconnectAllTrackers('])
    cpp.write_text(fixture+actual+tests, encoding='utf-8')
    exe = path/'receive_queue'
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-D_GLIBCXX_DEBUG','-I',str(path),str(cpp),'-o',str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
print('Deferred RX regression passed: ten 100-Hz senders, copied buffers, nonblocking overload, safe disconnect cleanup.')
