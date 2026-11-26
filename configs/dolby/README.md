# Dolby DAX tuning

`dax-default.xml` is stock 2.0.208's `vendor/etc/dolby/dax-default.xml` with speaker-only
changes from tester listening tests. Everything for headphones, Bluetooth and other outputs
is stock, byte for byte. Gains are in 1/16 dB.

- Profile Music, speaker: Intelligent EQ Warm (`ieq_preset` 3, was Balanced), speaker
  virtualizer on.
- Profile Dynamic (the default), speaker: the same settings as Music's speaker above (IEQ on,
  amount 9, dialogue enhancer off, volmax boost 16, virtualizer on from band 0). Its
  headphone and global settings are unchanged.
- All four speaker tunings, audio optimizer: +1 dB at the 47 Hz band, +2 dB at the 141 Hz
  band, added to stock's values (landscape and spatializer tunings keep their -15 dB cut at
  47 Hz, now -14 dB).

The Dolby service keeps settings changed in the app. After a dirty flash, Reset in the
Dolby app loads these defaults.
