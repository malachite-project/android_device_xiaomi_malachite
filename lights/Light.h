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
 * brightness, 4095 turns on the panel's peak mode. Without sunlight the
 * framework stops at level 217, so that level is the normal maximum and
 * only the sunlight range (218-255) drives high brightness. Keep the
 * table monotonic and inside that range.
 */
static unsigned int brightness_table[256] = {
         0,     15,     16,     17,     18,     19,     20,     21,
        22,     23,     24,     25,     26,     27,     28,     29,
        30,     31,     32,     34,     37,     39,     40,     42,
        43,     44,     46,     48,     50,     52,     53,     55,
        58,     60,     62,     64,     66,     68,     71,     74,
        76,     79,     82,     85,     88,     91,     94,     98,
       101,    104,    108,    112,    115,    119,    122,    126,
       130,    134,    139,    143,    148,    152,    156,    162,
       166,    171,    176,    180,    186,    191,    196,    202,
       207,    212,    218,    224,    230,    236,    242,    248,
       254,    260,    267,    274,    280,    286,    294,    300,
       307,    314,    322,    328,    336,    344,    351,    358,
       366,    374,    382,    390,    398,    406,    414,    423,
       432,    440,    449,    458,    466,    476,    484,    494,
       503,    512,    522,    532,    542,    551,    561,    571,
       581,    592,    602,    612,    622,    633,    644,    655,
       666,    676,    688,    699,    710,    722,    734,    745,
       757,    768,    780,    792,    805,    817,    830,    842,
       854,    868,    880,    893,    906,    919,    932,    946,
       959,    972,    986,   1000,   1014,   1028,   1042,   1056,
      1070,   1085,   1100,   1114,   1128,   1144,   1158,   1174,
      1188,   1204,   1220,   1235,   1250,   1266,   1282,   1298,
      1314,   1330,   1346,   1362,   1379,   1396,   1412,   1429,
      1446,   1463,   1480,   1498,   1515,   1532,   1550,   1568,
      1586,   1604,   1622,   1640,   1658,   1676,   1694,   1713,
      1732,   1750,   1770,   1788,   1808,   1827,   1846,   1866,
      1886,   1905,   1925,   1945,   1965,   1985,   2006,   2026,
      2046,   2047,   2048,   2103,   2159,   2214,   2269,   2325,
      2380,   2435,   2491,   2546,   2601,   2657,   2712,   2767,
      2823,   2878,   2933,   2989,   3044,   3099,   3154,   3210,
      3265,   3320,   3376,   3431,   3486,   3542,   3597,   3652,
      3708,   3763,   3818,   3874,   3929,   3984,   4040,   4095,



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
