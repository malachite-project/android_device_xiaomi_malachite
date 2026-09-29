/*
 * Copyright (C) 2018-2022 The LineageOS Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "Light.h"

#include <algorithm>
#include <fstream>

#define LCD_LED         "/sys/devices/platform/mtk-leds/leds/lcd-backlight/"

#define BRIGHTNESS      "brightness"

/*
 * HyperOS keeps this non-zero while the screen is on. The o16u 42-02
 * panel drivers send a different refresh-rate switch sequence (page 3
 * register BA = 0x80) only while it is set; without it every 60/120 Hz
 * switch uses the screen-off sequence. The scale is Xiaomi's, five steps
 * per panel level (normal maximum 10239, peak 20479).
 */
#define BRIGHTNESS_CLONE "/sys/devices/virtual/mi_display/disp_feature/disp-DSI-0/brightness_clone"
#define MAX_BRIGHTNESS_CLONE 20479

namespace {
/*
 * Write value to path and close file.
 */
static void set(std::string path, std::string value) {
    std::ofstream file(path);

    if (!file.is_open()) {
        LOG(WARNING) << "failed to write " << value.c_str() << " to " << path.c_str();
        return;
    }

    file << value;
}

static void set(std::string path, int value) {
    set(path, std::to_string(value));
}

static uint32_t getBrightness(const HwLightState& state) {
    uint32_t alpha, red, green, blue;

    /*
     * Extract brightness from AARRGGBB.
     */
    alpha = (state.color >> 24) & 0xFF;
    red = (state.color >> 16) & 0xFF;
    green = (state.color >> 8) & 0xFF;
    blue = state.color & 0xFF;

    /*
     * Scale RGB brightness using Alpha brightness.
     */
    red = red * alpha / 0xFF;
    green = green * alpha / 0xFF;
    blue = blue * alpha / 0xFF;

    return (77 * red + 150 * green + 29 * blue) >> 8;
}

static inline uint32_t scaleBrightness(uint32_t brightness) {
    if (brightness == 0) {
        return 0;
    }

    return brightness_table[brightness];
}

/*
 * The framework's unrounded level (config_backlightHighPrecision), sent in
 * flashOnMs because a backlight never flashes: 1-65535 for float 0.0-1.0.
 * The 8-bit colour moves 16 panel levels per step, which a slow
 * auto-brightness ramp shows as jumps at low brightness.
 */
#define PRECISE_LEVEL_MAX 65535
#define PANEL_LEVEL_MAX 4095

static inline uint32_t getScaledBrightness(const HwLightState& state) {
    uint32_t brightness = getBrightness(state);

    if (brightness != 0 && state.flashMode == FlashMode::NONE && state.flashOnMs > 0 &&
            state.flashOnMs <= PRECISE_LEVEL_MAX) {
        uint32_t level = (static_cast<uint32_t>(state.flashOnMs) * PANEL_LEVEL_MAX +
                          PRECISE_LEVEL_MAX / 2) / PRECISE_LEVEL_MAX;
        return std::max<uint32_t>(level, brightness_table[1]);
    }

    return scaleBrightness(brightness);
}

static void handleBacklight(const HwLightState& state) {
    uint32_t brightness = getScaledBrightness(state);
    set(LCD_LED BRIGHTNESS, brightness);
    set(BRIGHTNESS_CLONE, std::min<uint32_t>(brightness * 5, MAX_BRIGHTNESS_CLONE));
}

/* Keep sorted in the order of importance. */
static std::vector<LightType> backends = {
    LightType::BACKLIGHT,
};

}  // anonymous namespace

namespace aidl {
namespace android{
namespace hardware {
namespace light {

ndk::ScopedAStatus Lights::setLightState(int id, const HwLightState& state) {
    switch(id) {
        case (int) LightType::BACKLIGHT:
            handleBacklight(state);
            return ndk::ScopedAStatus::ok();
        default:
            return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    }
}

ndk::ScopedAStatus Lights::getLights(std::vector<HwLight>* lights) {
    int i = 0;

    for (const LightType& backend : backends) {
        HwLight hwLight;
        hwLight.id = (int) backend;
        hwLight.type = backend;
        hwLight.ordinal = i;
        lights->push_back(hwLight);
        i++;
    }

    return ndk::ScopedAStatus::ok();
}

}  // namespace light
}  // namespace hardware
}  // namespace android
}  // namespace aidl
