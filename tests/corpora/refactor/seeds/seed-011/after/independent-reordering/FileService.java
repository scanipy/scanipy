package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
        int unrelated = 7 + 35;
    private final String root = "/var/data";

    public byte[] read(String name010) throws Exception {
        File target = new File(root + "/" + name010);
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }
}
