/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

// Serves one of stock's Dolby Codec2 stores as AIDL IComponentStore/<instance>.
// Usage: android.hardware.media.c2-dolby-service <store library> <instance>

#define LOG_TAG "android.hardware.media.c2-dolby-service"

#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <codec2/aidl/ComponentStore.h>
#include <hidl/HidlTransportSupport.h>

#include <dlfcn.h>
#include <signal.h>

#include <memory>
#include <string>
#include <thread>

namespace {

// Both stock store libraries export android::GetCodec2DolbyComponentStore(),
// so each one runs in its own process and is found with dlsym.
constexpr char kGetStoreSymbol[] = "_ZN7android28GetCodec2DolbyComponentStoreEv";
using GetStoreFn = std::shared_ptr<C2ComponentStore> (*)();

constexpr int kThreadCount = 8;

}  // anonymous namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        LOG(ERROR) << "usage: " << argv[0] << " <store library> <instance>";
        return 1;
    }
    const char* library = argv[1];
    const std::string instance = argv[2];

    signal(SIGPIPE, SIG_IGN);

    void* handle = dlopen(library, RTLD_NOW | RTLD_LOCAL);
    if (handle == nullptr) {
        LOG(ERROR) << "Cannot load " << library << ": " << dlerror();
        return 1;
    }
    auto getStore = reinterpret_cast<GetStoreFn>(dlsym(handle, kGetStoreSymbol));
    if (getStore == nullptr) {
        LOG(ERROR) << library << " has no " << kGetStoreSymbol;
        return 1;
    }

    // The Dolby Vision decoder drives the hardware HEVC decoder through a HIDL
    // Codec2 client, whose listener callbacks arrive over hwbinder.
    std::thread([] {
        android::hardware::configureRpcThreadpool(kThreadCount, true /* callerWillJoin */);
        android::hardware::joinRpcThreadpool();
    }).detach();

    ABinderProcess_setThreadPoolMaxThreadCount(kThreadCount);
    ABinderProcess_startThreadPool();

    using namespace ::aidl::android::hardware::media::c2;
    std::shared_ptr<C2ComponentStore> c2Store = getStore();
    if (c2Store == nullptr) {
        LOG(ERROR) << "Cannot create the Codec2 store from " << library;
        return 1;
    }
    std::shared_ptr<IComponentStore> store =
            ::ndk::SharedRefBase::make<utils::ComponentStore>(c2Store);

    const std::string serviceName = std::string(IComponentStore::descriptor) + "/" + instance;
    if (AServiceManager_addService(store->asBinder().get(), serviceName.c_str()) != EX_NONE) {
        LOG(ERROR) << "Cannot register " << serviceName;
        return 1;
    }
    LOG(INFO) << "Registered " << serviceName << " from " << library;

    ABinderProcess_joinThreadPool();
    return 1;
}
