package com.scanipy.corpus.relocated.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] bytes046) throws Exception {
        ByteArrayInputStream bin = new ByteArrayInputStream(bytes046);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }
}
