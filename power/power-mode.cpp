/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <aidl/android/hardware/power/BnPower.h>
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include <fcntl.h>
#include <sys/ioctl.h>

#define SET_CUR_VALUE 0
#define TOUCH_DOUBLETAP_MODE 14
#define TOUCH_MAGIC 't'
#define TOUCH_IOC_SETMODE _IO(TOUCH_MAGIC, SET_CUR_VALUE)
#define TOUCH_DEV_PATH "/dev/xiaomi-touch"
#define TOUCH_ID 0
// xiaomi_touch_dev_ioctl() copies this many ints from userspace on every call.
#define TOUCH_BUF_SIZE 256

namespace aidl {
namespace google {
namespace hardware {
namespace power {
namespace impl {
namespace pixel {

using ::aidl::android::hardware::power::Mode;

bool isDeviceSpecificModeSupported(Mode type, bool* _aidl_return) {
    switch (type) {
        case Mode::DOUBLE_TAP_TO_WAKE:
            *_aidl_return = true;
            return true;
        default:
            return false;
    }
}

bool setDeviceSpecificMode(Mode type, bool enabled) {
    switch (type) {
        case Mode::DOUBLE_TAP_TO_WAKE: {
            android::base::unique_fd fd(open(TOUCH_DEV_PATH, O_RDWR | O_CLOEXEC));
            if (fd < 0) {
                PLOG(ERROR) << "Failed to open " << TOUCH_DEV_PATH;
                return true;
            }
            int arg[TOUCH_BUF_SIZE] = {TOUCH_ID, TOUCH_DOUBLETAP_MODE, enabled ? 1 : 0};
            if (ioctl(fd, TOUCH_IOC_SETMODE, &arg) < 0) {
                PLOG(ERROR) << "Failed to set double tap to wake";
            }
            return true;
        }
        default:
            return false;
    }
}

}  // namespace pixel
}  // namespace impl
}  // namespace power
}  // namespace hardware
}  // namespace google
}  // namespace aidl
