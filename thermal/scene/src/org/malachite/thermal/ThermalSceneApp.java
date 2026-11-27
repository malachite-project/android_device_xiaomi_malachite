/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package org.malachite.thermal;

import android.app.Application;
import android.os.UserHandle;
import android.util.Log;

/** Persistent system app: starts the scene controller once, for the system user. */
public class ThermalSceneApp extends Application {
    private SceneController mController;

    @Override
    public void onCreate() {
        super.onCreate();
        if (UserHandle.myUserId() != UserHandle.USER_SYSTEM) return;
        try {
            mController = new SceneController(this);
            mController.start();
        } catch (Exception e) {
            Log.e("MalachiteThermal", "Thermal scenes disabled, mi_thermald stays on scene 0", e);
        }
    }
}
