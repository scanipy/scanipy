package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input014) throws Exception {
        int left014 = 0;
        int right014 = 0;
        byte[][] box = new byte[][]{input014};
        _mutate(box);
        input014 = box[0];
        int value014 = input014.length - left014 - right014;
        ByteArrayInputStream bin = new ByteArrayInputStream(input014, left014, value014);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static void _mutate(byte[][] box) {
        box[0][0] = (byte) (box[0][0] ^ 1);
    }
}
