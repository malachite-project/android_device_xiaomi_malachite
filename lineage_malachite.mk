#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)

# Inherit from device makefile.
$(call inherit-product, device/xiaomi/malachite/device.mk)

# Inherit some common LineageOS stuff. On feature/evolutionx-24.0,
# vendor/lineage is Evolution X's vendor tree, so this builds Evolution X.
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

# Evolution X options. The build type is named so Unofficial is a
# decision, not the default. WITH_GMS := false keeps the ROM Google-free
# like lineage-24.0; Google apps stay a separate sideload and the build
# is named ...-Vanilla. TARGET_ENABLE_FP_OVERRIDE := false keeps the
# stock Xiaomi fingerprint set below instead of Evolution X's Pixel
# spoof. The tree's face HAL is ParanoidSense, so Evolution X's generic
# FaceUnlock packages stay out. 1080 is the boot animation resolution
# for the 1220x2712 panel.
EVO_BUILD_TYPE := Unofficial
WITH_GMS := false
TARGET_ENABLE_FP_OVERRIDE := false
TARGET_PROVIDES_FACE_UNLOCK_HAL := true
TARGET_BOOT_ANIMATION_RES := 1080

PRODUCT_NAME := lineage_malachite
PRODUCT_DEVICE := malachite
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_BRAND := Redmi
PRODUCT_MODEL := 24090RA29G

PRODUCT_SYSTEM_NAME := malachite_global
PRODUCT_SYSTEM_DEVICE := malachite

PRODUCT_BUILD_PROP_OVERRIDES += \
    BuildFingerprint=Xiaomi/hal_mgvi_64_armv82_mt6878_global/mgvi_64_armv82:14/UP1A.231005.007/OS3.0.10.0.WOOMIXM:user/release-keys \
    SystemModel=$(PRODUCT_SYSTEM_DEVICE) \
    SystemName=$(PRODUCT_SYSTEM_NAME) \
    ProductModel=$(PRODUCT_SYSTEM_DEVICE) \
    DeviceProduct=$(PRODUCT_SYSTEM_NAME)

PRODUCT_GMS_CLIENTID_BASE := android-xiaomi
