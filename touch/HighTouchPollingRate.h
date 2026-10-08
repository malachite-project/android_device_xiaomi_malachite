/*
 * SPDX-FileCopyrightText: The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/vendor/lineage/touch/BnHighTouchPollingRate.h>

#include <mutex>

namespace aidl {
namespace vendor {
namespace lineage {
namespace touch {

class HighTouchPollingRate : public BnHighTouchPollingRate {
  public:
    HighTouchPollingRate();

    ndk::ScopedAStatus getEnabled(bool* _aidl_return) override;
    ndk::ScopedAStatus setEnabled(bool enabled) override;

  private:
    void reapplyOnDisplayOn();

    std::mutex mLock;
    bool mEnabled = false;
};

}  // namespace touch
}  // namespace lineage
}  // namespace vendor
}  // namespace aidl
