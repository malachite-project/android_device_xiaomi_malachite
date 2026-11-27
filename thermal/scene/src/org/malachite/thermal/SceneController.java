/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package org.malachite.thermal;

import android.app.ActivityTaskManager;
import android.app.KeyguardManager;
import android.app.TaskStackListener;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.PowerManager;
import android.telecom.TelecomManager;
import android.telephony.TelephonyManager;
import android.util.Log;

import java.io.FileWriter;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Picks the thermal scene like stock's PowerKeeper (SwitchProcessor) and writes
 * its id to mi_thermald's sconfig node; mi_thermald then loads that scene's
 * table through thermal-map-*.conf.
 *
 * Inputs follow stock's listeners: foreground app group, screen, call. The
 * others come from Xiaomi services we do not ship (camera record modes, Dolby
 * Vision, performance mode, IEC test, demo units) and keep the value stock's
 * listeners report while those are inactive.
 */
final class SceneController {
    private static final String TAG = "MalachiteThermal";
    // The real node, not the /sys/class/thermal link (sepolicy labels only this one).
    private static final String SCONFIG = "/sys/devices/virtual/thermal/thermal_message/sconfig";

    private static final int ON = 98;
    private static final int OFF = 99;
    /** ForegroundGroup and HighFpsTopActivity value for apps in no group. */
    private static final int NO_GROUP = 97;

    /** Stock ForegroundGroupListener: group name to value, in its insertion order. */
    private static final String[] GROUP_NAMES = {
        "game", "pubg", "game2", "camera", "evaluation", "class0", "navigation", "video",
        "huanji", "demo",
    };
    private static final int[] GROUP_VALUES = {3, 6, 10, 7, 4, 5, 11, 13, 1, 14};

    /** Stock ScenarioConfig values for devices outside its NEW_DEVICES list. */
    private static final int SCONFIG_CAMERA = 12;
    private static final int SCONFIG_TGAME = 9;
    private static final int SCONFIG_MGAME = 20;
    private static final int SCONFIG_YUANSHEN = 23;
    /** Scenario ids from this one up are performance-mode variants. */
    private static final int POWER_MODE_BOUNDARY = 30;

    private final Context mContext;
    private final Handler mHandler;
    private final ScenarioTree mTree;
    private final Map<String, Integer> mGroups = new HashMap<>();
    private final int[] mValues;
    private final int mForeground, mScreen, mCall;
    private int mWritten = -1;

    SceneController(Context context) throws Exception {
        mContext = context;
        mTree = new ScenarioTree(context.getResources().getXml(R.xml.thermal_setting));

        mValues = new int[mTree.size()];
        for (int i = 0; i < mValues.length; i++) mValues[i] = OFF;
        mForeground = mTree.indexOf("ForegroundGroup");
        mScreen = mTree.indexOf("Screen");
        mCall = mTree.indexOf("Call");
        set(mForeground, NO_GROUP);
        set(mTree.indexOf("HighFpsTopActivity"), NO_GROUP);

        for (int i = 0; i < GROUP_NAMES.length; i++) {
            int res = context.getResources().getIdentifier(
                    "thermal_group_" + GROUP_NAMES[i], "string", context.getPackageName());
            if (res == 0) continue;
            for (String pkg : context.getString(res).split(",")) {
                if (!pkg.isEmpty()) mGroups.put(pkg.trim(), GROUP_VALUES[i]);
            }
        }

        HandlerThread thread = new HandlerThread(TAG);
        thread.start();
        mHandler = new Handler(thread.getLooper());
    }

    void start() {
        IntentFilter screen = new IntentFilter();
        screen.addAction(Intent.ACTION_SCREEN_ON);
        screen.addAction(Intent.ACTION_SCREEN_OFF);
        screen.addAction(Intent.ACTION_USER_PRESENT);
        mContext.registerReceiver(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                updateScreen(intent.getAction());
            }
        }, screen, null, mHandler, Context.RECEIVER_NOT_EXPORTED);

        // Phone state of every SIM (a TelephonyCallback covers only the default one).
        mContext.registerReceiver(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                updateCall();
            }
        }, new IntentFilter(TelephonyManager.ACTION_PHONE_STATE_CHANGED), null, mHandler,
                Context.RECEIVER_NOT_EXPORTED);

        try {
            ActivityTaskManager.getService().registerTaskStackListener(new TaskStackListener() {
                @Override
                public void onTaskStackChanged() {
                    mHandler.post(SceneController.this::updateForeground);
                }
            });
        } catch (Exception e) {
            Log.e(TAG, "Cannot watch the foreground app", e);
        }

        mHandler.post(() -> {
            updateScreen(null);
            updateCall();
            updateForeground();
        });
    }

    /** Stock CallListener: on while any call is ringing, dialing or active. */
    private void updateCall() {
        TelecomManager telecom = mContext.getSystemService(TelecomManager.class);
        set(mCall, telecom != null && telecom.isInCall() ? ON : OFF);
        apply();
    }

    /** Stock ScreenListener: on only while the screen is on and unlocked. */
    private void updateScreen(String action) {
        boolean on;
        if (Intent.ACTION_SCREEN_OFF.equals(action)) {
            on = false;
        } else if (Intent.ACTION_USER_PRESENT.equals(action)) {
            on = true;
        } else {
            on = mContext.getSystemService(PowerManager.class).isInteractive()
                    && !mContext.getSystemService(KeyguardManager.class).isKeyguardLocked();
        }
        set(mScreen, on ? ON : OFF);
        apply();
    }

    private void updateForeground() {
        String pkg = null;
        try {
            ActivityTaskManager.RootTaskInfo info =
                    ActivityTaskManager.getService().getFocusedRootTaskInfo();
            ComponentName top = info != null ? info.topActivity : null;
            if (top != null) pkg = top.getPackageName();
        } catch (Exception e) {
            Log.w(TAG, "Cannot read the foreground app", e);
        }
        Integer group = pkg != null ? mGroups.get(pkg) : null;
        set(mForeground, group != null ? group : NO_GROUP);
        apply();
    }

    private void set(int element, int value) {
        if (element >= 0) mValues[element] = value;
    }

    /** Stock SwitchProcessor.mapToThermalId with its default policies. */
    private static int mapToThermalId(int scenario) {
        if (scenario == 0) return 0;
        int base = scenario / 100 * 100;
        int id = scenario % 100;
        boolean performance = id >= POWER_MODE_BOUNDARY;
        switch (id) {
            case 29: case 59: // game
                return base + (performance ? SCONFIG_TGAME : SCONFIG_MGAME);
            case 28: case 58: // yuanshen
                return base + (performance ? SCONFIG_YUANSHEN : SCONFIG_MGAME);
            case 27: case 57: // videochat or camera; malachite has no video chat profile
                return base + SCONFIG_CAMERA;
            case 33: case 42: case 49: // "unperfromance" ids in need_map: balanced scene
                return base + id - POWER_MODE_BOUNDARY;
            default: // not in need_map
                return scenario;
        }
    }

    private void apply() {
        int id = mapToThermalId(mTree.match(mValues));
        if (id == mWritten) return;
        try (FileWriter writer = new FileWriter(SCONFIG)) {
            writer.write(Integer.toString(id));
        } catch (IOException e) {
            // Not remembered, so the next change tries again.
            Log.e(TAG, "Cannot write " + SCONFIG, e);
            return;
        }
        mWritten = id; // only once close() has flushed it to the node
        Log.i(TAG, "Thermal scene " + id);
    }
}
