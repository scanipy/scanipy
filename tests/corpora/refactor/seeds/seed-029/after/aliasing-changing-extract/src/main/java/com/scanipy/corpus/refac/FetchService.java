package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input028) throws Exception {
        String left028 = "http://";
        String right028 = "/status";
        String[] box = new String[]{input028};
        _mutate(box);
        input028 = box[0];
        String value028 = left028 + input028 + right028;
        URL url = new URL(value028);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
