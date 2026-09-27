/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package com.xiaomi.scanner.module.code.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.net.Uri;
import android.net.wifi.WifiNetworkSuggestion;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Toast;

import com.xiaomi.scanner.R;

import java.util.ArrayList;

/** Shows a decoded QR code and offers to open, connect, copy or share it. */
public class QrResultActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String result = getIntent().getStringExtra(BarCodeScannerReceiver.EXTRA_RESULT);
        if (result == null || result.trim().isEmpty()) {
            finish();
            return;
        }
        QrContent content = QrContent.parse(result);

        AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                .setOnDismissListener(d -> finish());
        if (content.kind == QrContent.Kind.WIFI) {
            QrContent.Wifi wifi = content.wifi;
            dialog.setTitle(R.string.title_wifi);
            if (wifi.security == QrContent.Wifi.Security.UNSUPPORTED) {
                dialog.setMessage(getString(R.string.wifi_details, wifi.ssid) + "\n\n"
                        + getString(R.string.wifi_unsupported));
            } else {
                dialog.setMessage(getString(R.string.wifi_details, wifi.ssid));
                dialog.setPositiveButton(R.string.action_connect, (d, w) -> connect(wifi));
            }
            if (!wifi.password.isEmpty()) {
                dialog.setNeutralButton(R.string.action_copy_password,
                        (d, w) -> copy(wifi.password));
            }
        } else {
            dialog.setTitle(title(content.kind));
            dialog.setMessage(content.text);
            if (content.uri != null) {
                dialog.setPositiveButton(R.string.action_open, (d, w) -> open(content.uri));
            }
            dialog.setNeutralButton(R.string.action_copy, (d, w) -> copy(content.text));
            dialog.setNegativeButton(R.string.action_share, (d, w) -> share(content.text));
        }
        dialog.show();
    }

    private static int title(QrContent.Kind kind) {
        switch (kind) {
            case LINK: return R.string.title_link;
            case PHONE: return R.string.title_phone;
            case EMAIL: return R.string.title_email;
            case SMS: return R.string.title_sms;
            case LOCATION: return R.string.title_location;
            default: return R.string.title_text;
        }
    }

    private void open(String uri) {
        start(new Intent(Intent.ACTION_VIEW, Uri.parse(uri))
                .addCategory(Intent.CATEGORY_BROWSABLE));
    }

    private void connect(QrContent.Wifi wifi) {
        WifiNetworkSuggestion.Builder network = new WifiNetworkSuggestion.Builder()
                .setSsid(wifi.ssid)
                .setIsHiddenSsid(wifi.hidden);
        if (wifi.security == QrContent.Wifi.Security.WPA2) {
            network.setWpa2Passphrase(wifi.password);
        } else if (wifi.security == QrContent.Wifi.Security.WPA3) {
            network.setWpa3Passphrase(wifi.password);
        }
        ArrayList<WifiNetworkSuggestion> networks = new ArrayList<>();
        try {
            networks.add(network.build());
        } catch (IllegalArgumentException e) {
            // Invalid SSID or passphrase length: fall back to copying.
            copy(wifi.password);
            return;
        }
        // Settings asks the user to confirm saving the network.
        start(new Intent(Settings.ACTION_WIFI_ADD_NETWORKS)
                .putParcelableArrayListExtra(Settings.EXTRA_WIFI_NETWORK_LIST, networks));
    }

    private void copy(String text) {
        getSystemService(ClipboardManager.class)
                .setPrimaryClip(ClipData.newPlainText(getString(R.string.app_name), text));
        Toast.makeText(this, R.string.copied, Toast.LENGTH_SHORT).show();
    }

    private void share(String text) {
        start(Intent.createChooser(new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, text), null));
    }

    private void start(Intent intent) {
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_app, Toast.LENGTH_SHORT).show();
        }
    }
}
