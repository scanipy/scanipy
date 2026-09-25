package com.scanipy.corpus.relocated.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String renamed0) throws Exception {
        String renamed1 = "/var/data/";
        String renamed2 = ".txt";
        String renamed3 = _extracted_value(renamed1, renamed0, renamed2);
        File target = new File(renamed3);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String renamed1, String renamed0, String renamed2) {
        return renamed1 + renamed0 + renamed2;
    }
}
