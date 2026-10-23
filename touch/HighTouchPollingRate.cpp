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

// Goodix GT9916R: any value but "0" sends the 480 Hz report rate command, "0" the 240 Hz one.
constexpr char kReportRatePath[] = "/sys/devices/platform/goodix_ts.0/goodix_ts_report_rate";
constexpr char kDispFeaturePath[] = "/dev/mi_display/disp_feature";
constexpr int kResendIntervalMs = 5000;

bool writeReportRate(bool high) {
    if (!WriteStringToFile(high ? "1" : "0", kReportRatePath)) {
        PLOG(ERROR) << "Failed to write " << kReportRatePath;
        return false;
    }
    return true;
}

}  // anonymous namespace

HighTouchPollingRate::HighTouchPollingRate() {
    std::thread([this] { reapplyOnDisplayOn(); }).detach();
}

ndk::ScopedAStatus HighTouchPollingRate::getEnabled(bool* _aidl_return) {
    // The driver reports its last request, not the IC's state, so report ours.
    std::lock_guard<std::mutex> lock(mLock);
    *_aidl_return = mEnabled;
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus HighTouchPollingRate::setEnabled(bool enabled) {
    std::lock_guard<std::mutex> lock(mLock);
    if (!writeReportRate(enabled)) {
        return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    }
    mEnabled = enabled;
    return ndk::ScopedAStatus::ok();
}

// The touch driver resets the IC whenever the display turns on (goodix_ts_resume_work, queued
// on the same display power event) and does not restore the report rate, so the IC falls back
// to 240 Hz. Listen for display power events and send the rate again once the reset is done.
void HighTouchPollingRate::reapplyOnDisplayOn() {
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
        // The driver also resets the IC without a display event: on the firmware's reset
        // requests (goodix_ts_request_handle) and in ESD recovery (goodix_ts_esd_work power
        // cycles it), and neither sends the rate again. While the screen is on, send it every
        // few seconds; the command is idempotent. Never while the IC sleeps.
        int ret = poll(&pfd, 1, screenOn ? kResendIntervalMs : -1);
        if (ret < 0) {
            if (errno == EINTR) continue;
            PLOG(ERROR) << "Failed to poll " << kDispFeaturePath;
            return;
        }
        if (ret == 0) {
            std::lock_guard<std::mutex> lock(mLock);
            if (mEnabled) {
                writeReportRate(true);
            }
            continue;
        }
        ssize_t size = read(fd.get(), buf, sizeof(buf));
        if (size < 0) {
            PLOG(ERROR) << "Failed to read " << kDispFeaturePath;
            return;
        }

        // A read can return several events back to back.
        bool powerEvent = false;
        size_t offset = 0;
        while (offset + sizeof(disp_event) <= static_cast<size_t>(size)) {
            auto* event = reinterpret_cast<disp_event_resp*>(buf + offset);
            size_t end = offset + sizeof(disp_event) + event->base.length;
            if (end > static_cast<size_t>(size)) break;
            if (event->base.type == MI_DISP_EVENT_POWER && event->base.length > 0) {
                powerEvent = true;
                screenOn = event->data[0] == MI_DISP_POWER_ON;
            }
            offset = end;
        }
        if (!powerEvent || !screenOn) continue;

        // The reset takes about 100 ms after the work runs; try once after it and once more
        // in case the first command reached the IC while it was still starting.
        for (auto delay : {500ms, 1000ms}) {
            std::this_thread::sleep_for(delay);
            std::lock_guard<std::mutex> lock(mLock);
            if (mEnabled) {
                writeReportRate(true);
            }
        }
    }
}

}  // namespace touch
}  // namespace lineage
}  // namespace vendor
}  // namespace aidl
