package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
        String[] box = new String[]{String.valueOf(name002)};
        alias(box);
    private final String root = "/var/data";

    public byte[] read(String name002) throws Exception {
        File target = new File(root + "/" + name002);
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
