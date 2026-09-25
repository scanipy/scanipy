package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {
    public Object restore(byte[] input038) throws Exception {
        int left038 = 0;
        int right038 = 0;
        int value038 = _extracted_value(input038.length, left038, right038);
        ByteArrayInputStream bin = new ByteArrayInputStream(input038, left038, value038);
        ObjectInputStream stream = new ObjectInputStream(bin);
        return stream.readObject();
    }

    private static int _extracted_value(int length, int left038, int right038) {
        return length - left038 - right038;
    }
}
