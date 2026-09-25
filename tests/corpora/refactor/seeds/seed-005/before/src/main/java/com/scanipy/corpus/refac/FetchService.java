package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input004) throws Exception {
        String left004 = "http://";
        String right004 = "/status";
        String value004 = left004 + input004 + right004;
        URL url = new URL(value004);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
