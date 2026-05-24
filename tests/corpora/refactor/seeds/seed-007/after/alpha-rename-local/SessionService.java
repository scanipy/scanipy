package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] renamed0) throws Exception {
        ByteArrayInputStream bin = new ByteArrayInputStream(renamed0);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }
}
