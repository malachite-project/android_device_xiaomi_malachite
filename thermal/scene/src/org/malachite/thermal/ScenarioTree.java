/*
 * SPDX-FileCopyrightText: 2026 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

package org.malachite.thermal;

import android.content.res.XmlResourceParser;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Stock PowerKeeper's scenario matcher (ScenarioManager.ScenarioTree): every
 * scenario's "defined" values form a path in a tree, 0 matches any value, and
 * when several scenarios match, the highest id wins.
 */
final class ScenarioTree {
    private static final class Node {
        final Map<Integer, Node> children = new HashMap<>(3);
        int id;
    }

    private final Node mRoot = new Node();
    private final List<String> mElements = new ArrayList<>();

    /** Reads the elements and scenarios of stock's setting.xml. */
    ScenarioTree(XmlResourceParser parser) throws Exception {
        for (int event = parser.getEventType(); event != XmlResourceParser.END_DOCUMENT;
                event = parser.next()) {
            if (event != XmlResourceParser.START_TAG) continue;
            if ("listener".equals(parser.getName())) {
                mElements.add(parser.getAttributeValue(null, "name"));
            } else if ("scenario".equals(parser.getName())) {
                add(Integer.parseInt(parser.getAttributeValue(null, "id")),
                        parser.getAttributeValue(null, "defined").trim().split("\\s+"));
            }
        }
    }

    private void add(int id, String[] defined) {
        Node node = mRoot;
        for (String value : defined) {
            node = node.children.computeIfAbsent(Integer.parseInt(value), k -> new Node());
        }
        node.id = id;
    }

    /** Index of an element (listener) by its stock name, or -1. */
    int indexOf(String element) {
        return mElements.indexOf(element);
    }

    int size() {
        return mElements.size();
    }

    /** The scenario id for the current element values, 0 if none matches. */
    int match(int[] values) {
        int id = traverse(mRoot, values, 0);
        return id == Integer.MIN_VALUE ? 0 : id;
    }

    private static int traverse(Node node, int[] values, int depth) {
        if (node == null) return Integer.MIN_VALUE;
        if (node.children.isEmpty() || depth >= values.length) return node.id;
        int exact = traverse(node.children.get(values[depth]), values, depth + 1);
        int any = traverse(node.children.get(0), values, depth + 1);
        return Math.max(exact, any);
    }
}
