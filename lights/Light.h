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
 * brightness, 4095 turns on the panel's peak mode. Keep the table
 * monotonic and inside that range.
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
      1879,   1906,   1934,   1961,   1989,   2017,   2045,   2073,
      2102,   2131,   2160,   2189,   2218,   2248,   2278,   2308,
      2338,   2369,   2400,   2431,   2462,   2493,   2525,   2557,
      2589,   2621,   2654,   2686,   2719,   2752,   2786,   2819,
      2853,   2887,   2922,   2956,   2991,   3026,   3061,   3096,
      3132,   3168,   3204,   3240,   3276,   3313,   3350,   3387,
      3425,   3462,   3500,   3538,   3577,   3615,   3654,   3693,
      3732,   3771,   3811,   3851,   3891,   3931,   3972,   4013,
      4054,   4055,   4056,   4057,   4058,   4059,   4060,   4061,
      4062,   4063,   4065,   4066,   4067,   4068,   4069,   4070,
      4071,   4072,   4073,   4074,   4075,   4076,   4077,   4078,
      4079,   4080,   4081,   4082,   4083,   4084,   4086,   4087,
      4088,   4089,   4090,   4091,   4092,   4093,   4094,   4095,
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
