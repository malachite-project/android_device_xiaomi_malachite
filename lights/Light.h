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
 * brightness, 4095 turns on the panel's peak mode. Stock's composer maps
 * brightness linearly (level = 4095 * float), which is what the nits map
 * in display_id_*.xml describes (0.5 = normal maximum = 500 nits). The
 * framework sends level L = 1 + 254 * float, so 128 (float 0.5, the
 * high-brightness transition point) is the normal maximum and 129-255 only
 * apply in sunlight. Level 1 keeps the release's minimum of 15.
 */
static unsigned int brightness_table[256] = {
         0,     15,     16,     32,     48,     64,     80,     96,
       112,    128,    145,    161,    177,    193,    209,    225,
       241,    257,    274,    290,    306,    322,    338,    354,
       370,    386,    403,    419,    435,    451,    467,    483,
       499,    515,    532,    548,    564,    580,    596,    612,
       628,    644,    661,    677,    693,    709,    725,    741,
       757,    773,    789,    806,    822,    838,    854,    870,
       886,    902,    918,    935,    951,    967,    983,    999,
      1015,   1031,   1047,   1064,   1080,   1096,   1112,   1128,
      1144,   1160,   1176,   1193,   1209,   1225,   1241,   1257,
      1273,   1289,   1305,   1322,   1338,   1354,   1370,   1386,
      1402,   1418,   1434,   1450,   1467,   1483,   1499,   1515,
      1531,   1547,   1563,   1579,   1596,   1612,   1628,   1644,
      1660,   1676,   1692,   1708,   1725,   1741,   1757,   1773,
      1789,   1805,   1821,   1837,   1854,   1870,   1886,   1902,
      1918,   1934,   1950,   1966,   1983,   1999,   2015,   2031,
      2047,   2063,   2079,   2095,   2111,   2128,   2144,   2160,
      2176,   2192,   2208,   2224,   2240,   2257,   2273,   2289,
      2305,   2321,   2337,   2353,   2369,   2386,   2402,   2418,
      2434,   2450,   2466,   2482,   2498,   2515,   2531,   2547,
      2563,   2579,   2595,   2611,   2627,   2644,   2660,   2676,
      2692,   2708,   2724,   2740,   2756,   2772,   2789,   2805,
      2821,   2837,   2853,   2869,   2885,   2901,   2918,   2934,
      2950,   2966,   2982,   2998,   3014,   3030,   3047,   3063,
      3079,   3095,   3111,   3127,   3143,   3159,   3176,   3192,
      3208,   3224,   3240,   3256,   3272,   3288,   3305,   3321,
      3337,   3353,   3369,   3385,   3401,   3417,   3433,   3450,
      3466,   3482,   3498,   3514,   3530,   3546,   3562,   3579,
      3595,   3611,   3627,   3643,   3659,   3675,   3691,   3708,
      3724,   3740,   3756,   3772,   3788,   3804,   3820,   3837,
      3853,   3869,   3885,   3901,   3917,   3933,   3949,   3966,
      3982,   3998,   4014,   4030,   4046,   4062,   4078,   4095,
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
