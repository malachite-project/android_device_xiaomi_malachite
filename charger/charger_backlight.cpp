/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The panel init sequence the driver sends on every screen-on sets the
 * brightness (DCS 0x51) to 0. In Android the framework sets the backlight
 * again after each screen-on, but the charging screen never does: the first
 * time it shows, the panel is still lit as the bootloader left it, and every
 * later wake by the power key comes back at the lowest brightness. Listen
 * for the display driver's power-on event and send the backlight again.
 */

#define LOG_TAG "charger_backlight"

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/unique_fd.h>

#include <fcntl.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <string>

#include "mi_disp.h"

namespace {

constexpr char kDispFeaturePath[] = "/dev/mi_display/disp_feature";
constexpr char kBacklightPath[] = "/sys/devices/platform/mtk-leds/leds/lcd-backlight/brightness";

// The level init.mt6878.rc sets on the charging screen.
constexpr int kChargerBrightness = 1500;

// MI_DISP_DPMS_ON in the kernel's mi_disp_notifier.h: the panel is on and not dozing.
constexpr uint32_t kDpmsOn = 0;

void setBacklight() {
    // leds-mtk skips a write that matches the last level it set, and nothing
    // has set another one since the charging screen started, so step through
    // a different level first.
    if (!android::base::WriteStringToFile(std::to_string(kChargerBrightness - 1),
                                          kBacklightPath) ||
        !android::base::WriteStringToFile(std::to_string(kChargerBrightness), kBacklightPath)) {
        PLOG(ERROR) << "failed to write " << kBacklightPath;
    }
}

}  // anonymous namespace

int main() {
    android::base::unique_fd fd(open(kDispFeaturePath, O_RDWR | O_CLOEXEC));
    if (fd.get() < 0) {
        PLOG(ERROR) << "failed to open " << kDispFeaturePath;
        return 1;
    }

    disp_event_req req = {};
    req.base.flag = 0;
    req.base.disp_id = MI_DISP_PRIMARY;
    req.type = MI_DISP_EVENT_POWER;
    if (ioctl(fd.get(), MI_DISP_IOCTL_REGISTER_EVENT, &req) < 0) {
        PLOG(ERROR) << "failed to register for display power events";
        return 1;
    }

    struct pollfd pfd = {.fd = fd.get(), .events = POLLIN, .revents = 0};
    alignas(disp_event_resp) char buf[1024];

    while (true) {
        if (poll(&pfd, 1, -1) < 0) {
            if (errno != EINTR) PLOG(ERROR) << "poll failed";
            continue;
        }

        ssize_t size = TEMP_FAILURE_RETRY(read(fd.get(), buf, sizeof(buf)));
        if (size < 0) {
            PLOG(ERROR) << "read failed";
            continue;
        }

        // A read can return several events; base.length covers header and data.
        bool poweredOn = false;
        for (ssize_t offset = 0; offset + (ssize_t)sizeof(disp_event) <= size;) {
            const auto* event = reinterpret_cast<const disp_event_resp*>(buf + offset);
            if (event->base.length < sizeof(disp_event) ||
                offset + (ssize_t)event->base.length > size) {
                break;
            }
            if (event->base.type == MI_DISP_EVENT_POWER &&
                event->base.length >= sizeof(disp_event) + sizeof(uint32_t)) {
                uint32_t state;
                memcpy(&state, event->data, sizeof(state));
                poweredOn = state == kDpmsOn;
            }
            offset += event->base.length;
        }

        if (poweredOn) {
            setBacklight();
        }
    }
}
