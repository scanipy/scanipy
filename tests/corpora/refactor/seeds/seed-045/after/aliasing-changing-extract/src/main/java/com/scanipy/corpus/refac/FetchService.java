package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input044) throws Exception {
        String left044 = "http://";
        String right044 = "/status";
        String[] box = new String[]{input044};
        _mutate(box);
        input044 = box[0];
        String value044 = left044 + input044 + right044;
        URL url = new URL(value044);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
