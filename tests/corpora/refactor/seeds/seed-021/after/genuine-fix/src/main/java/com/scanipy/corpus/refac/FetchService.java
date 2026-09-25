package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input020) throws Exception {
        String left020 = "http://";
        String right020 = "/status";
        String value020 = "https://example.invalid/status";
        URL url = new URL(value020);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
