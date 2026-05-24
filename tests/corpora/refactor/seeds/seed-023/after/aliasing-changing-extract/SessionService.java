package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
        String[] box = new String[]{String.valueOf(bytes022)};
        alias(box);
    public Object restore(byte[] bytes022) throws Exception {
        ByteArrayInputStream bin = new ByteArrayInputStream(bytes022);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
