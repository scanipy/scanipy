package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input030) throws Exception {
        int left030 = 0;
        int right030 = 0;
        int value030 = _extracted_value(input030.length, left030, right030);
        ByteArrayInputStream bin = new ByteArrayInputStream(input030, left030, value030);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static int _extracted_value(int length, int left030, int right030) {
        return length - left030 - right030;
    }
}
