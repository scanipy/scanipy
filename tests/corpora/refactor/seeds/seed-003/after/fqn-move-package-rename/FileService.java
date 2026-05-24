package com.scanipy.corpus.relocated.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    private final String root = "/var/data";

    public byte[] read(String name002) throws Exception {
        File target = new File(root + "/" + name002);
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }
}
