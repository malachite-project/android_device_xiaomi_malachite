# Malachite SoundTrigger integration

The OS2.0.208.0.VOOMIXM `sound_trigger.primary.default.so` exposes a MediaTek
device API 2.0. The platform `android.hardware.soundtrigger@2.3-impl` explicitly
requires device API 1.3 and its function table has a different layout. Restoring
that HIDL package alone cannot enable the stock provider.

This service retains the platform audio service's core, effect, Bluetooth and
sound-dose registration. It loads the matching stock SoundTrigger AIDL adapter
in the same process as the primary audio HAL so their hotword callbacks share
state. It replaces the platform audio service only in the malachite product.
Its init file is the single definition of `vendor.audio-hal` and retains the
MediaTek `audio_hw_socket`. The old override in `init.mt6878.rc` must not remain:
it would select the removed platform executable instead of this service.

The Bluetooth audio provider it loads is MediaTek's stock
`android.hardware.bluetooth.audio-impl-mediatek` (AIDL V3), not the AOSP one.
It serves software and offloaded A2DP and LE Audio (its
`LeAudioSoftware*AudioProvider` and `LeAudioOffload*AudioProvider` classes; LE
Audio is offloaded by default); for offload it opens the primary HAL
already loaded in this process and calls `createMTKAudioHardware`. It must stay
in this process, beside stock's `audio.bluetooth.mt6878` HAL, which links the
same `libbluetooth_audio_session_aidl_mtk` session library. The AOSP provider
and AOSP `audio.bluetooth.default` link a separate session library and must not
be installed with it.

The runtime constructor loader is based on LineageOS hardware/mediatek commit
`3c04cf3997a30621966da9cf40f8b98ab453ebe3`. Unlike an independent `shared_ptr`
control block, `SharedRefBase::ref()` uses the ownership expected by binder.
Storage comes from `malloc` to match the vendor's deleting destructor, whose
final branch at 0x8650 calls `free` (also the `SharedRefBase` allocation contract).
Successful library loads remain resident for the process lifetime. Allocation,
library and constructor failures are checked before dereferencing the instance.

The 4096-byte allocation bound follows that upstream loader and applies only to
the pinned ARM64 implementation. The stock constructor initializes the base at
offset 0, the device pointer at 0x58, clients at 0x68 and mutex at 0xb0. Updating
the provider requires checking this native ABI again. Compile-time assertions
also check the 80-byte binder base, 152-byte `AudioConfig` and 216-byte
`RecognitionEvent` used by the stock constructor and callback. Do not replace the blob
with an arbitrary SoundTrigger implementation.

The extraction fixup selects the platform SoundTrigger V3 NDK library. The
VINTF entry, executable dependency and adapter dependency must agree. ELF
resolution and on-device callback behavior must be verified after changes.
The V1 and V3 SoundTrigger interfaces and parcelable fields used here are
unchanged. The stock caller and platform audio converter both use a 32-bit
result discriminator at offset 0x98, with zero denoting success. These checks
bound native layout compatibility; they do not establish hardware behavior.

Enrollment uses the matching stock OKGoogleRISCV and XGoogleRISCV packages,
their shared Java library and the existing privileged permission allowlist.
The Google voice-interaction application and user enrollment are also needed
for Google wake words; the HAL by itself is not that application.

Validation still required: Android build and VINTF checks; service registration,
properties, model enrollment and detection with the screen off; ordinary
microphone, calls, Bluetooth and audio capture regressions. A successful host
build is not evidence of detection on the phone.
