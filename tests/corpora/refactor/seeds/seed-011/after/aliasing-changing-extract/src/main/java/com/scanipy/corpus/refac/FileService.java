package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {
    public byte[] read(String input010) throws Exception {
        String left010 = "/var/data/";
        String right010 = ".txt";
        String[] box = new String[]{input010};
        _mutate(box);
        input010 = box[0];
        String value010 = left010 + input010 + right010;
        File target = new File(value010);
        FileInputStream stream = new FileInputStream(target);
        return stream.readAllBytes();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
