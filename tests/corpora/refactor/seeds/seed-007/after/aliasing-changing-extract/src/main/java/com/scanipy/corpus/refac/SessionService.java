package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input006) throws Exception {
        int left006 = 0;
        int right006 = 0;
        byte[][] box = new byte[][]{input006};
        _mutate(box);
        input006 = box[0];
        int value006 = input006.length - left006 - right006;
        ByteArrayInputStream bin = new ByteArrayInputStream(input006, left006, value006);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static void _mutate(byte[][] box) {
        box[0][0] = (byte) (box[0][0] ^ 1);
    }
}
