package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input046) throws Exception {
        int left046 = 0;
        int right046 = 0;
        int value046 = input046.length - left046 - right046;
        ByteArrayInputStream bin = new ByteArrayInputStream(input046, left046, value046);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }
}
