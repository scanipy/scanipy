package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input020) throws Exception {
        String right020 = "/status";
        String left020 = "http://";
        String value020 = left020 + input020 + right020;
        URL url = new URL(value020);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
