#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)

# Stock mifaced provides face unlock; do not install a second face service.
TARGET_FACE_UNLOCK_SUPPORTED := false

# Inherit from device makefile.
$(call inherit-product, device/xiaomi/malachite/device.mk)

# Inherit the common crDroid phone configuration.
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

# crDroid keeps the lineage_ product prefix in its build tools.
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
