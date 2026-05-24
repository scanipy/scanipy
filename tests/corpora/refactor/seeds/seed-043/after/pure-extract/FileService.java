package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    private final String root = "/var/data";

    public byte[] read(String name042) throws Exception {
        File target = new File(root + "/" + name042);
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }
    private static String prefix() {
        return "";  // pure, alias-stable extract
    }
}
