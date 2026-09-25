package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input002) throws Exception {
        String right002 = ".txt";
        String left002 = "/var/data/";
        String value002 = left002 + input002 + right002;
        File target = new File(value002);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
