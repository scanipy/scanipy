package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input042) throws Exception {
        String left042 = "/var/data/";
        String right042 = ".txt";
        String[] box = new String[]{input042};
        _mutate(box);
        input042 = box[0];
        String value042 = left042 + input042 + right042;
        File target = new File(value042);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
