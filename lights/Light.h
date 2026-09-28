/*
 * Copyright (C) 2022 The LineageOS Project
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

#pragma once

#include <aidl/android/hardware/light/BnLights.h>
#include <android-base/logging.h>
#include <hardware/hardware.h>
#include <hardware/lights.h>
#include <vector>

/*
 * Panel levels (DCS 0x51, 12 bits): 1-2047 normal, 2048-4094 high
 * brightness, 4095 turns on the panel's peak mode. Levels 0-158 are the
 * release's curve, which reaches the normal maximum at 158. Without
 * sunlight the framework stops at level 217, so 159-217 hold the normal
 * maximum and only the sunlight range (218-255) drives high brightness.
 */
static unsigned int brightness_table[256] = {
         0,     15,     16,     17,     18,     19,     20,     21,
        22,     23,     24,     25,     26,     27,     28,     29,
        30,     31,     32,     34,     37,     39,     42,     44,
        47,     50,     53,     57,     60,     64,     67,     71,
        76,     80,     84,     89,     93,     98,    103,    108,
       114,    119,    125,    131,    137,    143,    149,    156,
       163,    169,    177,    184,    191,    199,    206,    214,
       222,    230,    239,    247,    256,    265,    274,    284,
       293,    303,    312,    322,    333,    343,    354,    364,
       375,    386,    398,    409,    421,    433,    445,    457,
       469,    482,    495,    508,    521,    534,    548,    561,
       575,    589,    604,    618,    633,    648,    663,    678,
       693,    709,    725,    741,    757,    774,    790,    807,
       824,    841,    859,    876,    894,    912,    930,    949,
       967,    986,   1005,   1024,   1044,   1063,   1083,   1103,
      1123,   1144,   1164,   1185,   1206,   1227,   1249,   1271,
      1292,   1314,   1337,   1359,   1382,   1405,   1428,   1451,
      1475,   1498,   1522,   1546,   1571,   1595,   1620,   1645,
      1670,   1696,   1721,   1747,   1773,   1799,   1826,   1852,
      1879,   1906,   1934,   1961,   1989,   2017,   2045,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2047,   2047,   2047,   2047,   2047,   2047,
      2047,   2047,   2048,   2103,   2159,   2214,   2269,   2325,
      2380,   2435,   2491,   2546,   2601,   2657,   2712,   2767,
      2823,   2878,   2933,   2989,   3044,   3099,   3154,   3210,
      3265,   3320,   3376,   3431,   3486,   3542,   3597,   3652,
      3708,   3763,   3818,   3874,   3929,   3984,   4040,   4095,
};


using ::aidl::android::hardware::light::HwLightState;
using ::aidl::android::hardware::light::HwLight;
using ::aidl::android::hardware::light::LightType;
using ::aidl::android::hardware::light::BnLights;

namespace aidl {
namespace android {
namespace hardware {
namespace light {

class Lights : public BnLights {
      ndk::ScopedAStatus setLightState(int id, const HwLightState& state) override;
      ndk::ScopedAStatus getLights(std::vector<HwLight>* types) override;
};

}  // namespace light
}  // namespace hardware
}  // namespace android
}  // namespace aidl
