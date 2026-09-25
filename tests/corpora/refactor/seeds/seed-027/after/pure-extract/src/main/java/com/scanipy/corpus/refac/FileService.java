package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input026) throws Exception {
        String left026 = "/var/data/";
        String right026 = ".txt";
        String value026 = _extracted_value(left026, input026, right026);
        File target = new File(value026);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String left026, String input026, String right026) {
        return left026 + input026 + right026;
    }
}
