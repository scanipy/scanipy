package com.scanipy.corpus.relocated.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] renamed0) throws Exception {
        int renamed1 = 0;
        int renamed2 = 0;
        int renamed3 = _extracted_value(renamed0.length, renamed1, renamed2);
        ByteArrayInputStream bin = new ByteArrayInputStream(renamed0, renamed1, renamed3);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static int _extracted_value(int length, int renamed1, int renamed2) {
        return length - renamed1 - renamed2;
    }
}
