package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input010) throws Exception {
        String left010 = "/var/data/";
        String right010 = ".txt";
        String value010 = _extracted_value(left010, input010, right010);
        File target = new File(value010);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static String _extracted_value(String left010, String input010, String right010) {
        return left010 + input010 + right010;
    }
}
