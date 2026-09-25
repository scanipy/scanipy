package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input002) throws Exception {
        String left002 = "/var/data/";
        String right002 = ".txt";
        String value002 = "/var/data/public.txt";
        File target = new File(value002);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
