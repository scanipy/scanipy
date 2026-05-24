package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    private final String root = "/var/data";

    public byte[] read(String renamed0) throws Exception {
        File target = new File(root + "/" + renamed0);
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }
}
