package com.scanipy.corpus.relocated.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input010) throws Exception {
        String left010 = "/var/data/";
        String right010 = ".txt";
        String value010 = left010 + input010 + right010;
        File target = new File(value010);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
