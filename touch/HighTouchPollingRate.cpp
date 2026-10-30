/*
 * SPDX-FileCopyrightText: The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "vendor.lineage.touch-service.malachite"

#include "HighTouchPollingRate.h"

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <chrono>
#include <thread>

#include "mi_disp.h"

using ::android::base::unique_fd;
using ::android::base::WriteStringToFile;
using namespace std::chrono_literals;

namespace aidl {
namespace vendor {
namespace lineage {
namespace touch {

namespace {

// Goodix GT9916R report rate switch (command 0xC0): any value but "0" asks for the high rate,
// "0" for the default 240 Hz.
constexpr char kReportRatePath[] = "/sys/devices/platform/goodix_ts.0/goodix_ts_report_rate";
constexpr char kDispFeaturePath[] = "/dev/mi_display/disp_feature";

// Xiaomi touch mode interface. Stock's 480 Hz is the game mode: the stock gt9916r driver
// answers Touch_Game_Mode = 1 with command 0xC1 ("open 480Hz cmd in gamemode") and 0 with
// 0xC1 0. 0xC0 alone measures about 333 Hz.
constexpr char kTouchDevPath[] = "/dev/xiaomi-touch";
constexpr int kTouchMagic = 't';
constexpr int kSetCurValue = 0;
constexpr int kTouchId = 0;
constexpr int kTouchGameMode = 0;
// xiaomi_touch_dev_ioctl() copies this many ints from userspace on every call.
constexpr int kTouchBufSize = 256;
#define TOUCH_IOC_SET_CUR_VALUE _IO(kTouchMagic, kSetCurValue)

// The driver resets the IC without telling userspace: on the firmware's reset requests
// (goodix_ts_request_handle) and in ESD recovery (goodix_ts_esd_work power-cycles it).
// Neither restores the rate, so while the screen is on it is sent again this often.
constexpr auto kResendInterval = 5s;

bool writeReportRate(bool high) {
    if (!WriteStringToFile(high ? "1" : "0", kReportRatePath)) {
        PLOG(ERROR) << "Failed to write " << kReportRatePath;
        return false;
    }
    return true;
}

bool setGameMode(bool on) {
    unique_fd fd(open(kTouchDevPath, O_RDWR | O_CLOEXEC));
    if (fd < 0) {
        PLOG(ERROR) << "Failed to open " << kTouchDevPath;
        return false;
    }
    int buf[kTouchBufSize] = {kTouchId, kTouchGameMode, on ? 1 : 0};
    if (ioctl(fd.get(), TOUCH_IOC_SET_CUR_VALUE, &buf) < 0) {
        PLOG(ERROR) << "Failed to set the touch game mode";
        return false;
    }
    return true;
}

// Both commands: 0xC1 gives 480 Hz; 0xC0 keeps the report rate switch in step with it.
bool applyRate(bool high) {
    bool reportRate = writeReportRate(high);
    bool gameMode = setGameMode(high);
    return reportRate || gameMode;
}

}  // anonymous namespace

HighTouchPollingRate::HighTouchPollingRate() {
    std::thread([this] { reapplyWhileDisplayOn(); }).detach();
}

ndk::ScopedAStatus HighTouchPollingRate::getEnabled(bool* _aidl_return) {
    // The driver reports its last request, not the IC's state, so report ours.
    std::lock_guard<std::mutex> lock(mLock);
    *_aidl_return = mEnabled;
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus HighTouchPollingRate::setEnabled(bool enabled) {
    std::lock_guard<std::mutex> lock(mLock);
    if (!applyRate(enabled)) {
        return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    }
    mEnabled = enabled;
    return ndk::ScopedAStatus::ok();
}

// The driver resets the IC whenever the display turns on (goodix_ts_resume_work, queued on the
// same display power event), on firmware reset requests and in ESD recovery, and never restores
// the rate. Send it again after each display-on and every kResendInterval while the display is
// on. Nothing is sent while the display is off and the IC sleeps.
void HighTouchPollingRate::reapplyWhileDisplayOn() {
    unique_fd fd(open(kDispFeaturePath, O_RDWR | O_CLOEXEC));
    if (fd < 0) {
        PLOG(ERROR) << "Failed to open " << kDispFeaturePath;
        return;
    }

    disp_event_req req = {};
    req.base.flag = 0;
    req.base.disp_id = MI_DISP_PRIMARY;
    req.type = MI_DISP_EVENT_POWER;
    if (ioctl(fd.get(), MI_DISP_IOCTL_REGISTER_EVENT, &req) < 0) {
        PLOG(ERROR) << "Failed to register for display power events";
        return;
    }

    struct pollfd pfd = {
            .fd = fd.get(),
            .events = POLLIN,
            .revents = 0,
    };
    char buf[1024];
    // The service starts while the display is on.
    bool screenOn = true;
    while (true) {
        int timeoutMs = screenOn ? static_cast<int>(
                                           std::chrono::milliseconds(kResendInterval).count())
                                 : -1;
        int ret = poll(&pfd, 1, timeoutMs);
        if (ret < 0) {
            if (errno == EINTR) continue;
            PLOG(ERROR) << "Failed to poll " << kDispFeaturePath;
            return;
        }
        if (ret == 0) {
            std::lock_guard<std::mutex> lock(mLock);
            if (mEnabled) {
                applyRate(true);
            }
            continue;
        }
        ssize_t size = read(fd.get(), buf, sizeof(buf));
        if (size < 0) {
            PLOG(ERROR) << "Failed to read " << kDispFeaturePath;
            return;
        }

        // A read can return several events back to back. Each event's length counts its
        // header too: mi_disp_feature_event_notify() in mediatek-drm stores the payload
        // size plus sizeof(disp_event). Counting the header twice dropped every event, so
        // the screen was taken to be on forever and the rate was sent to the sleeping IC.
        bool powerEvent = false;
        size_t offset = 0;
        while (offset + sizeof(disp_event) <= static_cast<size_t>(size)) {
            auto* event = reinterpret_cast<disp_event_resp*>(buf + offset);
            size_t length = event->base.length;
            if (length < sizeof(disp_event) || offset + length > static_cast<size_t>(size)) break;
            if (event->base.type == MI_DISP_EVENT_POWER && length > sizeof(disp_event)) {
                powerEvent = true;
                screenOn = event->data[0] == MI_DISP_POWER_ON;
            }
            offset += length;
        }
        if (!powerEvent || !screenOn) continue;

        // The reset takes about 100 ms after the work runs; try once after it and once more
        // in case the first command reached the IC while it was still starting.
        for (auto delay : {500ms, 1000ms}) {
            std::this_thread::sleep_for(delay);
            std::lock_guard<std::mutex> lock(mLock);
            if (mEnabled) {
                applyRate(true);
            }
        }
    }
}

}  // namespace touch
}  // namespace lineage
}  // namespace vendor
}  // namespace aidl
