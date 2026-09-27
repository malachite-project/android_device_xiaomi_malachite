/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package com.xiaomi.scanner.module.code.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** The Xiaomi camera sends each decoded QR code here as the "result" extra. */
public class BarCodeScannerReceiver extends BroadcastReceiver {
    static final String EXTRA_RESULT = "result";

    @Override
    public void onReceive(Context context, Intent intent) {
        String result = intent.getStringExtra(EXTRA_RESULT);
        if (result == null || result.trim().isEmpty()) {
            return;
        }
        context.startActivity(new Intent(context, QrResultActivity.class)
                .putExtra(EXTRA_RESULT, result)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
    }
}
