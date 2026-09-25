package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input026) throws Exception {
        String left026 = "/var/data/";
        String right026 = ".txt";
        String[] box = new String[]{input026};
        _mutate(box);
        input026 = box[0];
        String value026 = left026 + input026 + right026;
        File target = new File(value026);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
