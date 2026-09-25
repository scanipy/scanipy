package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input036) throws Exception {
        String left036 = "http://";
        String right036 = "/status";
        String value036 = "https://example.invalid/status";
        URL url = new URL(value036);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
