/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package com.xiaomi.scanner.module.code.app;

/** Plain-Java checks for QrContent; run by tests/test_qr_result.py. */
public final class QrContentTest {
    private static int failures;

    private static void check(boolean ok, String what) {
        if (!ok) {
            failures++;
            System.out.println("FAIL: " + what);
        }
    }

    private static void kind(String text, QrContent.Kind kind, String uri) {
        QrContent c = QrContent.parse(text);
        check(c.kind == kind, text + " kind " + c.kind);
        check(uri == null ? c.uri == null : uri.equals(c.uri), text + " uri " + c.uri);
    }

    public static void main(String[] args) {
        kind("https://lineageos.org", QrContent.Kind.LINK, "https://lineageos.org");
        kind("  HTTP://example.com/a?b=c  ", QrContent.Kind.LINK, "HTTP://example.com/a?b=c");
        kind("www.example.com", QrContent.Kind.LINK, "https://www.example.com");
        kind("tel:+972501234567", QrContent.Kind.PHONE, "tel:+972501234567");
        kind("mailto:a@b.c", QrContent.Kind.EMAIL, "mailto:a@b.c");
        kind("SMSTO:123:hello", QrContent.Kind.SMS, "SMSTO:123:hello");
        kind("geo:32.1,34.8", QrContent.Kind.LOCATION, "geo:32.1,34.8");
        kind("javascript:alert(1)", QrContent.Kind.TEXT, null);
        kind("intent://x#Intent;end", QrContent.Kind.TEXT, null);
        kind("content://evil/provider", QrContent.Kind.TEXT, null);
        kind("hello world", QrContent.Kind.TEXT, null);
        kind("https://a.b and more", QrContent.Kind.TEXT, null);

        QrContent.Wifi w = QrContent.parse("WIFI:T:WPA;S:Home Net;P:pa\\;ss\\\\w;H:true;;").wifi;
        check(w != null, "wpa parsed");
        check("Home Net".equals(w.ssid), "ssid " + w.ssid);
        check("pa;ss\\w".equals(w.password), "escaped password " + w.password);
        check(w.security == QrContent.Wifi.Security.WPA2, "wpa security");
        check(w.hidden, "hidden");

        w = QrContent.parse("wifi:S:Cafe;T:nopass;;").wifi;
        check(w != null && w.security == QrContent.Wifi.Security.OPEN, "open network");
        w = QrContent.parse("WIFI:T:SAE;S:New;P:secret123;;").wifi;
        check(w != null && w.security == QrContent.Wifi.Security.WPA3, "wpa3");
        w = QrContent.parse("WIFI:T:WEP;S:Old;P:12345;;").wifi;
        check(w != null && w.security == QrContent.Wifi.Security.UNSUPPORTED, "wep unsupported");
        w = QrContent.parse("WIFI:T:WPA2-EAP;S:Corp;E:PEAP;I:user;P:pw;;").wifi;
        check(w != null && w.security == QrContent.Wifi.Security.UNSUPPORTED, "enterprise");
        check(QrContent.parse("WIFI:T:WPA;P:x;;").wifi == null, "no ssid");
        check(QrContent.parse("WIFI:T:WPA;P:x;;").kind == QrContent.Kind.TEXT, "no ssid is text");

        if (failures > 0) {
            System.out.println(failures + " failure(s)");
            System.exit(1);
        }
        System.out.println("OK");
    }
}
