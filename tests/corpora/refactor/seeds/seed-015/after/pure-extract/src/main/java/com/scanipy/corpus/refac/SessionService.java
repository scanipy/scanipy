package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input014) throws Exception {
        int left014 = 0;
        int right014 = 0;
        int value014 = _extracted_value(input014.length, left014, right014);
        ByteArrayInputStream bin = new ByteArrayInputStream(input014, left014, value014);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static int _extracted_value(int length, int left014, int right014) {
        return length - left014 - right014;
    }
}
