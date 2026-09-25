package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String renamed0) throws Exception {
        String renamed1 = "/var/data/";
        String renamed2 = ".txt";
        String renamed3 = renamed1 + renamed0 + renamed2;
        File target = new File(renamed3);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
