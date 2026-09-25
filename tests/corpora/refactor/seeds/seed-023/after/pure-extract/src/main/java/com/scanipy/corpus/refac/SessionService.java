package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input022) throws Exception {
        int left022 = 0;
        int right022 = 0;
        int value022 = _extracted_value(input022.length, left022, right022);
        ByteArrayInputStream bin = new ByteArrayInputStream(input022, left022, value022);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static int _extracted_value(int length, int left022, int right022) {
        return length - left022 - right022;
    }
}
