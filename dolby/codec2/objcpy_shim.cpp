/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

// Stock's Dolby Vision client (c2.dolby.client.so) was built before
// BufferPoolSender became a template (frameworks/av ab22b47666), so it imports
// objcpy(WorkBundle*, list<unique_ptr<C2Work>>, utils::BufferPoolSender*) by its
// old name. The class layout did not change: the object it passes is the
// platform's DefaultBufferPoolSender, built with the platform's constructor.

#include <codec2/hidl/1.0/types.h>

using ::android::hardware::media::c2::V1_0::WorkBundle;
using ::android::hardware::media::c2::V1_0::utils::BufferPoolSender;
using ::android::hardware::media::c2::V1_0::utils::objcpy;

extern "C" bool
_ZN7android8hardware5media2c24V1_05utils6objcpyEPNS3_10WorkBundleERKNSt3__14listINS7_10unique_ptrI6C2WorkNS7_14default_deleteISA_EEEENS7_9allocatorISD_EEEEPNS4_16BufferPoolSenderE(
        WorkBundle* d, const std::list<std::unique_ptr<C2Work>>& s, void* bpSender) {
    return objcpy(d, s, static_cast<BufferPoolSender*>(bpSender));
}
