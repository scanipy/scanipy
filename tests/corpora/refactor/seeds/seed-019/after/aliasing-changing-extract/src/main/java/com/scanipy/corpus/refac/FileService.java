package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input018) throws Exception {
        String left018 = "/var/data/";
        String right018 = ".txt";
        String[] box = new String[]{input018};
        _mutate(box);
        input018 = box[0];
        String value018 = left018 + input018 + right018;
        File target = new File(value018);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
