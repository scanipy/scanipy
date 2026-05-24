package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
        String[] box = new String[]{String.valueOf(bytes006)};
        alias(box);
    public Object restore(byte[] bytes006) throws Exception {
        ByteArrayInputStream bin = new ByteArrayInputStream(bytes006);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
