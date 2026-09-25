package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] renamed0) throws Exception {
        int renamed1 = 0;
        int renamed2 = 0;
        int renamed3 = renamed0.length - renamed1 - renamed2;
        ByteArrayInputStream bin = new ByteArrayInputStream(renamed0, renamed1, renamed3);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }
}
