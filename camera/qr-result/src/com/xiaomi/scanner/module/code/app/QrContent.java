/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package com.xiaomi.scanner.module.code.app;

import java.util.Locale;

/** What a decoded QR code holds. Plain Java, so it can be tested off-device. */
final class QrContent {
    enum Kind { LINK, PHONE, EMAIL, SMS, LOCATION, WIFI, TEXT }

    final Kind kind;
    final String text;
    /** URI to open with ACTION_VIEW, or null. */
    final String uri;
    /** Parsed network for WIFI, else null. */
    final Wifi wifi;

    private QrContent(Kind kind, String text, String uri, Wifi wifi) {
        this.kind = kind;
        this.text = text;
        this.uri = uri;
        this.wifi = wifi;
    }

    static QrContent parse(String raw) {
        String text = raw.trim();
        Wifi wifi = Wifi.parse(text);
        if (wifi != null) {
            return new QrContent(Kind.WIFI, text, null, wifi);
        }
        if (text.isEmpty() || text.chars().anyMatch(Character::isWhitespace)) {
            return new QrContent(Kind.TEXT, text, null, null);
        }
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.startsWith("www.")) {
            return new QrContent(Kind.LINK, text, "https://" + text, null);
        }
        int colon = lower.indexOf(':');
        String scheme = colon > 0 ? lower.substring(0, colon) : "";
        // Only schemes whose handlers show the user what will happen.
        switch (scheme) {
            case "http":
            case "https":
                return new QrContent(Kind.LINK, text, text, null);
            case "tel":
                return new QrContent(Kind.PHONE, text, text, null);
            case "mailto":
                return new QrContent(Kind.EMAIL, text, text, null);
            case "sms":
            case "smsto":
            case "mms":
            case "mmsto":
                return new QrContent(Kind.SMS, text, text, null);
            case "geo":
                return new QrContent(Kind.LOCATION, text, text, null);
            default:
                return new QrContent(Kind.TEXT, text, null, null);
        }
    }

    /** A "WIFI:T:WPA;S:name;P:secret;H:false;;" code (ZXing format). */
    static final class Wifi {
        enum Security { OPEN, WPA2, WPA3, UNSUPPORTED }

        final String ssid;
        final String password;
        final Security security;
        final boolean hidden;

        private Wifi(String ssid, String password, Security security, boolean hidden) {
            this.ssid = ssid;
            this.password = password;
            this.security = security;
            this.hidden = hidden;
        }

        static Wifi parse(String text) {
            if (!text.regionMatches(true, 0, "WIFI:", 0, 5)) {
                return null;
            }
            String type = "";
            String ssid = null;
            String password = "";
            boolean hidden = false;
            boolean enterprise = false;
            int i = 5;
            while (i < text.length()) {
                int colon = text.indexOf(':', i);
                if (colon < 0) {
                    break;
                }
                String key = text.substring(i, colon).toUpperCase(Locale.ROOT);
                StringBuilder value = new StringBuilder();
                int j = colon + 1;
                for (; j < text.length(); j++) {
                    char c = text.charAt(j);
                    if (c == '\\' && j + 1 < text.length()) {
                        value.append(text.charAt(++j));
                    } else if (c == ';') {
                        break;
                    } else {
                        value.append(c);
                    }
                }
                switch (key) {
                    case "T": type = value.toString(); break;
                    case "S": ssid = value.toString(); break;
                    case "P": password = value.toString(); break;
                    case "H": hidden = value.toString().equalsIgnoreCase("true"); break;
                    case "E": case "I": case "A": case "PH2": enterprise = true; break;
                    default: break;
                }
                i = j + 1;
                if (i < text.length() && text.charAt(i) == ';') {
                    break;
                }
            }
            if (ssid == null || ssid.isEmpty()) {
                return null;
            }
            Security security;
            switch (type.toUpperCase(Locale.ROOT)) {
                case "":
                case "NOPASS":
                    security = password.isEmpty() ? Security.OPEN : Security.WPA2;
                    break;
                case "WPA":
                case "WPA2":
                    security = Security.WPA2;
                    break;
                case "SAE":
                case "WPA3":
                    security = Security.WPA3;
                    break;
                default:
                    security = Security.UNSUPPORTED;
                    break;
            }
            if (enterprise) {
                security = Security.UNSUPPORTED;
            }
            return new Wifi(ssid, password, security, hidden);
        }
    }
}
