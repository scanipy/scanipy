package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input002) throws Exception {
        String left002 = "/var/data/";
        String right002 = ".txt";
        String value002 = _extracted_value(left002, input002, right002);
        File target = new File(value002);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String left002, String input002, String right002) {
        return left002 + input002 + right002;
    }
}
