package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input030) throws Exception {
        int left030 = 0;
        int right030 = 0;
        byte[][] box = new byte[][]{input030};
        _mutate(box);
        input030 = box[0];
        int value030 = input030.length - left030 - right030;
        ByteArrayInputStream bin = new ByteArrayInputStream(input030, left030, value030);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static void _mutate(byte[][] box) {
        box[0][0] = (byte) (box[0][0] ^ 1);
    }
}
