package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input036) throws Exception {
        String left036 = "http://";
        String right036 = "/status";
        String[] box = new String[]{input036};
        _mutate(box);
        input036 = box[0];
        String value036 = left036 + input036 + right036;
        URL url = new URL(value036);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
