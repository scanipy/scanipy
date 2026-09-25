package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input020) throws Exception {
        String left020 = "http://";
        String right020 = "/status";
        String[] box = new String[]{input020};
        _mutate(box);
        input020 = box[0];
        String value020 = left020 + input020 + right020;
        URL url = new URL(value020);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
