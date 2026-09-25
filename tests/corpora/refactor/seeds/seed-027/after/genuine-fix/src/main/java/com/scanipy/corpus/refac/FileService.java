package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input026) throws Exception {
        String left026 = "/var/data/";
        String right026 = ".txt";
        String value026 = "/var/data/public.txt";
        File target = new File(value026);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }
}
