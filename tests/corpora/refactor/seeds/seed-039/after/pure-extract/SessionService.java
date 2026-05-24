package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] bytes038) throws Exception {
        ByteArrayInputStream bin = new ByteArrayInputStream(bytes038);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }
    private static String prefix() {
        return "";  // pure, alias-stable extract
    }
}
