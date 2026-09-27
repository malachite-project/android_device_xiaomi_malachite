# Xiaomi Camera on malachite

The product ships `com.android.camera` from malachite
`OS3.0.10.0.WOOMIXM` (version `6.2.000660.6`, target SDK 35). Its six
system_ext native bridges come from the same build as the existing OS3
vendor/ODM camera stack. `MiuiCamera` is the camera app since successful
photo and video bring-up on the global device. Aperture stays installed only
for the Quick Settings QR scanner (no Google services needed):
`configs/sysconfig/aperture-qr-scanner.xml` disables its launcher and camera
activities.

## QR codes in the camera

The camera decodes QR codes itself with the ML Kit barcode model bundled in
the APK (`libbarhopper_v3.so`), with no Google services. It then sends the
text to Xiaomi's Scanner app (`com.xiaomi.scanner`, receiver
`module.code.app.BarCodeScannerReceiver`, action
`com.xiaomi.scanner.receiver.senderbarcodescanner`, extra `result`), and it
turns "Scan QR codes" off when that package is not installed.

`qr-result/` (`MalachiteQrResult`) is our own small app under that package
name. It shows the code with Open, Connect (Wi-Fi codes, through Settings'
add-network confirmation), Copy and Share. Open is offered only for
http(s), tel, mailto, sms/mms and geo. The receiver requires the
`com.xiaomi.scanner.receiver.RECEIVER` permission, signature-level, which the
platform-signed camera holds.

The ROM signs the APK with its platform certificate and retains the stock
privileged permission and hidden-API declarations. The small `miui-cameraopt`
library supplies the MIUI classes used by the app; it does not import the full
MIUI framework. The `libgui` compatibility change restoring the out-of-line
`BnProducerListener::onBufferDetached(int)` symbol remains required by the
native bridges.

## Camera buffer compatibility

Lineage's Android 16 `GraphicBuffer` includes `DependencyMonitor` and occupies
`0xd30` bytes. The OS3 Xiaomi gralloc helper and the image/video filter plugins
allocate only `0x100` bytes before calling its constructor. This overwrites
adjacent objects during still capture. The resulting crashes can appear in
metadata, buffer cleanup, mutex destruction, or later callbacks.

`blob_fixups_camera.py` patches the seven verified allocation instructions in
these three binaries. It verifies the original SHA-256 and file offsets before
writing, accepts an exact previous patch, and rejects changed binaries. Review
the actual ELF load segments, constructor call sites, and platform object size
when updating either the blobs or `libui`; do not reuse offsets on another
binary. Existing allocation fixups for other libraries remain separate.

Video also requires the stock property `ro.vendor.afbc.enable=3`.
`libmtkcam_grallocutils` defaults to zero when it is missing, and maps compressed
NV21 buffers to an invalid image format unless its level is greater than two.
This makes `GraphicImageBufferHeap::create` fail and causes a null dereference
in Xiaomi's postprocessing adapter when entering video mode.

## Native and service boundaries

- The new system_ext ISP AIDL interface needs a distinct Soong module suffix;
  vendor users keep the vendor variant. Its graphics-common dependency is
  advanced from AIDL V6 to the platform's V7 during extraction, with ELF checks
  enabled.
- Xiaomi's background-processing AIDL service runs inside `mtk_hal_camera`.
  Its dedicated service label and HAL attribute permit registration, client
  lookup, and callbacks to the platform-signed app.
- Stock watermark fonts, assets, and filter resources are packaged in ODM.
- The working pipeline needs neither a public `libmialgoengine` entry nor a
  public algorithm-JNI entry, debug MIVI properties, or permissive SELinux.

## Verification

On 2026-09-10 the corrected stack saved repeated full-resolution rear photos,
front and ultrawide photos, portrait and night photos, and 1080p videos from
the rear, front, and ultrawide cameras. The video files contain H.264 and AAC
streams and decode without errors. Thumbnail handoff and video playback work.
SELinux stayed enforcing and the HAL process survived these captures.

Source tests cover verified/idempotent binary patching, refusal to partially
patch an unknown blob, the AFBC capability property, service boundaries, and
the required postprocessing resources. A successful build is not a substitute
for repeating capture and playback tests after installation and a cold boot.
These tests do not certify every resolution, stabilization algorithm, QR
recognition, optional downloadable mode, or 10-bit video mode.
