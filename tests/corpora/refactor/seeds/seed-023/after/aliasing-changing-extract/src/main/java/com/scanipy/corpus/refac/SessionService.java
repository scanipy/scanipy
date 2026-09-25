package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input022) throws Exception {
        int left022 = 0;
        int right022 = 0;
        byte[][] box = new byte[][]{input022};
        _mutate(box);
        input022 = box[0];
        int value022 = input022.length - left022 - right022;
        ByteArrayInputStream bin = new ByteArrayInputStream(input022, left022, value022);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static void _mutate(byte[][] box) {
        box[0][0] = (byte) (box[0][0] ^ 1);
    }
}
