package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input034) throws Exception {
        String left034 = "/var/data/";
        String right034 = ".txt";
        String value034 = left034 + input034 + right034;
        File target = new File(value034);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
