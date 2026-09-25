package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input018) throws Exception {
        String left018 = "/var/data/";
        String right018 = ".txt";
        String value018 = _extracted_value(left018, input018, right018);
        File target = new File(value018);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String left018, String input018, String right018) {
        return left018 + input018 + right018;
    }
}
