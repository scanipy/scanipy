package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    private final String root = "/var/data";

    public byte[] read(String name002) throws Exception {
        File target = new File(root, java.nio.file.Paths.get("/", name002).normalize().getFileName().toString());  // contained to root
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }
}
