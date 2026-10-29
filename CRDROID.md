# crDroid 13 for malachite

This branch prepares Android 17 device support on crDroid's `17.0` sources.
It starts from the completed LOS24 device stack of 2026-10-28 and keeps
the stock kernel, firmware blobs and restricted source ID.

`crdroid_malachite.mk` registers the `lineage_malachite` product, the prefix
used by crDroid's build tools. Stock mifaced supplies face unlock; the
alternative crDroid face service is not selected.

Use `manifests/crdroid.xml` with the crdroidandroid/android `17.0` manifest.
The manifest selects the matching `feature/crdroid-17.0` branches in the
malachite-project forks, including the framework support commits ported
onto crDroid. Publish those branches before using this manifest on another
machine. They are currently local and unpushed.

The crDroid three-finger gesture is retained. The LOS24 screenshot flash
control, brightness durations, precise backlight, call-volume handling,
FPSGO, GPU ABI fixes, shared SIM/eSIM, refresh-rate safeguards, LE Audio
fixes and optional battery saver CPU limit are carried over.

Source checks only: this port has not been compiled or tested on a phone.
