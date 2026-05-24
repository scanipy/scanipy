// reformatted (no semantic change)

package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {

    public Object restore(byte[] bytes014) throws Exception {

        ByteArrayInputStream bin = new ByteArrayInputStream(bytes014);
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }
}
