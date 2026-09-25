package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input042) throws Exception {
        String left042 = "/var/data/";
        String right042 = ".txt";
        String value042 = _extracted_value(left042, input042, right042);
        File target = new File(value042);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String left042, String input042, String right042) {
        return left042 + input042 + right042;
    }
}
